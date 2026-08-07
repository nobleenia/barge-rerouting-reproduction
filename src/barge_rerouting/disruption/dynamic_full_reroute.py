"""Truck-enabled Full-Reroute model for dynamic service status."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.disruption.recovery_capacity import (
    RecoveryCapacitySnapshot,
)
from barge_rerouting.disruption.truck_recourse import (
    TruckAllocationResult,
)
from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import (
    DemandNetworkIndex,
    ExperimentInstance,
)
from barge_rerouting.rerouting.network import (
    FragmentNetworkSnapshot,
)
from barge_rerouting.rerouting.optimization import (
    CurrentDemandFlowResult,
    FragmentFlowResult,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    RollingBookingState,
)

DYNAMIC_FULL_REROUTE_TOLERANCE = 1e-6


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw)


def _positive_float(
    name: str,
    value: object,
) -> float:
    """Validate a strictly positive finite number."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric


def _create_acceptance_variable(
    model: Any,
    *,
    demand_id: str,
    category: CustomerCategory,
) -> Any:
    """Create the current request acceptance variable."""
    name = _solver_name("xi", demand_id)

    if category is CustomerCategory.REGULAR:
        return model.continuous_var(
            lb=1.0,
            ub=1.0,
            name=name,
        )

    if category is CustomerCategory.PARTIALLY_SPOT:
        return model.continuous_var(
            lb=0.0,
            ub=1.0,
            name=name,
        )

    if category is CustomerCategory.FULLY_SPOT:
        return model.binary_var(name=name)

    raise ValueError(f"Unsupported customer category: {category}")


def _normalise_penalties(
    event: BookingDecisionEvent,
    fragment_networks: FragmentNetworkSnapshot,
    values: Mapping[str, float],
) -> dict[str, float]:
    """Require one explicit truck penalty per affected demand."""
    if not isinstance(values, Mapping):
        raise TypeError("truck_penalty_per_teu_by_demand must be a mapping.")

    penalties: dict[str, float] = {}

    for raw_demand_id, raw_penalty in values.items():
        if not isinstance(raw_demand_id, str):
            raise TypeError("Truck-penalty demand identifiers must be strings.")

        demand_id = raw_demand_id.strip()

        if not demand_id:
            raise ValueError("Truck-penalty demand identifiers must be non-empty.")

        penalties[demand_id] = _positive_float(
            f"truck penalty for {demand_id}",
            raw_penalty,
        )

    expected = {
        event.demand_id,
        *(index.demand_id for index in fragment_networks.indexes),
    }

    if set(penalties) != expected:
        missing = tuple(sorted(expected.difference(penalties)))
        extra = tuple(sorted(set(penalties).difference(expected)))

        raise ValueError(
            "Truck penalties must cover exactly current "
            "and reroutable demands; "
            f"missing={missing}, extra={extra}."
        )

    return penalties


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteModelArtifacts:
    """DOcplex objects for one dynamic Full-Reroute booking."""

    instance: ExperimentInstance
    state: RollingBookingState
    event: BookingDecisionEvent
    recovery_capacity: RecoveryCapacitySnapshot
    fragment_networks: FragmentNetworkSnapshot
    current_network_index: DemandNetworkIndex
    truck_penalty_per_teu_by_demand: dict[str, float]
    allow_current_truck: bool
    model: Any
    acceptance_variable: Any
    current_flow_variables: dict[str, Any]
    current_truck_variable: Any
    fragment_flow_variables: dict[tuple[str, str], Any]
    fragment_truck_variables: dict[str, Any]
    current_flow_balance_constraints: dict[object, Any]
    current_sink_balance_constraint: Any
    current_truck_acceptance_constraint: Any
    fragment_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ]
    fragment_sink_balance_constraints: dict[str, Any]
    capacity_constraints: dict[str, Any]
    available_capacities: dict[str, float]


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteSolution:
    """Extracted dynamic Full-Reroute decision."""

    event_id: str
    demand_id: str
    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptance_fraction: float | None
    current_flows: tuple[CurrentDemandFlowResult, ...]
    current_truck_volume: float | None
    current_truck_penalty_per_teu: float
    fragment_flows: tuple[FragmentFlowResult, ...]
    fragment_truck_allocations: tuple[
        TruckAllocationResult,
        ...,
    ]

    def current_flow_on(
        self,
        arc_id: str,
    ) -> float:
        """Return current-demand barge flow on one arc."""
        for result in self.current_flows:
            if result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown current-demand arc: {arc_id}")

    def fragment_flow_on(
        self,
        fragment_id: str,
        arc_id: str,
    ) -> float:
        """Return one prior fragment's barge flow."""
        for result in self.fragment_flows:
            if result.fragment_id == fragment_id and result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown fragment-arc result: {fragment_id}, {arc_id}")

    def fragment_truck_volume_for(
        self,
        fragment_id: str,
    ) -> float:
        """Return truck allocation for one prior fragment."""
        for result in self.fragment_truck_allocations:
            if result.fragment_id == fragment_id:
                return float(result.volume)

        raise KeyError(f"Unknown fragment: {fragment_id}")

    @property
    def current_truck_penalty(self) -> float:
        """Return current-request truck penalty."""
        if self.current_truck_volume is None:
            return 0.0

        return float(self.current_truck_volume * self.current_truck_penalty_per_teu)

    @property
    def prior_truck_volume(self) -> float:
        """Return truck allocation across prior fragments."""
        return float(sum(allocation.volume for allocation in self.fragment_truck_allocations))

    @property
    def total_truck_volume(self) -> float:
        """Return total truck volume in this solve."""
        return float((self.current_truck_volume or 0.0) + self.prior_truck_volume)

    @property
    def total_truck_penalty(self) -> float:
        """Return all decision-dependent truck penalty."""
        return float(
            self.current_truck_penalty
            + sum(allocation.penalty_value for allocation in self.fragment_truck_allocations)
        )


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteValidationReport:
    """Independent residual checks for dynamic FR."""

    is_valid: bool
    max_flow_balance_violation: float
    max_delivery_balance_violation: float
    max_capacity_violation: float
    objective_violation: float
    violations: tuple[str, ...]


def _validate_inputs(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    recovery_capacity: RecoveryCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
) -> None:
    """Validate dynamic Full-Reroute inputs."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(
        recovery_capacity,
        RecoveryCapacitySnapshot,
    ):
        raise TypeError("recovery_capacity must be a RecoveryCapacitySnapshot.")

    if not isinstance(
        fragment_networks,
        FragmentNetworkSnapshot,
    ):
        raise TypeError("fragment_networks must be a FragmentNetworkSnapshot.")

    fingerprint = instance.demand_fingerprint

    if state.instance_fingerprint != fingerprint:
        raise ValueError("Booking state belongs to another instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("Booking event must be the next unprocessed event.")

    if recovery_capacity.instance_fingerprint != fingerprint:
        raise ValueError("Recovery capacity belongs to another instance.")

    if fragment_networks.instance_fingerprint != fingerprint:
        raise ValueError("Fragment networks belong to another instance.")

    if recovery_capacity.event_id != event.event_id:
        raise ValueError("Recovery capacity must use the current booking event identifier.")

    if fragment_networks.current_event_id != event.event_id:
        raise ValueError("Fragment networks must use the current booking event identifier.")

    if recovery_capacity.physical_time != event.decision_time:
        raise ValueError("Recovery capacity must use the booking time.")

    if fragment_networks.physical_time != event.decision_time:
        raise ValueError("Fragment networks must use the booking time.")

    if recovery_capacity.fixed_overload_arc_ids:
        raise ValueError(
            "Dynamic Full-Reroute cannot repair fixed "
            "reservations outside the released fragment set."
        )

    prior_ids = set(state.accepted_demand_ids)

    unknown_fragment_demands = {index.demand_id for index in fragment_networks.indexes}.difference(
        prior_ids
    )

    if unknown_fragment_demands:
        raise ValueError(
            "Fragment networks reference demands without "
            "prior accepted commitments: "
            f"{tuple(sorted(unknown_fragment_demands))}."
        )


def build_dynamic_full_reroute_model(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    recovery_capacity: RecoveryCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
    *,
    truck_penalty_per_teu_by_demand: Mapping[str, float],
    allow_current_truck: bool = True,
) -> DynamicFullRerouteModelArtifacts:
    """Build current booking + prior fragments + truck recourse."""
    _validate_inputs(
        instance,
        state,
        event,
        recovery_capacity,
        fragment_networks,
    )

    if not isinstance(allow_current_truck, bool):
        raise TypeError("allow_current_truck must be a boolean.")

    penalties = _normalise_penalties(
        event,
        fragment_networks,
        truck_penalty_per_teu_by_demand,
    )

    demand = event.demand
    current_network_index = instance.network_index_for(demand.demand_id)

    available_transport_arc_ids = set(recovery_capacity.available_arc_ids)

    unavailable_current_arcs = tuple(
        sorted(
            arc_id
            for arc_id in current_network_index.feasible_arc_ids
            if instance.arc_by_id(arc_id).is_transport and arc_id not in available_transport_arc_ids
        )
    )

    if unavailable_current_arcs:
        raise ValueError(
            f"Current demand contains non-bookable transport arcs: {unavailable_current_arcs}."
        )

    model = Model(
        name=_solver_name(
            "dynamic_full_reroute",
            event.sequence_number,
            demand.demand_id,
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

    for arc_number, arc_id in enumerate(current_network_index.all_flow_arc_ids):
        current_flow_variables[arc_id] = model.continuous_var(
            lb=0.0,
            ub=float(demand.volume),
            name=_solver_name(
                "current_v",
                demand.demand_id,
                arc_number,
                arc_id,
            ),
        )

    current_truck_variable = model.continuous_var(
        lb=0.0,
        ub=(float(demand.volume) if allow_current_truck else 0.0),
        name=_solver_name(
            "current_truck",
            demand.demand_id,
        ),
    )

    fragment_flow_variables: dict[
        tuple[str, str],
        Any,
    ] = {}
    fragment_truck_variables: dict[str, Any] = {}

    for index in fragment_networks.indexes:
        fragment_truck_variables[index.fragment_id] = model.continuous_var(
            lb=0.0,
            ub=index.volume,
            name=_solver_name(
                "fragment_truck",
                index.fragment_id,
            ),
        )

        for arc_number, arc_id in enumerate(index.all_flow_arc_ids):
            fragment_flow_variables[(index.fragment_id, arc_id)] = model.continuous_var(
                lb=0.0,
                ub=index.volume,
                name=_solver_name(
                    "fragment_v",
                    index.fragment_id,
                    arc_number,
                    arc_id,
                ),
            )

    model.maximize(
        demand.maximum_revenue * acceptance_variable
        - penalties[demand.demand_id] * current_truck_variable
        - model.sum(
            penalties[index.demand_id] * fragment_truck_variables[index.fragment_id]
            for index in fragment_networks.indexes
        )
    )

    current_truck_acceptance_constraint = model.add_constraint(
        current_truck_variable <= demand.volume * acceptance_variable,
        ctname=_solver_name(
            "current_truck_acceptance",
            demand.demand_id,
        ),
    )

    current_flow_balance_constraints: dict[
        object,
        Any,
    ] = {}

    for node_index in current_network_index.node_flow_indexes:
        node = node_index.node

        outgoing = model.sum(
            current_flow_variables[arc_id]
            for arc_id in current_network_index.outgoing_flow_arc_ids(node)
        )

        incoming = model.sum(
            current_flow_variables[arc_id]
            for arc_id in current_network_index.incoming_flow_arc_ids(node)
        )

        required = (
            demand.volume * acceptance_variable - current_truck_variable
            if node == current_network_index.source
            else 0.0
        )

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
        model.sum(current_flow_variables[arc_id] for arc_id in current_network_index.sink_arc_ids)
        + current_truck_variable
        == demand.volume * acceptance_variable,
        ctname=_solver_name(
            "current_delivery",
            demand.demand_id,
        ),
    )

    fragment_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ] = {}
    fragment_sink_balance_constraints: dict[
        str,
        Any,
    ] = {}

    for index in fragment_networks.indexes:
        fragment_id = index.fragment_id
        truck = fragment_truck_variables[fragment_id]

        for node_index in index.node_flow_indexes:
            node = node_index.node

            outgoing = model.sum(
                fragment_flow_variables[(fragment_id, arc_id)]
                for arc_id in index.outgoing_flow_arc_ids(node)
            )

            incoming = model.sum(
                fragment_flow_variables[(fragment_id, arc_id)]
                for arc_id in index.incoming_flow_arc_ids(node)
            )

            required = index.volume - truck if node == index.source else 0.0

            fragment_flow_balance_constraints[(fragment_id, node)] = model.add_constraint(
                outgoing - incoming == required,
                ctname=_solver_name(
                    "fragment_balance",
                    fragment_id,
                    node[0],
                    node[1],
                ),
            )

        fragment_sink_balance_constraints[fragment_id] = model.add_constraint(
            model.sum(
                fragment_flow_variables[(fragment_id, arc_id)] for arc_id in index.sink_arc_ids
            )
            + truck
            == index.volume,
            ctname=_solver_name(
                "fragment_delivery",
                fragment_id,
            ),
        )

    capacity_constraints: dict[str, Any] = {}
    available_capacities: dict[str, float] = {}

    for arc_id in recovery_capacity.available_arc_ids:
        relevant: list[Any] = []

        if arc_id in current_network_index.feasible_arc_ids:
            relevant.append(current_flow_variables[arc_id])

        for index in fragment_networks.indexes:
            if arc_id in index.feasible_arc_ids:
                relevant.append(fragment_flow_variables[(index.fragment_id, arc_id)])

        if not relevant:
            continue

        available = float(recovery_capacity.available_capacity_for(arc_id))

        available_capacities[arc_id] = available

        capacity_constraints[arc_id] = model.add_constraint(
            model.sum(relevant) <= available,
            ctname=_solver_name(
                "actual_full_reroute_capacity",
                arc_id,
            ),
        )

    return DynamicFullRerouteModelArtifacts(
        instance=instance,
        state=state,
        event=event,
        recovery_capacity=recovery_capacity,
        fragment_networks=fragment_networks,
        current_network_index=current_network_index,
        truck_penalty_per_teu_by_demand=penalties,
        allow_current_truck=allow_current_truck,
        model=model,
        acceptance_variable=acceptance_variable,
        current_flow_variables=current_flow_variables,
        current_truck_variable=current_truck_variable,
        fragment_flow_variables=fragment_flow_variables,
        fragment_truck_variables=fragment_truck_variables,
        current_flow_balance_constraints=(current_flow_balance_constraints),
        current_sink_balance_constraint=(current_sink_balance_constraint),
        current_truck_acceptance_constraint=(current_truck_acceptance_constraint),
        fragment_flow_balance_constraints=(fragment_flow_balance_constraints),
        fragment_sink_balance_constraints=(fragment_sink_balance_constraints),
        capacity_constraints=capacity_constraints,
        available_capacities=available_capacities,
    )


def solve_dynamic_full_reroute_model(
    artifacts: DynamicFullRerouteModelArtifacts,
) -> DynamicFullRerouteSolution:
    """Solve and extract a dynamic Full-Reroute booking."""
    if not isinstance(
        artifacts,
        DynamicFullRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be a DynamicFullRerouteModelArtifacts.")

    raw = artifacts.model.solve(log_output=(artifacts.instance.config.solver.log_output))

    status = str(artifacts.model.solve_details.status)

    current_penalty = artifacts.truck_penalty_per_teu_by_demand[artifacts.event.demand_id]

    if raw is None:
        return DynamicFullRerouteSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            is_solved=False,
            solve_status=status,
            objective_value=None,
            acceptance_fraction=None,
            current_flows=(),
            current_truck_volume=None,
            current_truck_penalty_per_teu=current_penalty,
            fragment_flows=(),
            fragment_truck_allocations=(),
        )

    current_flows = tuple(
        CurrentDemandFlowResult(
            arc_id=arc_id,
            volume=float(raw.get_value(variable)),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    fragment_flows = tuple(
        FragmentFlowResult(
            fragment_id=fragment_id,
            arc_id=arc_id,
            volume=float(raw.get_value(variable)),
        )
        for (
            fragment_id,
            arc_id,
        ), variable in sorted(artifacts.fragment_flow_variables.items())
    )

    fragment_trucks = tuple(
        TruckAllocationResult(
            fragment_id=index.fragment_id,
            demand_id=index.demand_id,
            volume=float(raw.get_value(artifacts.fragment_truck_variables[index.fragment_id])),
            penalty_per_teu=(artifacts.truck_penalty_per_teu_by_demand[index.demand_id]),
        )
        for index in artifacts.fragment_networks.indexes
    )

    return DynamicFullRerouteSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        is_solved=True,
        solve_status=status,
        objective_value=float(raw.objective_value),
        acceptance_fraction=float(raw.get_value(artifacts.acceptance_variable)),
        current_flows=current_flows,
        current_truck_volume=float(raw.get_value(artifacts.current_truck_variable)),
        current_truck_penalty_per_teu=current_penalty,
        fragment_flows=fragment_flows,
        fragment_truck_allocations=fragment_trucks,
    )


def validate_dynamic_full_reroute_solution(
    artifacts: DynamicFullRerouteModelArtifacts,
    solution: DynamicFullRerouteSolution,
    *,
    tolerance: float = DYNAMIC_FULL_REROUTE_TOLERANCE,
) -> DynamicFullRerouteValidationReport:
    """Independently validate dynamic Full-Reroute."""
    tol = _positive_float("tolerance", tolerance)

    if not isinstance(
        artifacts,
        DynamicFullRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be a DynamicFullRerouteModelArtifacts.")

    if not isinstance(
        solution,
        DynamicFullRerouteSolution,
    ):
        raise TypeError("solution must be a DynamicFullRerouteSolution.")

    if not solution.is_solved:
        raise ValueError("An unsolved dynamic Full-Reroute solution cannot be validated.")

    if (
        solution.objective_value is None
        or solution.acceptance_fraction is None
        or solution.current_truck_volume is None
    ):
        raise ValueError("Solved dynamic Full-Reroute output is incomplete.")

    if solution.event_id != artifacts.event.event_id:
        raise ValueError("Solution event does not match artifacts.")

    if solution.demand_id != artifacts.event.demand_id:
        raise ValueError("Solution demand does not match artifacts.")

    expected_current_arc_ids = set(artifacts.current_flow_variables)
    actual_current_arc_ids = {result.arc_id for result in solution.current_flows}

    if actual_current_arc_ids != expected_current_arc_ids:
        raise ValueError("Current flow indexes do not match model.")

    expected_fragment_keys = set(artifacts.fragment_flow_variables)
    actual_fragment_keys = {
        (result.fragment_id, result.arc_id) for result in solution.fragment_flows
    }

    if actual_fragment_keys != expected_fragment_keys:
        raise ValueError("Fragment flow indexes do not match model.")

    expected_fragment_ids = set(artifacts.fragment_truck_variables)
    actual_fragment_ids = {
        allocation.fragment_id for allocation in solution.fragment_truck_allocations
    }

    if actual_fragment_ids != expected_fragment_ids:
        raise ValueError("Fragment truck indexes do not match model.")

    demand = artifacts.event.demand

    acceptance = float(demand.normalize_acceptance_fraction(solution.acceptance_fraction))
    accepted_volume = float(demand.volume) * acceptance
    current_truck = float(solution.current_truck_volume)

    current_flow = {result.arc_id: float(result.volume) for result in solution.current_flows}
    fragment_flow = {
        (result.fragment_id, result.arc_id): float(result.volume)
        for result in solution.fragment_flows
    }
    fragment_truck = {
        allocation.fragment_id: float(allocation.volume)
        for allocation in solution.fragment_truck_allocations
    }

    violations: list[str] = []
    max_flow = 0.0
    max_delivery = 0.0
    max_capacity = 0.0

    if current_truck < -tol:
        violations.append("Current truck volume is negative.")

    if current_truck - accepted_volume > tol:
        violations.append("Current truck volume exceeds accepted current volume.")

    current_index = artifacts.current_network_index

    for node_index in current_index.node_flow_indexes:
        node = node_index.node

        outgoing = sum(current_flow[arc_id] for arc_id in current_index.outgoing_flow_arc_ids(node))
        incoming = sum(current_flow[arc_id] for arc_id in current_index.incoming_flow_arc_ids(node))

        required = accepted_volume - current_truck if node == current_index.source else 0.0

        violation = abs(outgoing - incoming - required)
        max_flow = max(max_flow, violation)

        if violation > tol:
            violations.append(f"Current flow-balance violation at {node}: {violation}.")

    current_barge_delivered = sum(current_flow[arc_id] for arc_id in current_index.sink_arc_ids)

    current_delivery_violation = abs(current_barge_delivered + current_truck - accepted_volume)
    max_delivery = max(
        max_delivery,
        current_delivery_violation,
    )

    if current_delivery_violation > tol:
        violations.append("Current barge-plus-truck delivery balance failed.")

    for index in artifacts.fragment_networks.indexes:
        fragment_id = index.fragment_id
        truck = fragment_truck[fragment_id]

        if truck < -tol:
            violations.append(f"Negative truck volume for {fragment_id}.")

        if truck - index.volume > tol:
            violations.append(f"Truck volume exceeds fragment volume for {fragment_id}.")

        for node_index in index.node_flow_indexes:
            node = node_index.node

            outgoing = sum(
                fragment_flow[(fragment_id, arc_id)] for arc_id in index.outgoing_flow_arc_ids(node)
            )
            incoming = sum(
                fragment_flow[(fragment_id, arc_id)] for arc_id in index.incoming_flow_arc_ids(node)
            )

            required = index.volume - truck if node == index.source else 0.0

            violation = abs(outgoing - incoming - required)
            max_flow = max(max_flow, violation)

            if violation > tol:
                violations.append(f"Fragment flow-balance violation for {fragment_id} at {node}.")

        barge_delivered = sum(fragment_flow[(fragment_id, arc_id)] for arc_id in index.sink_arc_ids)

        violation = abs(barge_delivered + truck - index.volume)
        max_delivery = max(
            max_delivery,
            violation,
        )

        if violation > tol:
            violations.append(
                f"Fragment barge-plus-truck delivery balance failed for {fragment_id}."
            )

    for arc_id, available in artifacts.available_capacities.items():
        used = 0.0

        if arc_id in current_index.feasible_arc_ids:
            used += current_flow[arc_id]

        for index in artifacts.fragment_networks.indexes:
            if arc_id in index.feasible_arc_ids:
                used += fragment_flow[(index.fragment_id, arc_id)]

        violation = max(
            0.0,
            used - available,
        )
        max_capacity = max(
            max_capacity,
            violation,
        )

        if violation > tol:
            violations.append(f"Dynamic actual-capacity violation on {arc_id}: {violation}.")

    expected_objective = (
        demand.maximum_revenue * acceptance
        - artifacts.truck_penalty_per_teu_by_demand[demand.demand_id] * current_truck
        - sum(
            artifacts.truck_penalty_per_teu_by_demand[index.demand_id]
            * fragment_truck[index.fragment_id]
            for index in artifacts.fragment_networks.indexes
        )
    )

    objective_violation = abs(float(solution.objective_value) - expected_objective)

    if objective_violation > tol:
        violations.append(
            "Dynamic Full-Reroute objective does not match independent reconstruction."
        )

    return DynamicFullRerouteValidationReport(
        is_valid=not violations,
        max_flow_balance_violation=max_flow,
        max_delivery_balance_violation=max_delivery,
        max_capacity_violation=max_capacity,
        objective_violation=objective_violation,
        violations=tuple(violations),
    )
