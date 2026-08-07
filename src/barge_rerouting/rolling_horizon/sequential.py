"""Sequential current-demand optimisation under prior commitments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
    PlannedArcFlow,
    validate_commitment_against_instance,
)
from barge_rerouting.rolling_horizon.state import RollingBookingState
from barge_rerouting.rolling_horizon.timeline import BookingDecisionEvent


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw_name = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw_name)


def _validate_tolerance(value: object) -> float:
    """Validate and return a strictly positive finite tolerance."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("tolerance must be a real number.")

    tolerance = float(value)

    if not isfinite(tolerance):
        raise ValueError("tolerance must be finite.")

    if tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")

    return tolerance


@dataclass(frozen=True, slots=True)
class SequentialBookingModelArtifacts:
    """One event-specific DOcplex booking model."""

    instance: ExperimentInstance
    state: RollingBookingState
    event: BookingDecisionEvent
    model: Any
    acceptance_variable: Any
    flow_variables: dict[str, Any]
    flow_balance_constraints: dict[object, Any]
    sink_balance_constraint: Any
    capacity_constraints: dict[str, Any]
    residual_capacities: dict[str, float]

    @property
    def flow_variable_count(self) -> int:
        """Return the number of current-demand flow variables."""
        return len(self.flow_variables)


@dataclass(frozen=True, slots=True)
class SequentialArcFlowResult:
    """Solved current-demand flow on one arc."""

    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class SequentialBookingSolution:
    """Extracted solution for one booking event."""

    event_id: str
    demand_id: str
    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptance_fraction: float | None
    flows: tuple[SequentialArcFlowResult, ...]

    def flow_on(self, arc_id: str) -> float:
        """Return solved current-demand flow on one arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for flow_result in self.flows:
            if flow_result.arc_id == normalised_arc_id:
                return float(flow_result.volume)

        raise KeyError(f"Arc {normalised_arc_id} is not present in this solution.")


def _create_acceptance_variable(
    model: Any,
    *,
    demand_id: str,
    category: CustomerCategory,
) -> Any:
    """Create the current demand's acceptance variable."""
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


def build_sequential_booking_model(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    *,
    capacity_snapshot: TransportCapacitySnapshot | None = None,
    residual_capacity_overrides: dict[str, float] | None = None,
) -> SequentialBookingModelArtifacts:
    """Build one myopic booking model using residual transport capacity."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another experiment instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The booking event must be the next unprocessed event.")

    if capacity_snapshot is not None:
        if not isinstance(
            capacity_snapshot,
            TransportCapacitySnapshot,
        ):
            raise TypeError("capacity_snapshot must be a TransportCapacitySnapshot or None.")

        if capacity_snapshot.instance_fingerprint != instance.demand_fingerprint:
            raise ValueError("The capacity snapshot belongs to another instance.")

        if capacity_snapshot.physical_time != event.decision_time:
            raise ValueError("The capacity snapshot time must equal the booking decision time.")

    if capacity_snapshot is not None and residual_capacity_overrides is not None:
        raise ValueError(
            "capacity_snapshot and residual_capacity_overrides are mutually exclusive."
        )

    normalised_capacity_overrides: dict[str, float] | None = None

    if residual_capacity_overrides is not None:
        if not isinstance(
            residual_capacity_overrides,
            dict,
        ):
            raise TypeError("residual_capacity_overrides must be a dictionary or None.")

        normalised_capacity_overrides = {}

        for raw_arc_id, raw_capacity in residual_capacity_overrides.items():
            if not isinstance(raw_arc_id, str):
                raise TypeError("Residual-capacity arc identifiers must be strings.")

            arc_id = raw_arc_id.strip()

            if not arc_id:
                raise ValueError("Residual-capacity arc identifiers must be non-empty.")

            arc = instance.arc_by_id(arc_id)

            if not arc.is_transport:
                raise ValueError("Residual-capacity overrides may contain only transport arcs.")

            if isinstance(raw_capacity, bool) or not isinstance(
                raw_capacity,
                (int, float),
            ):
                raise TypeError("Residual-capacity values must be real numbers.")

            residual_capacity = float(raw_capacity)

            if not isfinite(residual_capacity):
                raise ValueError("Residual-capacity values must be finite.")

            if residual_capacity < -COMMITMENT_TOLERANCE:
                raise ValueError("Residual-capacity values must be non-negative.")

            if arc.nominal_capacity is None:
                raise ValueError(f"Transport arc {arc_id} has no nominal capacity.")

            if residual_capacity - float(arc.nominal_capacity) > COMMITMENT_TOLERANCE:
                raise ValueError(f"Residual capacity cannot exceed nominal capacity on {arc_id}.")

            normalised_capacity_overrides[arc_id] = max(
                0.0,
                residual_capacity,
            )

    demand = instance.demand_by_id(event.demand_id)

    if demand != event.demand:
        raise ValueError("The booking event demand does not match the instance.")

    network_index = instance.network_index_for(event.demand_id)

    model = Model(
        name=_solver_name(
            "sequential_dca",
            event.sequence_number,
            event.demand_id,
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

    flow_variables: dict[str, Any] = {}

    for arc_number, arc_id in enumerate(network_index.all_flow_arc_ids):
        flow_variables[arc_id] = model.continuous_var(
            lb=0.0,
            name=_solver_name(
                "v",
                demand.demand_id,
                arc_number,
                arc_id,
            ),
        )

    model.maximize(demand.maximum_revenue * acceptance_variable)

    flow_balance_constraints: dict[object, Any] = {}

    for node_index in network_index.node_flow_indexes:
        node = node_index.node

        outgoing_flow = model.sum(
            flow_variables[arc_id] for arc_id in network_index.outgoing_flow_arc_ids(node)
        )
        incoming_flow = model.sum(
            flow_variables[arc_id] for arc_id in network_index.incoming_flow_arc_ids(node)
        )

        required_balance = (
            demand.volume * acceptance_variable if node == network_index.source else 0.0
        )

        flow_balance_constraints[node] = model.add_constraint(
            outgoing_flow - incoming_flow == required_balance,
            ctname=_solver_name(
                "flow_balance",
                demand.demand_id,
                node[0],
                node[1],
            ),
        )

    sink_balance_constraint = model.add_constraint(
        model.sum(flow_variables[arc_id] for arc_id in network_index.sink_arc_ids)
        == demand.volume * acceptance_variable,
        ctname=_solver_name(
            "sink_balance",
            demand.demand_id,
        ),
    )

    capacity_constraints: dict[str, Any] = {}
    residual_capacities: dict[str, float] = {}

    for arc_id in network_index.feasible_arc_ids:
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            continue

        if normalised_capacity_overrides is not None:
            if arc_id not in normalised_capacity_overrides:
                raise ValueError(f"Missing residual-capacity override for transport arc {arc_id}.")

            residual_capacity = float(normalised_capacity_overrides[arc_id])
        elif capacity_snapshot is not None:
            residual_capacity = float(capacity_snapshot.bookable_capacity_for(arc_id))
        else:
            residual_capacity = float(
                state.residual_transport_capacity(
                    instance,
                    arc_id,
                )
            )

        residual_capacities[arc_id] = residual_capacity

        capacity_constraints[arc_id] = model.add_constraint(
            flow_variables[arc_id] <= residual_capacity,
            ctname=_solver_name(
                "residual_capacity",
                arc_id,
            ),
        )

    return SequentialBookingModelArtifacts(
        instance=instance,
        state=state,
        event=event,
        model=model,
        acceptance_variable=acceptance_variable,
        flow_variables=flow_variables,
        flow_balance_constraints=flow_balance_constraints,
        sink_balance_constraint=sink_balance_constraint,
        capacity_constraints=capacity_constraints,
        residual_capacities=residual_capacities,
    )


def solve_sequential_booking_model(
    artifacts: SequentialBookingModelArtifacts,
) -> SequentialBookingSolution:
    """Solve and extract one sequential booking decision."""
    if not isinstance(artifacts, SequentialBookingModelArtifacts):
        raise TypeError("artifacts must be SequentialBookingModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=artifacts.instance.config.solver.log_output)
    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return SequentialBookingSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            is_solved=False,
            solve_status=solve_status,
            objective_value=None,
            acceptance_fraction=None,
            flows=(),
        )

    acceptance_fraction = float(raw_solution.get_value(artifacts.acceptance_variable))

    flows = tuple(
        SequentialArcFlowResult(
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for arc_id, variable in sorted(artifacts.flow_variables.items())
    )

    return SequentialBookingSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        is_solved=True,
        solve_status=solve_status,
        objective_value=float(raw_solution.objective_value),
        acceptance_fraction=acceptance_fraction,
        flows=flows,
    )


def commitment_from_sequential_solution(
    artifacts: SequentialBookingModelArtifacts,
    solution: SequentialBookingSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DemandCommitment | None:
    """Convert a solved sequential decision into a persistent commitment."""
    if not isinstance(artifacts, SequentialBookingModelArtifacts):
        raise TypeError("artifacts must be SequentialBookingModelArtifacts.")

    if not isinstance(solution, SequentialBookingSolution):
        raise TypeError("solution must be a SequentialBookingSolution.")

    validated_tolerance = _validate_tolerance(tolerance)

    if not solution.is_solved:
        raise ValueError("An unsolved booking model cannot create a commitment.")

    if solution.acceptance_fraction is None:
        raise ValueError("Solved booking decision has no acceptance value.")

    if solution.demand_id != artifacts.event.demand_id:
        raise ValueError("Solution demand does not match the booking event.")

    demand = artifacts.event.demand
    acceptance_fraction = float(solution.acceptance_fraction)

    if abs(acceptance_fraction) <= validated_tolerance:
        acceptance_fraction = 0.0
    elif abs(acceptance_fraction - 1.0) <= validated_tolerance:
        acceptance_fraction = 1.0

    acceptance_fraction = demand.normalize_acceptance_fraction(acceptance_fraction)

    expected_objective = demand.maximum_revenue * acceptance_fraction

    if solution.objective_value is None:
        raise ValueError("Solved decision has no objective value.")

    if abs(solution.objective_value - expected_objective) > validated_tolerance:
        raise ValueError("Sequential objective does not match the acceptance decision.")

    if acceptance_fraction <= validated_tolerance:
        if any(abs(flow_result.volume) > validated_tolerance for flow_result in solution.flows):
            raise ValueError("A rejected demand cannot retain positive flow.")

        return None

    planned_arc_flows = tuple(
        PlannedArcFlow(
            arc_id=flow_result.arc_id,
            volume=flow_result.volume,
        )
        for flow_result in solution.flows
        if flow_result.volume > validated_tolerance
    )

    commitment = DemandCommitment(
        decision_sequence=artifacts.event.sequence_number,
        decision_time=artifacts.event.decision_time,
        demand=demand,
        acceptance_fraction=acceptance_fraction,
        planned_arc_flows=planned_arc_flows,
    )

    report = validate_commitment_against_instance(
        artifacts.instance,
        commitment,
        tolerance=validated_tolerance,
    )

    if not report.is_valid:
        raise ValueError("Sequential commitment failed network validation.")

    for arc_id, residual_capacity in artifacts.residual_capacities.items():
        planned_volume = commitment.planned_volume_on(arc_id)

        if planned_volume - residual_capacity > validated_tolerance:
            raise ValueError(f"Commitment exceeds residual capacity on {arc_id}.")

    return commitment


def apply_sequential_booking_solution(
    artifacts: SequentialBookingModelArtifacts,
    solution: SequentialBookingSolution,
) -> RollingBookingState:
    """Persist a solved acceptance or rejection in a new booking state."""
    commitment = commitment_from_sequential_solution(
        artifacts,
        solution,
    )

    return artifacts.state.advance(
        artifacts.instance,
        event=artifacts.event,
        commitment=commitment,
    )
