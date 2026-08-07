"""Explicit truck recourse for status-triggered barge recovery."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.disruption.recovery import (
    RecoveryFragmentSnapshot,
)
from barge_rerouting.disruption.recovery_capacity import (
    RecoveryCapacitySnapshot,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.network import (
    FragmentNetworkSnapshot,
)

TRUCK_RECOURSE_TOLERANCE = 1e-6


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw_name = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw_name)


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


def _normalise_penalties(
    recovery_fragments: RecoveryFragmentSnapshot,
    values: Mapping[str, float],
) -> dict[str, float]:
    """Validate one truck penalty per affected demand."""
    if not isinstance(values, Mapping):
        raise TypeError("truck_penalty_per_teu_by_demand must be a mapping.")

    penalties: dict[str, float] = {}

    for demand_id, raw_penalty in values.items():
        if not isinstance(demand_id, str):
            raise TypeError("Truck-penalty demand identifiers must be strings.")

        normalised = demand_id.strip()

        if not normalised:
            raise ValueError("Truck-penalty demand identifiers must be non-empty.")

        if normalised in penalties:
            raise ValueError("Truck-penalty demand identifiers must be unique.")

        penalties[normalised] = _positive_float(
            f"truck penalty for {normalised}",
            raw_penalty,
        )

    expected = set(recovery_fragments.demand_ids)

    if set(penalties) != expected:
        missing = tuple(sorted(expected.difference(penalties)))
        extra = tuple(sorted(set(penalties).difference(expected)))

        raise ValueError(
            "Truck penalties must cover exactly the "
            "recovery demands; "
            f"missing={missing}, extra={extra}."
        )

    return penalties


@dataclass(frozen=True, slots=True)
class RecoveryBargeFlowResult:
    """Solved barge flow of one recovery fragment."""

    fragment_id: str
    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class TruckAllocationResult:
    """Solved direct-truck allocation of one fragment."""

    fragment_id: str
    demand_id: str
    volume: float
    penalty_per_teu: float

    @property
    def penalty_value(self) -> float:
        """Return truck penalty incurred by this allocation."""
        return float(self.volume * self.penalty_per_teu)


@dataclass(frozen=True, slots=True)
class TruckRecourseSolution:
    """Extracted status-recovery optimisation result."""

    event_id: str
    is_solved: bool
    solve_status: str
    objective_value: float | None
    barge_flows: tuple[RecoveryBargeFlowResult, ...]
    truck_allocations: tuple[TruckAllocationResult, ...]

    def fragment_flow_on(
        self,
        fragment_id: str,
        arc_id: str,
    ) -> float:
        """Return barge flow for one fragment-arc pair."""
        for result in self.barge_flows:
            if result.fragment_id == fragment_id and result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown recovery fragment-arc result: {fragment_id}, {arc_id}.")

    def truck_volume_for(
        self,
        fragment_id: str,
    ) -> float:
        """Return trucked volume for one fragment."""
        for result in self.truck_allocations:
            if result.fragment_id == fragment_id:
                return float(result.volume)

        raise KeyError(f"Unknown recovery fragment: {fragment_id}")

    @property
    def total_truck_volume(self) -> float:
        """Return total volume transferred to trucks."""
        return float(sum(allocation.volume for allocation in self.truck_allocations))

    @property
    def total_truck_penalty(self) -> float:
        """Return total incurred truck penalty."""
        return float(sum(allocation.penalty_value for allocation in self.truck_allocations))


@dataclass(frozen=True, slots=True)
class TruckRecourseModelArtifacts:
    """DOcplex objects for one status-recovery optimisation."""

    instance: ExperimentInstance
    recovery_fragments: RecoveryFragmentSnapshot
    recovery_capacity: RecoveryCapacitySnapshot
    fragment_networks: FragmentNetworkSnapshot
    truck_penalty_per_teu_by_demand: dict[str, float]
    model: Any
    fragment_flow_variables: dict[tuple[str, str], Any]
    truck_variables: dict[str, Any]
    flow_balance_constraints: dict[tuple[str, object], Any]
    sink_balance_constraints: dict[str, Any]
    capacity_constraints: dict[str, Any]
    available_capacities: dict[str, float]


@dataclass(frozen=True, slots=True)
class TruckRecourseValidationReport:
    """Independent residual checks for a solved recovery model."""

    is_valid: bool
    max_flow_balance_violation: float
    max_delivery_balance_violation: float
    max_capacity_violation: float
    objective_violation: float
    violations: tuple[str, ...]


def _validate_inputs(
    instance: ExperimentInstance,
    recovery_fragments: RecoveryFragmentSnapshot,
    recovery_capacity: RecoveryCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
) -> None:
    """Validate status-recovery model inputs."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        recovery_fragments,
        RecoveryFragmentSnapshot,
    ):
        raise TypeError("recovery_fragments must be a RecoveryFragmentSnapshot.")

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

    for snapshot in (
        recovery_fragments,
        recovery_capacity,
        fragment_networks,
    ):
        if snapshot.instance_fingerprint != fingerprint:
            raise ValueError("Truck-recourse inputs belong to different instances.")

        if snapshot.physical_time != recovery_fragments.physical_time:
            raise ValueError("Truck-recourse inputs must use the same physical time.")

    if recovery_capacity.event_id != recovery_fragments.event_id:
        raise ValueError("Recovery capacity must use the status-recovery event.")

    if fragment_networks.current_event_id != recovery_fragments.event_id:
        raise ValueError("Fragment networks must use the status-recovery event.")

    if set(fragment_networks.fragment_ids) != set(recovery_fragments.fragment_ids):
        raise ValueError("Fragment-network indexes must match the recovery fragment set.")

    if recovery_capacity.fixed_overload_arc_ids:
        raise ValueError(
            "Truck-recourse optimisation cannot repair "
            "fixed reservations outside the released "
            "recovery set."
        )


def build_truck_recourse_model(
    instance: ExperimentInstance,
    recovery_fragments: RecoveryFragmentSnapshot,
    recovery_capacity: RecoveryCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
    *,
    truck_penalty_per_teu_by_demand: Mapping[str, float],
) -> TruckRecourseModelArtifacts:
    """Build status recovery with explicit truck recourse."""
    _validate_inputs(
        instance,
        recovery_fragments,
        recovery_capacity,
        fragment_networks,
    )

    penalties = _normalise_penalties(
        recovery_fragments,
        truck_penalty_per_teu_by_demand,
    )

    model = Model(
        name=_solver_name(
            "status_truck_recovery",
            recovery_fragments.event_id,
        ),
        log_output=instance.config.solver.log_output,
    )

    model.parameters.timelimit = instance.config.solver.time_limit_seconds
    model.parameters.mip.tolerances.mipgap = instance.config.solver.relative_mip_gap

    fragment_flow_variables: dict[
        tuple[str, str],
        Any,
    ] = {}

    truck_variables: dict[str, Any] = {}

    for index in fragment_networks.indexes:
        truck_variables[index.fragment_id] = model.continuous_var(
            lb=0.0,
            ub=index.volume,
            name=_solver_name(
                "truck",
                index.fragment_id,
            ),
        )

        for arc_number, arc_id in enumerate(index.all_flow_arc_ids):
            fragment_flow_variables[(index.fragment_id, arc_id)] = model.continuous_var(
                lb=0.0,
                ub=index.volume,
                name=_solver_name(
                    "recovery_v",
                    index.fragment_id,
                    arc_number,
                    arc_id,
                ),
            )

    model.minimize(
        model.sum(
            penalties[index.demand_id] * truck_variables[index.fragment_id]
            for index in fragment_networks.indexes
        )
    )

    flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ] = {}

    sink_balance_constraints: dict[str, Any] = {}

    for index in fragment_networks.indexes:
        fragment_id = index.fragment_id
        truck = truck_variables[fragment_id]

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

            flow_balance_constraints[(fragment_id, node)] = model.add_constraint(
                outgoing - incoming == required,
                ctname=_solver_name(
                    "recovery_flow_balance",
                    fragment_id,
                    node[0],
                    node[1],
                ),
            )

        sink_balance_constraints[fragment_id] = model.add_constraint(
            model.sum(
                fragment_flow_variables[(fragment_id, arc_id)] for arc_id in index.sink_arc_ids
            )
            + truck
            == index.volume,
            ctname=_solver_name(
                "recovery_delivery_balance",
                fragment_id,
            ),
        )

    capacity_constraints: dict[str, Any] = {}
    available_capacities: dict[str, float] = {}

    for arc_id in recovery_capacity.available_arc_ids:
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Recovery capacity may index only transport arcs.")

        relevant_variables: list[Any] = []

        for index in fragment_networks.indexes:
            if arc_id not in index.feasible_arc_ids:
                continue

            relevant_variables.append(fragment_flow_variables[(index.fragment_id, arc_id)])

        if not relevant_variables:
            continue

        available = float(recovery_capacity.available_capacity_for(arc_id))

        available_capacities[arc_id] = available

        capacity_constraints[arc_id] = model.add_constraint(
            model.sum(relevant_variables) <= available,
            ctname=_solver_name(
                "actual_recovery_capacity",
                arc_id,
            ),
        )

    return TruckRecourseModelArtifacts(
        instance=instance,
        recovery_fragments=recovery_fragments,
        recovery_capacity=recovery_capacity,
        fragment_networks=fragment_networks,
        truck_penalty_per_teu_by_demand=penalties,
        model=model,
        fragment_flow_variables=fragment_flow_variables,
        truck_variables=truck_variables,
        flow_balance_constraints=flow_balance_constraints,
        sink_balance_constraints=sink_balance_constraints,
        capacity_constraints=capacity_constraints,
        available_capacities=available_capacities,
    )


def solve_truck_recourse_model(
    artifacts: TruckRecourseModelArtifacts,
) -> TruckRecourseSolution:
    """Solve and extract one status-recovery model."""
    if not isinstance(
        artifacts,
        TruckRecourseModelArtifacts,
    ):
        raise TypeError("artifacts must be TruckRecourseModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=(artifacts.instance.config.solver.log_output))

    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return TruckRecourseSolution(
            event_id=artifacts.recovery_fragments.event_id,
            is_solved=False,
            solve_status=solve_status,
            objective_value=None,
            barge_flows=(),
            truck_allocations=(),
        )

    barge_flows = tuple(
        RecoveryBargeFlowResult(
            fragment_id=fragment_id,
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for (
            fragment_id,
            arc_id,
        ), variable in sorted(artifacts.fragment_flow_variables.items())
    )

    truck_allocations = tuple(
        TruckAllocationResult(
            fragment_id=index.fragment_id,
            demand_id=index.demand_id,
            volume=float(raw_solution.get_value(artifacts.truck_variables[index.fragment_id])),
            penalty_per_teu=(artifacts.truck_penalty_per_teu_by_demand[index.demand_id]),
        )
        for index in artifacts.fragment_networks.indexes
    )

    return TruckRecourseSolution(
        event_id=artifacts.recovery_fragments.event_id,
        is_solved=True,
        solve_status=solve_status,
        objective_value=float(raw_solution.objective_value),
        barge_flows=barge_flows,
        truck_allocations=truck_allocations,
    )


def validate_truck_recourse_solution(
    artifacts: TruckRecourseModelArtifacts,
    solution: TruckRecourseSolution,
    *,
    tolerance: float = TRUCK_RECOURSE_TOLERANCE,
) -> TruckRecourseValidationReport:
    """Independently validate truck/barge recovery identities."""
    validated_tolerance = _positive_float(
        "tolerance",
        tolerance,
    )

    if not isinstance(
        artifacts,
        TruckRecourseModelArtifacts,
    ):
        raise TypeError("artifacts must be TruckRecourseModelArtifacts.")

    if not isinstance(
        solution,
        TruckRecourseSolution,
    ):
        raise TypeError("solution must be a TruckRecourseSolution.")

    if not solution.is_solved:
        raise ValueError("An unsolved recovery model cannot be validated.")

    if solution.objective_value is None:
        raise ValueError("A solved recovery model requires an objective value.")

    expected_flow_keys = set(artifacts.fragment_flow_variables)
    actual_flow_keys = {(result.fragment_id, result.arc_id) for result in solution.barge_flows}

    if actual_flow_keys != expected_flow_keys:
        raise ValueError("Recovery solution flow indexes do not match the model.")

    expected_fragment_ids = set(artifacts.truck_variables)
    actual_fragment_ids = {result.fragment_id for result in solution.truck_allocations}

    if actual_fragment_ids != expected_fragment_ids:
        raise ValueError("Truck-allocation indexes do not match the model.")

    violations: list[str] = []
    max_flow_balance_violation = 0.0
    max_delivery_balance_violation = 0.0
    max_capacity_violation = 0.0

    flow_lookup = {
        (result.fragment_id, result.arc_id): float(result.volume) for result in solution.barge_flows
    }

    truck_lookup = {
        result.fragment_id: float(result.volume) for result in solution.truck_allocations
    }

    for index in artifacts.fragment_networks.indexes:
        fragment_id = index.fragment_id
        truck = truck_lookup[fragment_id]

        if truck < -validated_tolerance:
            violations.append(f"Negative truck volume for {fragment_id}.")

        if truck - index.volume > validated_tolerance:
            violations.append(f"Truck volume exceeds fragment volume for {fragment_id}.")

        for node_index in index.node_flow_indexes:
            node = node_index.node

            outgoing = sum(
                flow_lookup[(fragment_id, arc_id)] for arc_id in index.outgoing_flow_arc_ids(node)
            )
            incoming = sum(
                flow_lookup[(fragment_id, arc_id)] for arc_id in index.incoming_flow_arc_ids(node)
            )

            required = index.volume - truck if node == index.source else 0.0

            violation = abs(outgoing - incoming - required)

            max_flow_balance_violation = max(
                max_flow_balance_violation,
                violation,
            )

            if violation > validated_tolerance:
                violations.append(
                    f"Recovery flow-balance violation for {fragment_id} at {node}: {violation}."
                )

        barge_delivered = sum(flow_lookup[(fragment_id, arc_id)] for arc_id in index.sink_arc_ids)

        delivery_violation = abs(barge_delivered + truck - index.volume)

        max_delivery_balance_violation = max(
            max_delivery_balance_violation,
            delivery_violation,
        )

        if delivery_violation > validated_tolerance:
            violations.append(
                f"Barge-plus-truck delivery balance failed for {fragment_id}: {delivery_violation}."
            )

    for arc_id, available in artifacts.available_capacities.items():
        used = sum(
            flow_lookup[(index.fragment_id, arc_id)]
            for index in artifacts.fragment_networks.indexes
            if arc_id in index.feasible_arc_ids
        )

        violation = max(
            0.0,
            used - available,
        )

        max_capacity_violation = max(
            max_capacity_violation,
            violation,
        )

        if violation > validated_tolerance:
            violations.append(f"Actual-capacity violation on {arc_id}: {violation}.")

    expected_objective = sum(
        artifacts.truck_penalty_per_teu_by_demand[index.demand_id] * truck_lookup[index.fragment_id]
        for index in artifacts.fragment_networks.indexes
    )

    objective_violation = abs(float(solution.objective_value) - expected_objective)

    if objective_violation > validated_tolerance:
        violations.append(
            "Truck-recourse objective does not equal the independently reconstructed penalty."
        )

    return TruckRecourseValidationReport(
        is_valid=not violations,
        max_flow_balance_violation=(max_flow_balance_violation),
        max_delivery_balance_violation=(max_delivery_balance_violation),
        max_capacity_violation=max_capacity_violation,
        objective_violation=objective_violation,
        violations=tuple(violations),
    )
