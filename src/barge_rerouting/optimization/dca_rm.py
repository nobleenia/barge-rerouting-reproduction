"""Current-demand allocation with future-demand revenue management."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.domain import (
    CustomerCategory,
    FutureValueInterpretation,
)
from barge_rerouting.instance import (
    DemandNetworkIndex,
    ExperimentInstance,
)
from barge_rerouting.revenue_management import (
    FutureDemandCandidate,
    FutureDemandSet,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
)

DCA_RM_TOLERANCE = 1e-6


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw_name = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw_name)


def _validate_tolerance(value: object) -> float:
    """Validate and return a positive finite tolerance."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("tolerance must be a real number.")

    tolerance = float(value)

    if not isfinite(tolerance):
        raise ValueError("tolerance must be finite.")

    if tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")

    return tolerance


def _create_acceptance_variable(
    model: Any,
    *,
    demand_id: str,
    category: CustomerCategory,
) -> Any:
    """Create the current request's acceptance variable."""
    variable_name = _solver_name("xi", demand_id)

    if category is CustomerCategory.REGULAR:
        return model.continuous_var(
            lb=1.0,
            ub=1.0,
            name=variable_name,
        )

    if category is CustomerCategory.PARTIALLY_SPOT:
        return model.continuous_var(
            lb=0.0,
            ub=1.0,
            name=variable_name,
        )

    if category is CustomerCategory.FULLY_SPOT:
        return model.binary_var(name=variable_name)

    raise ValueError(f"Unsupported customer category: {category}")


@dataclass(frozen=True, slots=True)
class DcaRmModelArtifacts:
    """DOcplex objects for one DCA-RM booking decision."""

    instance: ExperimentInstance
    state: RollingBookingState
    event: BookingDecisionEvent
    future_set: FutureDemandSet
    value_interpretation: FutureValueInterpretation
    capacity_snapshot: TransportCapacitySnapshot | None
    current_network_index: DemandNetworkIndex
    model: Any
    acceptance_variable: Any
    current_flow_variables: dict[str, Any]
    selector_variables: dict[tuple[str, int], Any]
    protected_volume_variables: dict[str, Any]
    future_flow_variables: dict[tuple[str, str], Any]
    current_flow_balance_constraints: dict[object, Any]
    current_sink_balance_constraint: Any
    selector_constraints: dict[str, Any]
    protected_volume_constraints: dict[str, Any]
    future_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ]
    future_sink_balance_constraints: dict[str, Any]
    capacity_constraints: dict[str, Any]
    available_capacities: dict[str, float]
    future_value_coefficients: dict[
        tuple[str, int],
        float,
    ]

    @property
    def selector_variable_count(self) -> int:
        """Return the number of binary y(k,j) variables."""
        return len(self.selector_variables)

    @property
    def future_flow_variable_count(self) -> int:
        """Return the tentative future-flow count."""
        return len(self.future_flow_variables)

    @property
    def forecast_count(self) -> int:
        """Return the number of forecasts in K(current)."""
        return len(self.future_set.candidates)


@dataclass(frozen=True, slots=True)
class DcaRmCurrentFlowResult:
    """Current-demand flow on one arc."""

    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class FutureSelectorResult:
    """Solved value of one future protection selector."""

    forecast_id: str
    protection_level: int
    selected_value: float


@dataclass(frozen=True, slots=True)
class FutureTentativeFlowResult:
    """Tentative protected future flow on one arc."""

    forecast_id: str
    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class FutureProtectionResult:
    """Selected protection and expected value for one forecast."""

    forecast_id: str
    protection_level: int
    protected_volume: float
    credited_expected_volume: float
    credited_expected_revenue: float


@dataclass(frozen=True, slots=True)
class DcaRmSolution:
    """Extracted solution of one DCA-RM model."""

    event_id: str
    demand_id: str
    value_interpretation: FutureValueInterpretation
    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptance_fraction: float | None
    current_revenue: float | None
    future_expected_revenue: float | None
    current_flows: tuple[DcaRmCurrentFlowResult, ...]
    selectors: tuple[FutureSelectorResult, ...]
    protections: tuple[FutureProtectionResult, ...]
    future_flows: tuple[FutureTentativeFlowResult, ...]

    def current_flow_on(self, arc_id: str) -> float:
        """Return current-demand flow on one arc."""
        for result in self.current_flows:
            if result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown current-demand arc: {arc_id}")

    def selector_value(
        self,
        forecast_id: str,
        protection_level: int,
    ) -> float:
        """Return one solved y(k,j) value."""
        for result in self.selectors:
            if result.forecast_id == forecast_id and result.protection_level == protection_level:
                return float(result.selected_value)

        raise KeyError(f"Unknown future selector: {forecast_id}, {protection_level}")

    def protection_for(
        self,
        forecast_id: str,
    ) -> FutureProtectionResult:
        """Return the selected result for one forecast."""
        for result in self.protections:
            if result.forecast_id == forecast_id:
                return result

        raise KeyError(f"Unknown protected forecast: {forecast_id}")

    def future_flow_on(
        self,
        forecast_id: str,
        arc_id: str,
    ) -> float:
        """Return tentative future flow on one arc."""
        for result in self.future_flows:
            if result.forecast_id == forecast_id and result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown future forecast-arc combination: {forecast_id}, {arc_id}")


@dataclass(frozen=True, slots=True)
class DcaRmValidationReport:
    """Independent numerical validation of DCA-RM."""

    is_valid: bool
    tolerance: float
    recomputed_objective: float
    reported_objective: float
    max_acceptance_violation: float
    max_selector_binary_violation: float
    max_selector_exclusivity_violation: float
    max_protected_volume_violation: float
    max_negative_flow_violation: float
    max_flow_balance_violation: float
    max_sink_balance_violation: float
    max_capacity_violation: float
    objective_violation: float
    violations: tuple[str, ...]


def _validate_inputs(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    future_set: FutureDemandSet,
    value_interpretation: FutureValueInterpretation,
    capacity_snapshot: TransportCapacitySnapshot | None,
) -> None:
    """Validate the common DCA-RM inputs."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(future_set, FutureDemandSet):
        raise TypeError("future_set must be a FutureDemandSet.")

    if not isinstance(
        value_interpretation,
        FutureValueInterpretation,
    ):
        raise TypeError("value_interpretation must be a FutureValueInterpretation.")

    if state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The event must be the next unprocessed event.")

    if future_set.current_event != event:
        raise ValueError("The future-demand set must belong to the booking event.")

    if instance.demand_by_id(event.demand_id) != event.demand:
        raise ValueError("The booking event demand does not match the instance.")

    if capacity_snapshot is not None:
        if not isinstance(
            capacity_snapshot,
            TransportCapacitySnapshot,
        ):
            raise TypeError("capacity_snapshot must be a TransportCapacitySnapshot or None.")

        if capacity_snapshot.instance_fingerprint != instance.demand_fingerprint:
            raise ValueError("The capacity snapshot belongs to another instance.")

        if capacity_snapshot.physical_time != event.decision_time:
            raise ValueError("Capacity snapshot time must equal the decision time.")


def _available_capacity(
    instance: ExperimentInstance,
    state: RollingBookingState,
    arc_id: str,
    capacity_snapshot: TransportCapacitySnapshot | None,
) -> float:
    """Return capacity available to current and future flow."""
    if capacity_snapshot is not None:
        return float(capacity_snapshot.bookable_capacity_for(arc_id))

    return float(
        state.residual_transport_capacity(
            instance,
            arc_id,
        )
    )


def _future_transport_arc_ids(
    instance: ExperimentInstance,
    candidate: FutureDemandCandidate,
) -> tuple[str, ...]:
    """Return transport arcs in one future network."""
    return tuple(
        arc_id
        for arc_id in candidate.network_index.feasible_arc_ids
        if instance.arc_by_id(arc_id).is_transport
    )


def build_dca_rm_model(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    future_set: FutureDemandSet,
    *,
    value_interpretation: FutureValueInterpretation,
    capacity_snapshot: TransportCapacitySnapshot | None = None,
) -> DcaRmModelArtifacts:
    """Build the current-plus-future DCA-RM programme."""
    _validate_inputs(
        instance,
        state,
        event,
        future_set,
        value_interpretation,
        capacity_snapshot,
    )

    demand = event.demand
    current_index = instance.network_index_for(event.demand_id)

    model = Model(
        name=_solver_name(
            "dca_rm",
            event.sequence_number,
            event.demand_id,
            value_interpretation.value,
        ),
        log_output=instance.config.solver.log_output,
    )

    model.parameters.timelimit = instance.config.solver.time_limit_seconds
    model.parameters.mip.tolerances.mipgap = instance.config.solver.relative_mip_gap

    acceptance_variable = _create_acceptance_variable(
        model,
        demand_id=demand.demand_id,
        category=demand.category,
    )

    current_flow_variables: dict[str, Any] = {}

    for number, arc_id in enumerate(current_index.all_flow_arc_ids):
        current_flow_variables[arc_id] = model.continuous_var(
            lb=0.0,
            name=_solver_name(
                "current_v",
                demand.demand_id,
                number,
                arc_id,
            ),
        )

    selector_variables: dict[tuple[str, int], Any] = {}
    protected_volume_variables: dict[str, Any] = {}
    future_flow_variables: dict[
        tuple[str, str],
        Any,
    ] = {}
    future_value_coefficients: dict[
        tuple[str, int],
        float,
    ] = {}

    for candidate in future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id

        protected_volume_variables[forecast_id] = model.integer_var(
            lb=0,
            ub=forecast.maximum_volume,
            name=_solver_name(
                "maxvol",
                forecast_id,
            ),
        )

        for level in forecast.positive_protection_levels:
            selector_variables[
                (
                    forecast_id,
                    level,
                )
            ] = model.binary_var(
                name=_solver_name(
                    "y",
                    forecast_id,
                    level,
                )
            )

            future_value_coefficients[
                (
                    forecast_id,
                    level,
                )
            ] = float(
                forecast.protected_expected_revenue(
                    level,
                    interpretation=value_interpretation,
                )
            )

        for number, arc_id in enumerate(candidate.network_index.all_flow_arc_ids):
            future_flow_variables[
                (
                    forecast_id,
                    arc_id,
                )
            ] = model.continuous_var(
                lb=0.0,
                name=_solver_name(
                    "future_v",
                    forecast_id,
                    number,
                    arc_id,
                ),
            )

    objective_terms: list[Any] = [demand.maximum_revenue * acceptance_variable]

    objective_terms.extend(
        coefficient * selector_variables[(forecast_id, level)]
        for (
            forecast_id,
            level,
        ), coefficient in sorted(future_value_coefficients.items())
    )

    model.maximize(model.sum(objective_terms))

    current_flow_balance_constraints: dict[
        object,
        Any,
    ] = {}

    for node_index in current_index.node_flow_indexes:
        node = node_index.node

        outgoing = model.sum(
            current_flow_variables[arc_id] for arc_id in (current_index.outgoing_flow_arc_ids(node))
        )
        incoming = model.sum(
            current_flow_variables[arc_id] for arc_id in (current_index.incoming_flow_arc_ids(node))
        )

        required = demand.volume * acceptance_variable if node == current_index.source else 0.0

        current_flow_balance_constraints[node] = model.add_constraint(
            outgoing - incoming == required,
            ctname=_solver_name(
                "current_balance",
                demand.demand_id,
                node[0],
                node[1],
            ),
        )

    current_sink_balance_constraint = model.add_constraint(
        model.sum(current_flow_variables[arc_id] for arc_id in current_index.sink_arc_ids)
        == demand.volume * acceptance_variable,
        ctname=_solver_name(
            "current_sink",
            demand.demand_id,
        ),
    )

    selector_constraints: dict[str, Any] = {}
    protected_volume_constraints: dict[str, Any] = {}
    future_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ] = {}
    future_sink_balance_constraints: dict[str, Any] = {}

    for candidate in future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id
        network = candidate.network_index

        selectors = [
            selector_variables[(forecast_id, level)]
            for level in forecast.positive_protection_levels
        ]

        selector_constraints[forecast_id] = model.add_constraint(
            model.sum(selectors) <= 1,
            ctname=_solver_name(
                "selector_exclusivity",
                forecast_id,
            ),
        )

        protected_volume_constraints[forecast_id] = model.add_constraint(
            protected_volume_variables[forecast_id]
            == model.sum(
                level
                * selector_variables[
                    (
                        forecast_id,
                        level,
                    )
                ]
                for level in (forecast.positive_protection_levels)
            ),
            ctname=_solver_name(
                "maxvol_link",
                forecast_id,
            ),
        )

        for node_index in network.node_flow_indexes:
            node = node_index.node

            outgoing = model.sum(
                future_flow_variables[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in (network.outgoing_flow_arc_ids(node))
            )
            incoming = model.sum(
                future_flow_variables[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in (network.incoming_flow_arc_ids(node))
            )

            required = protected_volume_variables[forecast_id] if node == network.source else 0.0

            future_flow_balance_constraints[
                (
                    forecast_id,
                    node,
                )
            ] = model.add_constraint(
                outgoing - incoming == required,
                ctname=_solver_name(
                    "future_balance",
                    forecast_id,
                    node[0],
                    node[1],
                ),
            )

        future_sink_balance_constraints[forecast_id] = model.add_constraint(
            model.sum(
                future_flow_variables[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in network.sink_arc_ids
            )
            == protected_volume_variables[forecast_id],
            ctname=_solver_name(
                "future_sink",
                forecast_id,
            ),
        )

    capacity_arc_ids: set[str] = {
        arc_id
        for arc_id in current_index.feasible_arc_ids
        if instance.arc_by_id(arc_id).is_transport
    }

    for candidate in future_set.candidates:
        capacity_arc_ids.update(
            _future_transport_arc_ids(
                instance,
                candidate,
            )
        )

    capacity_constraints: dict[str, Any] = {}
    available_capacities: dict[str, float] = {}

    for arc_id in sorted(capacity_arc_ids):
        relevant_variables: list[Any] = []

        if arc_id in current_index.feasible_arc_ids:
            relevant_variables.append(current_flow_variables[arc_id])

        for candidate in future_set.candidates:
            if arc_id not in candidate.network_index.feasible_arc_ids:
                continue

            relevant_variables.append(
                future_flow_variables[
                    (
                        candidate.forecast_id,
                        arc_id,
                    )
                ]
            )

        available_capacity = _available_capacity(
            instance,
            state,
            arc_id,
            capacity_snapshot,
        )

        available_capacities[arc_id] = available_capacity

        capacity_constraints[arc_id] = model.add_constraint(
            model.sum(relevant_variables) <= available_capacity,
            ctname=_solver_name(
                "shared_capacity",
                arc_id,
            ),
        )

    return DcaRmModelArtifacts(
        instance=instance,
        state=state,
        event=event,
        future_set=future_set,
        value_interpretation=value_interpretation,
        capacity_snapshot=capacity_snapshot,
        current_network_index=current_index,
        model=model,
        acceptance_variable=acceptance_variable,
        current_flow_variables=current_flow_variables,
        selector_variables=selector_variables,
        protected_volume_variables=(protected_volume_variables),
        future_flow_variables=future_flow_variables,
        current_flow_balance_constraints=(current_flow_balance_constraints),
        current_sink_balance_constraint=(current_sink_balance_constraint),
        selector_constraints=selector_constraints,
        protected_volume_constraints=(protected_volume_constraints),
        future_flow_balance_constraints=(future_flow_balance_constraints),
        future_sink_balance_constraints=(future_sink_balance_constraints),
        capacity_constraints=capacity_constraints,
        available_capacities=available_capacities,
        future_value_coefficients=(future_value_coefficients),
    )


def solve_dca_rm_model(
    artifacts: DcaRmModelArtifacts,
) -> DcaRmSolution:
    """Solve and extract one DCA-RM decision."""
    if not isinstance(
        artifacts,
        DcaRmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRmModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=(artifacts.instance.config.solver.log_output))
    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return DcaRmSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            value_interpretation=(artifacts.value_interpretation),
            is_solved=False,
            solve_status=solve_status,
            objective_value=None,
            acceptance_fraction=None,
            current_revenue=None,
            future_expected_revenue=None,
            current_flows=(),
            selectors=(),
            protections=(),
            future_flows=(),
        )

    acceptance = float(raw_solution.get_value(artifacts.acceptance_variable))

    current_flows = tuple(
        DcaRmCurrentFlowResult(
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    selectors = tuple(
        FutureSelectorResult(
            forecast_id=forecast_id,
            protection_level=level,
            selected_value=float(raw_solution.get_value(variable)),
        )
        for (
            forecast_id,
            level,
        ), variable in sorted(artifacts.selector_variables.items())
    )

    protections: list[FutureProtectionResult] = []

    for candidate in artifacts.future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id

        protected_volume = float(
            raw_solution.get_value(artifacts.protected_volume_variables[forecast_id])
        )
        selected_level = int(round(protected_volume))

        protections.append(
            FutureProtectionResult(
                forecast_id=forecast_id,
                protection_level=selected_level,
                protected_volume=protected_volume,
                credited_expected_volume=float(
                    forecast.protected_expected_volume(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
                credited_expected_revenue=float(
                    forecast.protected_expected_revenue(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
            )
        )

    future_flows = tuple(
        FutureTentativeFlowResult(
            forecast_id=forecast_id,
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for (
            forecast_id,
            arc_id,
        ), variable in sorted(artifacts.future_flow_variables.items())
    )

    current_revenue = artifacts.event.demand.maximum_revenue * acceptance
    future_expected_revenue = float(sum(result.credited_expected_revenue for result in protections))

    return DcaRmSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        value_interpretation=(artifacts.value_interpretation),
        is_solved=True,
        solve_status=solve_status,
        objective_value=float(raw_solution.objective_value),
        acceptance_fraction=acceptance,
        current_revenue=float(current_revenue),
        future_expected_revenue=(future_expected_revenue),
        current_flows=current_flows,
        selectors=selectors,
        protections=tuple(protections),
        future_flows=future_flows,
    )


def validate_dca_rm_solution(
    artifacts: DcaRmModelArtifacts,
    solution: DcaRmSolution,
    *,
    tolerance: float = DCA_RM_TOLERANCE,
) -> DcaRmValidationReport:
    """Independently validate one solved DCA-RM solution."""
    if not isinstance(
        artifacts,
        DcaRmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRmModelArtifacts.")

    if not isinstance(solution, DcaRmSolution):
        raise TypeError("solution must be a DcaRmSolution.")

    if (
        not solution.is_solved
        or solution.objective_value is None
        or solution.acceptance_fraction is None
    ):
        raise ValueError("Only a solved DCA-RM solution can be validated.")

    validated_tolerance = _validate_tolerance(tolerance)
    violations: list[str] = []

    acceptance = float(solution.acceptance_fraction)
    demand = artifacts.event.demand

    if demand.category is CustomerCategory.REGULAR:
        acceptance_violation = abs(acceptance - 1.0)
    elif demand.category is CustomerCategory.PARTIALLY_SPOT:
        acceptance_violation = max(
            0.0,
            -acceptance,
            acceptance - 1.0,
        )
    else:
        acceptance_violation = min(
            abs(acceptance),
            abs(acceptance - 1.0),
        )

    if acceptance_violation > validated_tolerance:
        violations.append("Current acceptance violates its customer-category domain.")

    current_flow = {result.arc_id: float(result.volume) for result in solution.current_flows}
    future_flow = {
        (
            result.forecast_id,
            result.arc_id,
        ): float(result.volume)
        for result in solution.future_flows
    }
    selector = {
        (
            result.forecast_id,
            result.protection_level,
        ): float(result.selected_value)
        for result in solution.selectors
    }
    protection = {result.forecast_id: result for result in solution.protections}

    max_selector_binary_violation = 0.0
    max_selector_exclusivity_violation = 0.0
    max_protected_volume_violation = 0.0
    max_negative_flow_violation = 0.0
    max_flow_balance_violation = 0.0
    max_sink_balance_violation = 0.0
    max_capacity_violation = 0.0

    for value in selector.values():
        binary_violation = min(
            abs(value),
            abs(value - 1.0),
        )
        max_selector_binary_violation = max(
            max_selector_binary_violation,
            binary_violation,
        )

    for value in (
        *current_flow.values(),
        *future_flow.values(),
    ):
        max_negative_flow_violation = max(
            max_negative_flow_violation,
            max(0.0, -value),
        )

    current_index = artifacts.current_network_index

    for node_index in current_index.node_flow_indexes:
        node = node_index.node
        outgoing = sum(
            current_flow[arc_id] for arc_id in (current_index.outgoing_flow_arc_ids(node))
        )
        incoming = sum(
            current_flow[arc_id] for arc_id in (current_index.incoming_flow_arc_ids(node))
        )
        required = demand.volume * acceptance if node == current_index.source else 0.0

        max_flow_balance_violation = max(
            max_flow_balance_violation,
            abs(outgoing - incoming - required),
        )

    current_delivered = sum(current_flow[arc_id] for arc_id in current_index.sink_arc_ids)

    max_sink_balance_violation = max(
        max_sink_balance_violation,
        abs(current_delivered - demand.volume * acceptance),
    )

    for candidate in artifacts.future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id
        network = candidate.network_index
        result = protection[forecast_id]

        selector_sum = sum(
            selector[(forecast_id, level)] for level in forecast.positive_protection_levels
        )

        max_selector_exclusivity_violation = max(
            max_selector_exclusivity_violation,
            max(0.0, selector_sum - 1.0),
        )

        linked_volume = sum(
            level * selector[(forecast_id, level)] for level in forecast.positive_protection_levels
        )

        max_protected_volume_violation = max(
            max_protected_volume_violation,
            abs(result.protected_volume - linked_volume),
        )

        for node_index in network.node_flow_indexes:
            node = node_index.node
            outgoing = sum(
                future_flow[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in (network.outgoing_flow_arc_ids(node))
            )
            incoming = sum(
                future_flow[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in (network.incoming_flow_arc_ids(node))
            )
            required = result.protected_volume if node == network.source else 0.0

            max_flow_balance_violation = max(
                max_flow_balance_violation,
                abs(outgoing - incoming - required),
            )

        delivered = sum(
            future_flow[
                (
                    forecast_id,
                    arc_id,
                )
            ]
            for arc_id in network.sink_arc_ids
        )

        max_sink_balance_violation = max(
            max_sink_balance_violation,
            abs(delivered - result.protected_volume),
        )

    for arc_id, available_capacity in artifacts.available_capacities.items():
        used = current_flow.get(arc_id, 0.0)

        used += sum(
            future_flow.get(
                (
                    candidate.forecast_id,
                    arc_id,
                ),
                0.0,
            )
            for candidate in artifacts.future_set.candidates
        )

        max_capacity_violation = max(
            max_capacity_violation,
            max(0.0, used - available_capacity),
        )

    recomputed_objective = float(
        demand.maximum_revenue * acceptance
        + sum(result.credited_expected_revenue for result in solution.protections)
    )
    reported_objective = float(solution.objective_value)
    objective_violation = abs(recomputed_objective - reported_objective)

    metrics = (
        acceptance_violation,
        max_selector_binary_violation,
        max_selector_exclusivity_violation,
        max_protected_volume_violation,
        max_negative_flow_violation,
        max_flow_balance_violation,
        max_sink_balance_violation,
        max_capacity_violation,
        objective_violation,
    )

    metric_names = (
        "acceptance",
        "selector binary",
        "selector exclusivity",
        "protected volume",
        "negative flow",
        "flow balance",
        "sink balance",
        "capacity",
        "objective",
    )

    for name, value in zip(
        metric_names,
        metrics,
        strict=True,
    ):
        if value > validated_tolerance:
            violations.append(f"{name} violation: {value}.")

    return DcaRmValidationReport(
        is_valid=not violations,
        tolerance=validated_tolerance,
        recomputed_objective=recomputed_objective,
        reported_objective=reported_objective,
        max_acceptance_violation=(acceptance_violation),
        max_selector_binary_violation=(max_selector_binary_violation),
        max_selector_exclusivity_violation=(max_selector_exclusivity_violation),
        max_protected_volume_violation=(max_protected_volume_violation),
        max_negative_flow_violation=(max_negative_flow_violation),
        max_flow_balance_violation=(max_flow_balance_violation),
        max_sink_balance_violation=(max_sink_balance_violation),
        max_capacity_violation=(max_capacity_violation),
        objective_violation=objective_violation,
        violations=tuple(violations),
    )
