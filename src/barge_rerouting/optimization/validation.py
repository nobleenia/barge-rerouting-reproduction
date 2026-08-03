"""Independent validation of solved DCA models."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.dca import DcaSolution


@dataclass(frozen=True, slots=True)
class DcaValidationReport:
    """Numerical validation results for one solved DCA model."""

    is_valid: bool
    tolerance: float
    recomputed_objective: float
    reported_objective: float
    max_acceptance_violation: float
    max_negative_flow_violation: float
    max_flow_balance_violation: float
    max_sink_balance_violation: float
    max_capacity_violation: float
    objective_violation: float
    violations: tuple[str, ...]


def _validate_tolerance(tolerance: object) -> float:
    """Validate and return a strictly positive finite tolerance."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise TypeError("tolerance must be a real number.")

    numeric_tolerance = float(tolerance)

    if not isfinite(numeric_tolerance):
        raise ValueError("tolerance must be finite.")

    if numeric_tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")

    return numeric_tolerance


def validate_dca_solution(
    instance: ExperimentInstance,
    solution: DcaSolution,
    *,
    tolerance: float = 1e-6,
) -> DcaValidationReport:
    """Independently validate a solved DCA solution."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(solution, DcaSolution):
        raise TypeError("solution must be a DcaSolution.")

    if not solution.is_solved or solution.objective_value is None:
        raise ValueError("Only a solved DCA solution can be validated.")

    validated_tolerance = _validate_tolerance(tolerance)

    acceptance_lookup = {
        result.demand_id: float(result.acceptance_fraction) for result in solution.acceptances
    }
    flow_lookup = {
        (result.demand_id, result.arc_id): float(result.volume) for result in solution.flows
    }

    violations: list[str] = []

    max_acceptance_violation = 0.0
    max_negative_flow_violation = 0.0
    max_flow_balance_violation = 0.0
    max_sink_balance_violation = 0.0
    max_capacity_violation = 0.0

    recomputed_objective = 0.0

    for demand in instance.demands:
        if demand.demand_id not in acceptance_lookup:
            raise ValueError(f"Missing acceptance result for demand {demand.demand_id}.")

        acceptance = acceptance_lookup[demand.demand_id]

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
            raise ValueError(f"Unsupported customer category: {demand.category}")

        max_acceptance_violation = max(
            max_acceptance_violation,
            acceptance_violation,
        )

        if acceptance_violation > validated_tolerance:
            violations.append(
                f"Acceptance-domain violation for {demand.demand_id}: {acceptance_violation}."
            )

        recomputed_objective += demand.maximum_revenue * acceptance

    for flow_result in solution.flows:
        negative_flow_violation = max(0.0, -float(flow_result.volume))

        max_negative_flow_violation = max(
            max_negative_flow_violation,
            negative_flow_violation,
        )

        if negative_flow_violation > validated_tolerance:
            violations.append(
                f"Negative flow for {flow_result.demand_id} on "
                f"{flow_result.arc_id}: {flow_result.volume}."
            )

    for network_index in instance.demand_network_indexes:
        demand = network_index.demand
        demand_id = network_index.demand_id
        acceptance = acceptance_lookup[demand_id]

        for node_index in network_index.node_flow_indexes:
            node = node_index.node

            outgoing_flow = 0.0

            for arc_id in network_index.outgoing_flow_arc_ids(node):
                key = (demand_id, arc_id)

                if key not in flow_lookup:
                    raise ValueError(f"Missing flow result for {demand_id} on {arc_id}.")

                outgoing_flow += flow_lookup[key]

            incoming_flow = 0.0

            for arc_id in network_index.incoming_flow_arc_ids(node):
                key = (demand_id, arc_id)

                if key not in flow_lookup:
                    raise ValueError(f"Missing flow result for {demand_id} on {arc_id}.")

                incoming_flow += flow_lookup[key]

            required_balance = demand.volume * acceptance if node == network_index.source else 0.0

            balance_violation = abs(outgoing_flow - incoming_flow - required_balance)

            max_flow_balance_violation = max(
                max_flow_balance_violation,
                balance_violation,
            )

            if balance_violation > validated_tolerance:
                violations.append(
                    f"Flow-balance violation for {demand_id} at {node}: {balance_violation}."
                )

        delivered_flow = 0.0

        for sink_arc_id in network_index.sink_arc_ids:
            key = (demand_id, sink_arc_id)

            if key not in flow_lookup:
                raise ValueError(f"Missing delivery flow for {demand_id} on {sink_arc_id}.")

            delivered_flow += flow_lookup[key]

        required_delivery = demand.volume * acceptance
        sink_violation = abs(delivered_flow - required_delivery)

        max_sink_balance_violation = max(
            max_sink_balance_violation,
            sink_violation,
        )

        if sink_violation > validated_tolerance:
            violations.append(f"Sink-balance violation for {demand_id}: {sink_violation}.")

    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no capacity.")

        used_capacity = 0.0

        for network_index in instance.demand_network_indexes:
            key = (
                network_index.demand_id,
                arc.arc_id,
            )

            used_capacity += flow_lookup.get(key, 0.0)

        capacity_violation = max(
            0.0,
            used_capacity - arc.nominal_capacity,
        )

        max_capacity_violation = max(
            max_capacity_violation,
            capacity_violation,
        )

        if capacity_violation > validated_tolerance:
            violations.append(f"Capacity violation on {arc.arc_id}: {capacity_violation}.")

    reported_objective = float(solution.objective_value)
    objective_violation = abs(recomputed_objective - reported_objective)

    if objective_violation > validated_tolerance:
        violations.append(f"Objective reconstruction violation: {objective_violation}.")

    return DcaValidationReport(
        is_valid=not violations,
        tolerance=validated_tolerance,
        recomputed_objective=recomputed_objective,
        reported_objective=reported_objective,
        max_acceptance_violation=max_acceptance_violation,
        max_negative_flow_violation=max_negative_flow_violation,
        max_flow_balance_violation=max_flow_balance_violation,
        max_sink_balance_violation=max_sink_balance_violation,
        max_capacity_violation=max_capacity_violation,
        objective_violation=objective_violation,
        violations=tuple(violations),
    )
