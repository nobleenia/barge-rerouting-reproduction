"""Combined rerouting and future-demand revenue management."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any, cast

from barge_rerouting.domain import (
    CustomerCategory,
    FutureValueInterpretation,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.dca_rm import (
    FutureProtectionResult,
    FutureSelectorResult,
    FutureTentativeFlowResult,
)
from barge_rerouting.rerouting.capacity import (
    ReroutingCapacitySnapshot,
)
from barge_rerouting.rerouting.network import (
    FragmentNetworkIndex,
    FragmentNetworkSnapshot,
)
from barge_rerouting.rerouting.optimization import (
    CurrentDemandFlowResult,
    DcaRerouteModelArtifacts,
    FragmentFlowResult,
    build_dca_reroute_model,
)
from barge_rerouting.revenue_management import (
    FutureDemandCandidate,
    FutureDemandSet,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    RollingBookingState,
)

DCA_RRM_TOLERANCE = 1e-6


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


def _future_transport_arc_ids(
    instance: ExperimentInstance,
    candidate: FutureDemandCandidate,
) -> tuple[str, ...]:
    """Return transport arcs used by one future commodity."""
    return tuple(
        arc_id
        for arc_id in candidate.network_index.feasible_arc_ids
        if instance.arc_by_id(arc_id).is_transport
    )


def _validate_future_inputs(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    capacity_snapshot: ReroutingCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
    future_set: FutureDemandSet,
    value_interpretation: FutureValueInterpretation,
) -> None:
    """Validate the DCA-RRM-specific inputs."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(
        capacity_snapshot,
        ReroutingCapacitySnapshot,
    ):
        raise TypeError("capacity_snapshot must be a ReroutingCapacitySnapshot.")

    if not isinstance(
        fragment_networks,
        FragmentNetworkSnapshot,
    ):
        raise TypeError("fragment_networks must be a FragmentNetworkSnapshot.")

    if not isinstance(future_set, FutureDemandSet):
        raise TypeError("future_set must be a FutureDemandSet.")

    if not isinstance(
        value_interpretation,
        FutureValueInterpretation,
    ):
        raise TypeError("value_interpretation must be a FutureValueInterpretation.")

    if future_set.current_event != event:
        raise ValueError("The future-demand set must belong to the current booking event.")

    available_arc_ids = set(capacity_snapshot.available_arc_ids)

    for candidate in future_set.candidates:
        unavailable_arc_ids = tuple(
            sorted(
                set(
                    _future_transport_arc_ids(
                        instance,
                        candidate,
                    )
                ).difference(available_arc_ids)
            )
        )

        if unavailable_arc_ids:
            raise ValueError(
                "A future-demand network contains "
                "non-bookable transport arcs: "
                f"{unavailable_arc_ids}."
            )


@dataclass(frozen=True, slots=True)
class DcaRrmModelArtifacts:
    """DOcplex objects for one combined DCA-RRM decision."""

    base_artifacts: DcaRerouteModelArtifacts
    future_set: FutureDemandSet
    value_interpretation: FutureValueInterpretation
    selector_variables: dict[tuple[str, int], Any]
    protected_volume_variables: dict[str, Any]
    future_flow_variables: dict[tuple[str, str], Any]
    selector_constraints: dict[str, Any]
    protected_volume_constraints: dict[str, Any]
    future_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ]
    future_sink_balance_constraints: dict[str, Any]
    combined_capacity_constraints: dict[str, Any]
    available_capacities: dict[str, float]
    future_value_coefficients: dict[
        tuple[str, int],
        float,
    ]

    @property
    def instance(self) -> ExperimentInstance:
        """Return the experiment instance."""
        return self.base_artifacts.instance

    @property
    def state(self) -> RollingBookingState:
        """Return the persistent state before solving."""
        return self.base_artifacts.state

    @property
    def event(self) -> BookingDecisionEvent:
        """Return the current booking event."""
        return self.base_artifacts.event

    @property
    def model(self) -> Any:
        """Return the combined DOcplex model."""
        return self.base_artifacts.model

    @property
    def capacity_snapshot(
        self,
    ) -> ReroutingCapacitySnapshot:
        """Return released rerouting capacity."""
        return self.base_artifacts.capacity_snapshot

    @property
    def fragment_networks(
        self,
    ) -> FragmentNetworkSnapshot:
        """Return accepted-fragment networks."""
        return self.base_artifacts.fragment_networks

    @property
    def acceptance_variable(self) -> Any:
        """Return the current acceptance variable."""
        return self.base_artifacts.acceptance_variable

    @property
    def current_flow_variables(self) -> dict[str, Any]:
        """Return current-demand flow variables."""
        return cast(
            dict[str, Any],
            self.base_artifacts.current_flow_variables,
        )

    @property
    def fragment_flow_variables(
        self,
    ) -> dict[tuple[str, str], Any]:
        """Return accepted-fragment flow variables."""
        return cast(
            dict[tuple[str, str], Any],
            self.base_artifacts.fragment_flow_variables,
        )

    @property
    def fragment_count(self) -> int:
        """Return the number of mandatory fragments."""
        return cast(
            int,
            self.base_artifacts.fragment_count,
        )

    @property
    def forecast_count(self) -> int:
        """Return the number of future commodities."""
        return len(self.future_set.candidates)

    @property
    def current_flow_variable_count(self) -> int:
        """Return current-demand flow-variable count."""
        return len(self.current_flow_variables)

    @property
    def fragment_flow_variable_count(self) -> int:
        """Return accepted-fragment flow-variable count."""
        return len(self.fragment_flow_variables)

    @property
    def future_flow_variable_count(self) -> int:
        """Return tentative future-flow count."""
        return len(self.future_flow_variables)

    @property
    def selector_variable_count(self) -> int:
        """Return future binary-selector count."""
        return len(self.selector_variables)


@dataclass(frozen=True, slots=True)
class DcaRrmSolution:
    """Extracted solution of one combined DCA-RRM model."""

    event_id: str
    demand_id: str
    value_interpretation: FutureValueInterpretation
    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptance_fraction: float | None
    current_revenue: float | None
    future_expected_revenue: float | None
    current_flows: tuple[CurrentDemandFlowResult, ...]
    fragment_flows: tuple[FragmentFlowResult, ...]
    selectors: tuple[FutureSelectorResult, ...]
    protections: tuple[FutureProtectionResult, ...]
    future_flows: tuple[FutureTentativeFlowResult, ...]

    def current_flow_on(
        self,
        arc_id: str,
    ) -> float:
        """Return current-demand flow on one arc."""
        for result in self.current_flows:
            if result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown current-demand arc: {arc_id}")

    def fragment_flow_on(
        self,
        fragment_id: str,
        arc_id: str,
    ) -> float:
        """Return one accepted fragment's flow."""
        for result in self.fragment_flows:
            if result.fragment_id == fragment_id and result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown fragment-arc combination: {fragment_id}, {arc_id}")

    def fragment_delivered_volume(
        self,
        index: FragmentNetworkIndex,
    ) -> float:
        """Return volume entering one fragment sink."""
        return float(
            sum(
                self.fragment_flow_on(
                    index.fragment_id,
                    arc_id,
                )
                for arc_id in index.sink_arc_ids
            )
        )

    def selector_value(
        self,
        forecast_id: str,
        protection_level: int,
    ) -> float:
        """Return one future selector value."""
        for result in self.selectors:
            if result.forecast_id == forecast_id and result.protection_level == protection_level:
                return float(result.selected_value)

        raise KeyError(f"Unknown future selector: {forecast_id}, {protection_level}")

    def protection_for(
        self,
        forecast_id: str,
    ) -> FutureProtectionResult:
        """Return one future protection result."""
        for result in self.protections:
            if result.forecast_id == forecast_id:
                return result

        raise KeyError(f"Unknown future forecast: {forecast_id}")

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


def build_dca_rrm_model(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    capacity_snapshot: ReroutingCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
    future_set: FutureDemandSet,
    *,
    value_interpretation: FutureValueInterpretation,
) -> DcaRrmModelArtifacts:
    """Build the combined past-current-future model."""
    _validate_future_inputs(
        instance,
        state,
        event,
        capacity_snapshot,
        fragment_networks,
        future_set,
        value_interpretation,
    )

    base_artifacts = build_dca_reroute_model(
        instance,
        state,
        event,
        capacity_snapshot,
        fragment_networks,
    )
    model = base_artifacts.model

    selector_variables: dict[
        tuple[str, int],
        Any,
    ] = {}
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
                "rrm_maxvol",
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
                    "rrm_y",
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
                    "rrm_future_v",
                    forecast_id,
                    number,
                    arc_id,
                ),
            )

    objective_terms: list[Any] = [event.demand.maximum_revenue * base_artifacts.acceptance_variable]

    objective_terms.extend(
        coefficient
        * selector_variables[
            (
                forecast_id,
                level,
            )
        ]
        for (
            forecast_id,
            level,
        ), coefficient in sorted(future_value_coefficients.items())
    )

    model.maximize(model.sum(objective_terms))

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

        selector_constraints[forecast_id] = model.add_constraint(
            model.sum(
                selector_variables[
                    (
                        forecast_id,
                        level,
                    )
                ]
                for level in (forecast.positive_protection_levels)
            )
            <= 1,
            ctname=_solver_name(
                "rrm_selector_exclusivity",
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
                "rrm_maxvol_link",
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
                    "rrm_future_balance",
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
                "rrm_future_sink",
                forecast_id,
            ),
        )

    combined_capacity_constraints: dict[str, Any] = {}
    available_capacities = dict(base_artifacts.available_capacities)

    future_transport_arc_ids: set[str] = set()

    for candidate in future_set.candidates:
        future_transport_arc_ids.update(
            _future_transport_arc_ids(
                instance,
                candidate,
            )
        )

    for arc_id in sorted(future_transport_arc_ids):
        relevant_variables: list[Any] = []

        if arc_id in base_artifacts.current_network_index.feasible_arc_ids:
            relevant_variables.append(base_artifacts.current_flow_variables[arc_id])

        for index in fragment_networks.indexes:
            if arc_id not in index.feasible_arc_ids:
                continue

            relevant_variables.append(
                base_artifacts.fragment_flow_variables[
                    (
                        index.fragment_id,
                        arc_id,
                    )
                ]
            )

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

        available_capacity = float(capacity_snapshot.available_capacity_for(arc_id))
        available_capacities[arc_id] = available_capacity

        combined_capacity_constraints[arc_id] = model.add_constraint(
            model.sum(relevant_variables) <= available_capacity,
            ctname=_solver_name(
                "rrm_shared_capacity",
                arc_id,
            ),
        )

    return DcaRrmModelArtifacts(
        base_artifacts=base_artifacts,
        future_set=future_set,
        value_interpretation=value_interpretation,
        selector_variables=selector_variables,
        protected_volume_variables=(protected_volume_variables),
        future_flow_variables=future_flow_variables,
        selector_constraints=selector_constraints,
        protected_volume_constraints=(protected_volume_constraints),
        future_flow_balance_constraints=(future_flow_balance_constraints),
        future_sink_balance_constraints=(future_sink_balance_constraints),
        combined_capacity_constraints=(combined_capacity_constraints),
        available_capacities=available_capacities,
        future_value_coefficients=(future_value_coefficients),
    )


def solve_dca_rrm_model(
    artifacts: DcaRrmModelArtifacts,
) -> DcaRrmSolution:
    """Solve and extract one combined DCA-RRM decision."""
    if not isinstance(
        artifacts,
        DcaRrmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRrmModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=(artifacts.instance.config.solver.log_output))
    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return DcaRrmSolution(
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
            fragment_flows=(),
            selectors=(),
            protections=(),
            future_flows=(),
        )

    acceptance = float(raw_solution.get_value(artifacts.acceptance_variable))

    current_flows = tuple(
        CurrentDemandFlowResult(
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    fragment_flows = tuple(
        FragmentFlowResult(
            fragment_id=fragment_id,
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for (
            fragment_id,
            arc_id,
        ), variable in sorted(artifacts.fragment_flow_variables.items())
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

    return DcaRrmSolution(
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
        fragment_flows=fragment_flows,
        selectors=selectors,
        protections=tuple(protections),
        future_flows=future_flows,
    )


@dataclass(frozen=True, slots=True)
class DcaRrmValidationReport:
    """Independent numerical validation of DCA-RRM."""

    is_valid: bool
    tolerance: float
    recomputed_objective: float
    reported_objective: float
    max_acceptance_violation: float
    max_selector_binary_violation: float
    max_selector_exclusivity_violation: float
    max_protected_volume_violation: float
    max_protection_value_violation: float
    max_negative_flow_violation: float
    max_current_flow_balance_violation: float
    max_fragment_flow_balance_violation: float
    max_future_flow_balance_violation: float
    max_sink_balance_violation: float
    max_capacity_violation: float
    current_revenue_violation: float
    future_revenue_violation: float
    objective_violation: float
    violations: tuple[str, ...]


def _validate_solution_indexes(
    artifacts: DcaRrmModelArtifacts,
    solution: DcaRrmSolution,
) -> None:
    """Validate exact correspondence with model variables."""
    current_arc_ids = tuple(result.arc_id for result in solution.current_flows)

    if len(set(current_arc_ids)) != len(current_arc_ids):
        raise ValueError("Current-flow solution arc IDs must be unique.")

    if set(current_arc_ids) != set(artifacts.current_flow_variables):
        raise ValueError("Current-flow results do not match model variables.")

    fragment_keys = tuple(
        (
            result.fragment_id,
            result.arc_id,
        )
        for result in solution.fragment_flows
    )

    if len(set(fragment_keys)) != len(fragment_keys):
        raise ValueError("Fragment-flow solution keys must be unique.")

    if set(fragment_keys) != set(artifacts.fragment_flow_variables):
        raise ValueError("Fragment-flow results do not match model variables.")

    selector_keys = tuple(
        (
            result.forecast_id,
            result.protection_level,
        )
        for result in solution.selectors
    )

    if len(set(selector_keys)) != len(selector_keys):
        raise ValueError("Future-selector result keys must be unique.")

    if set(selector_keys) != set(artifacts.selector_variables):
        raise ValueError("Future-selector results do not match model variables.")

    future_flow_keys = tuple(
        (
            result.forecast_id,
            result.arc_id,
        )
        for result in solution.future_flows
    )

    if len(set(future_flow_keys)) != len(future_flow_keys):
        raise ValueError("Future-flow result keys must be unique.")

    if set(future_flow_keys) != set(artifacts.future_flow_variables):
        raise ValueError("Future-flow results do not match model variables.")

    protection_ids = tuple(result.forecast_id for result in solution.protections)
    expected_protection_ids = tuple(
        candidate.forecast_id for candidate in artifacts.future_set.candidates
    )

    if len(set(protection_ids)) != len(protection_ids):
        raise ValueError("Future-protection IDs must be unique.")

    if set(protection_ids) != set(expected_protection_ids):
        raise ValueError("Future-protection results do not match forecasts.")


def validate_dca_rrm_solution(
    artifacts: DcaRrmModelArtifacts,
    solution: DcaRrmSolution,
    *,
    tolerance: float = DCA_RRM_TOLERANCE,
) -> DcaRrmValidationReport:
    """Independently validate one solved DCA-RRM solution."""
    if not isinstance(
        artifacts,
        DcaRrmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRrmModelArtifacts.")

    if not isinstance(solution, DcaRrmSolution):
        raise TypeError("solution must be a DcaRrmSolution.")

    if (
        not solution.is_solved
        or solution.objective_value is None
        or solution.acceptance_fraction is None
        or solution.current_revenue is None
        or solution.future_expected_revenue is None
    ):
        raise ValueError("Only a complete solved DCA-RRM solution can be validated.")

    validated_tolerance = _validate_tolerance(tolerance)

    if solution.event_id != artifacts.event.event_id:
        raise ValueError("Solution event does not match model artifacts.")

    if solution.demand_id != artifacts.event.demand_id:
        raise ValueError("Solution demand does not match model artifacts.")

    if solution.value_interpretation is not artifacts.value_interpretation:
        raise ValueError("Solution value interpretation does not match model artifacts.")

    _validate_solution_indexes(
        artifacts,
        solution,
    )

    violations: list[str] = []

    demand = artifacts.event.demand
    acceptance = float(solution.acceptance_fraction)

    if demand.category is CustomerCategory.REGULAR:
        acceptance_violation = abs(acceptance - 1.0)
    elif demand.category is CustomerCategory.PARTIALLY_SPOT:
        acceptance_violation = max(
            0.0,
            -acceptance,
            acceptance - 1.0,
        )
    elif demand.category is CustomerCategory.FULLY_SPOT:
        acceptance_violation = min(
            abs(acceptance),
            abs(acceptance - 1.0),
        )
    else:
        raise ValueError("Unsupported current customer category.")

    if acceptance_violation > validated_tolerance:
        violations.append("Current acceptance violates its customer-category domain.")

    current_flow = {result.arc_id: float(result.volume) for result in solution.current_flows}
    fragment_flow = {
        (
            result.fragment_id,
            result.arc_id,
        ): float(result.volume)
        for result in solution.fragment_flows
    }
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
    max_protection_value_violation = 0.0
    max_negative_flow_violation = 0.0
    max_current_flow_balance_violation = 0.0
    max_fragment_flow_balance_violation = 0.0
    max_future_flow_balance_violation = 0.0
    max_sink_balance_violation = 0.0
    max_capacity_violation = 0.0

    for value in selector.values():
        max_selector_binary_violation = max(
            max_selector_binary_violation,
            min(
                abs(value),
                abs(value - 1.0),
            ),
        )

    if max_selector_binary_violation > validated_tolerance:
        violations.append("At least one future selector is non-binary.")

    for candidate in artifacts.future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id

        selector_sum = float(
            sum(
                selector[
                    (
                        forecast_id,
                        level,
                    )
                ]
                for level in (forecast.positive_protection_levels)
            )
        )

        max_selector_exclusivity_violation = max(
            max_selector_exclusivity_violation,
            max(0.0, selector_sum - 1.0),
        )

        linked_protected_volume = float(
            sum(
                level
                * selector[
                    (
                        forecast_id,
                        level,
                    )
                ]
                for level in (forecast.positive_protection_levels)
            )
        )

        protection_result = protection[forecast_id]
        reported_protected_volume = float(protection_result.protected_volume)

        max_protected_volume_violation = max(
            max_protected_volume_violation,
            abs(reported_protected_volume - linked_protected_volume),
        )

        selected_level = int(round(reported_protected_volume))

        expected_credited_volume = float(
            forecast.protected_expected_volume(
                selected_level,
                interpretation=(artifacts.value_interpretation),
            )
        )
        expected_credited_revenue = float(
            forecast.protected_expected_revenue(
                selected_level,
                interpretation=(artifacts.value_interpretation),
            )
        )

        max_protection_value_violation = max(
            max_protection_value_violation,
            abs(float(protection_result.credited_expected_volume) - expected_credited_volume),
            abs(float(protection_result.credited_expected_revenue) - expected_credited_revenue),
            abs(float(protection_result.protection_level) - selected_level),
        )

    if max_selector_exclusivity_violation > validated_tolerance:
        violations.append("A future forecast selects more than one positive protection level.")

    if max_protected_volume_violation > validated_tolerance:
        violations.append("A protected future volume violates its selector linking equation.")

    if max_protection_value_violation > validated_tolerance:
        violations.append("A future protection result has an incorrect credited value.")

    for value in (
        *current_flow.values(),
        *fragment_flow.values(),
        *future_flow.values(),
    ):
        max_negative_flow_violation = max(
            max_negative_flow_violation,
            max(0.0, -value),
        )

    if max_negative_flow_violation > validated_tolerance:
        violations.append("At least one commodity flow is negative.")

    current_index = artifacts.base_artifacts.current_network_index
    accepted_volume = demand.volume * acceptance

    for node_index in current_index.node_flow_indexes:
        node = node_index.node

        outgoing = float(
            sum(current_flow[arc_id] for arc_id in (current_index.outgoing_flow_arc_ids(node)))
        )
        incoming = float(
            sum(current_flow[arc_id] for arc_id in (current_index.incoming_flow_arc_ids(node)))
        )
        required = accepted_volume if node == current_index.source else 0.0

        max_current_flow_balance_violation = max(
            max_current_flow_balance_violation,
            abs(outgoing - incoming - required),
        )

    current_sink_volume = float(sum(current_flow[arc_id] for arc_id in current_index.sink_arc_ids))

    max_sink_balance_violation = max(
        max_sink_balance_violation,
        abs(current_sink_volume - accepted_volume),
    )

    for index in artifacts.fragment_networks.indexes:
        fragment_id = index.fragment_id

        for node_index in index.node_flow_indexes:
            node = node_index.node

            outgoing = float(
                sum(
                    fragment_flow[
                        (
                            fragment_id,
                            arc_id,
                        )
                    ]
                    for arc_id in (index.outgoing_flow_arc_ids(node))
                )
            )
            incoming = float(
                sum(
                    fragment_flow[
                        (
                            fragment_id,
                            arc_id,
                        )
                    ]
                    for arc_id in (index.incoming_flow_arc_ids(node))
                )
            )
            required = index.volume if node == index.source else 0.0

            max_fragment_flow_balance_violation = max(
                max_fragment_flow_balance_violation,
                abs(outgoing - incoming - required),
            )

        fragment_sink_volume = float(
            sum(
                fragment_flow[
                    (
                        fragment_id,
                        arc_id,
                    )
                ]
                for arc_id in index.sink_arc_ids
            )
        )

        max_sink_balance_violation = max(
            max_sink_balance_violation,
            abs(fragment_sink_volume - index.volume),
        )

    for candidate in artifacts.future_set.candidates:
        forecast_id = candidate.forecast_id
        network = candidate.network_index
        protected_volume = float(protection[forecast_id].protected_volume)

        for node_index in network.node_flow_indexes:
            node = node_index.node

            outgoing = float(
                sum(
                    future_flow[
                        (
                            forecast_id,
                            arc_id,
                        )
                    ]
                    for arc_id in (network.outgoing_flow_arc_ids(node))
                )
            )
            incoming = float(
                sum(
                    future_flow[
                        (
                            forecast_id,
                            arc_id,
                        )
                    ]
                    for arc_id in (network.incoming_flow_arc_ids(node))
                )
            )
            required = protected_volume if node == network.source else 0.0

            max_future_flow_balance_violation = max(
                max_future_flow_balance_violation,
                abs(outgoing - incoming - required),
            )

        future_sink_volume = float(
            sum(
                future_flow[
                    (
                        forecast_id,
                        arc_id,
                    )
                ]
                for arc_id in network.sink_arc_ids
            )
        )

        max_sink_balance_violation = max(
            max_sink_balance_violation,
            abs(future_sink_volume - protected_volume),
        )

    if max_current_flow_balance_violation > validated_tolerance:
        violations.append("Current-demand flow conservation is violated.")

    if max_fragment_flow_balance_violation > validated_tolerance:
        violations.append("Accepted-fragment flow conservation is violated.")

    if max_future_flow_balance_violation > validated_tolerance:
        violations.append("Tentative future-flow conservation is violated.")

    if max_sink_balance_violation > validated_tolerance:
        violations.append("At least one commodity sink balance is violated.")

    for (
        arc_id,
        available_capacity,
    ) in artifacts.available_capacities.items():
        used_capacity = 0.0

        if arc_id in current_index.feasible_arc_ids:
            used_capacity += current_flow[arc_id]

        for index in artifacts.fragment_networks.indexes:
            if arc_id not in index.feasible_arc_ids:
                continue

            used_capacity += fragment_flow[
                (
                    index.fragment_id,
                    arc_id,
                )
            ]

        for candidate in artifacts.future_set.candidates:
            if arc_id not in candidate.network_index.feasible_arc_ids:
                continue

            used_capacity += future_flow[
                (
                    candidate.forecast_id,
                    arc_id,
                )
            ]

        max_capacity_violation = max(
            max_capacity_violation,
            max(
                0.0,
                used_capacity - float(available_capacity),
            ),
        )

    if max_capacity_violation > validated_tolerance:
        violations.append("Shared transport capacity is violated.")

    recomputed_current_revenue = float(demand.maximum_revenue * acceptance)
    recomputed_future_revenue = float(
        sum(
            coefficient
            * selector[
                (
                    forecast_id,
                    level,
                )
            ]
            for (
                forecast_id,
                level,
            ), coefficient in (artifacts.future_value_coefficients.items())
        )
    )
    recomputed_objective = float(recomputed_current_revenue + recomputed_future_revenue)

    current_revenue_violation = abs(float(solution.current_revenue) - recomputed_current_revenue)
    future_revenue_violation = abs(
        float(solution.future_expected_revenue) - recomputed_future_revenue
    )
    objective_violation = abs(float(solution.objective_value) - recomputed_objective)

    if current_revenue_violation > validated_tolerance:
        violations.append("Reported current revenue is incorrect.")

    if future_revenue_violation > validated_tolerance:
        violations.append("Reported expected future revenue is incorrect.")

    if objective_violation > validated_tolerance:
        violations.append("Reported DCA-RRM objective is incorrect.")

    return DcaRrmValidationReport(
        is_valid=not violations,
        tolerance=validated_tolerance,
        recomputed_objective=recomputed_objective,
        reported_objective=float(solution.objective_value),
        max_acceptance_violation=(acceptance_violation),
        max_selector_binary_violation=(max_selector_binary_violation),
        max_selector_exclusivity_violation=(max_selector_exclusivity_violation),
        max_protected_volume_violation=(max_protected_volume_violation),
        max_protection_value_violation=(max_protection_value_violation),
        max_negative_flow_violation=(max_negative_flow_violation),
        max_current_flow_balance_violation=(max_current_flow_balance_violation),
        max_fragment_flow_balance_violation=(max_fragment_flow_balance_violation),
        max_future_flow_balance_violation=(max_future_flow_balance_violation),
        max_sink_balance_violation=(max_sink_balance_violation),
        max_capacity_violation=(max_capacity_violation),
        current_revenue_violation=(current_revenue_violation),
        future_revenue_violation=(future_revenue_violation),
        objective_violation=objective_violation,
        violations=tuple(violations),
    )
