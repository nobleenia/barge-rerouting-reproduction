"""Execution reconstruction using the Phase-10 recovery overlay."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from math import isfinite

from barge_rerouting.disruption.recovery_transition import (
    RecoveredFragmentPlan,
    RecoveryOperationalState,
)
from barge_rerouting.domain import (
    AcceptedDemandState,
    DemandFragment,
    TimeSpaceNode,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    auxiliary_sink_id_for,
    build_auxiliary_sink_arcs,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    EXECUTION_TOLERANCE,
    ExecutionSnapshot,
    PlannedDemandPath,
    build_execution_snapshot,
)

type FlowNode = TimeSpaceNode | str

# A whole recovered plan at this scale is treated as solver numerical dust.
# The dust is removed from physical path reconstruction but retained in volume accounting.
RECOVERY_NUMERICAL_DUST_TOLERANCE = 10.0 * EXECUTION_TOLERANCE


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _latest_plans_by_demand(
    state: RecoveryOperationalState,
) -> dict[str, tuple[RecoveredFragmentPlan, ...]]:
    """Return the most recent persisted recovery generation per demand.

    Recovery chronology is defined by ``recovery_event_ids`` rather
    than lexicographic event identifiers. This matters when multiple
    recovery triggers occur at the same physical time, such as a
    status update immediately followed by a Full-Reroute booking.
    """
    grouped: dict[str, list[RecoveredFragmentPlan]] = defaultdict(list)

    for plan in state.active_fragment_plans:
        grouped[plan.demand_id].append(plan)

    event_order = {event_id: position for position, event_id in enumerate(state.recovery_event_ids)}

    latest: dict[str, tuple[RecoveredFragmentPlan, ...]] = {}

    for demand_id, plans in grouped.items():
        unknown_event_ids = tuple(
            sorted({plan.event_id for plan in plans if plan.event_id not in event_order})
        )

        if unknown_event_ids:
            raise ValueError(
                f"Recovered plans reference unknown recovery events: {unknown_event_ids}."
            )

        latest_event_id = max(
            (plan.event_id for plan in plans),
            key=event_order.__getitem__,
        )

        selected = tuple(
            sorted(
                (plan for plan in plans if plan.event_id == latest_event_id),
                key=lambda plan: plan.fragment_id,
            )
        )

        latest[demand_id] = selected

    return latest


def _decompose_recovered_plan(
    instance: ExperimentInstance,
    plan: RecoveredFragmentPlan,
) -> tuple[PlannedDemandPath, ...]:
    """Decompose one persisted recovered barge flow into paths."""
    if plan.original_remaining_volume <= RECOVERY_NUMERICAL_DUST_TOLERANCE:
        return ()

    flow_by_arc = {
        flow.arc_id: float(flow.volume)
        for flow in plan.barge_arc_flows
        if flow.volume > EXECUTION_TOLERANCE
    }

    if not flow_by_arc:
        return ()

    demand = instance.demand_by_id(plan.demand_id)

    candidate_destination_nodes = tuple(
        sorted(
            (
                node
                for node in instance.graph.nodes
                if isinstance(node, tuple)
                and len(node) == 2
                and node[0] == demand.destination
                and plan.rerouting_source[1] <= node[1] <= demand.due_time
            ),
            key=lambda node: (node[1], node[0]),
        )
    )

    sink_arcs = build_auxiliary_sink_arcs(
        demand_id=plan.fragment_id,
        destination_nodes=candidate_destination_nodes,
    )

    sink_arc_by_id = {sink_arc.arc_id: sink_arc for sink_arc in sink_arcs}

    tail_by_arc: dict[str, FlowNode] = {}
    head_by_arc: dict[str, FlowNode] = {}
    outgoing_by_node: dict[FlowNode, list[str]] = defaultdict(list)

    for arc_id in flow_by_arc:
        if arc_id in sink_arc_by_id:
            sink_arc = sink_arc_by_id[arc_id]
            tail_by_arc[arc_id] = sink_arc.tail
            head_by_arc[arc_id] = sink_arc.sink_id
            outgoing_by_node[sink_arc.tail].append(arc_id)
            continue

        arc = instance.arc_by_id(arc_id)

        tail_by_arc[arc_id] = arc.tail
        head_by_arc[arc_id] = arc.head
        outgoing_by_node[arc.tail].append(arc_id)

    for arc_ids in outgoing_by_node.values():
        arc_ids.sort()

    source: FlowNode = plan.rerouting_source
    sink: FlowNode = auxiliary_sink_id_for(plan.fragment_id)

    residual = dict(flow_by_arc)
    recovered_paths: list[PlannedDemandPath] = []

    while (
        sum(
            residual.get(arc_id, 0.0)
            for arc_id in outgoing_by_node.get(
                source,
                (),
            )
        )
        > EXECUTION_TOLERANCE
    ):
        current_node = source
        selected_arc_ids: list[str] = []
        guard = 0

        while current_node != sink:
            candidates = [
                arc_id
                for arc_id in outgoing_by_node.get(
                    current_node,
                    (),
                )
                if residual.get(
                    arc_id,
                    0.0,
                )
                > EXECUTION_TOLERANCE
            ]

            if not candidates:
                raise ValueError(
                    "Persisted recovery flow cannot be decomposed into a complete barge path."
                )

            arc_id = candidates[0]
            selected_arc_ids.append(arc_id)
            current_node = head_by_arc[arc_id]

            guard += 1

            if guard > len(flow_by_arc) + 1:
                raise ValueError("Recovered barge-flow decomposition encountered a cycle.")

        path_volume = min(residual[arc_id] for arc_id in selected_arc_ids)

        if not isfinite(path_volume) or path_volume <= EXECUTION_TOLERANCE:
            raise ValueError("Recovered path volume must be positive and finite.")

        selected_sink_ids = tuple(arc_id for arc_id in selected_arc_ids if arc_id in sink_arc_by_id)

        if len(selected_sink_ids) != 1:
            raise ValueError("Every recovered barge path requires one logical delivery arc.")

        delivery_arc_id = selected_sink_ids[0]

        if selected_arc_ids[-1] != delivery_arc_id:
            raise ValueError("Recovered delivery arc must terminate the path.")

        suffix_physical_arc_ids = tuple(
            arc_id for arc_id in selected_arc_ids if arc_id != delivery_arc_id
        )

        full_physical_arc_ids = (
            *plan.immutable_arc_ids,
            *suffix_physical_arc_ids,
        )

        if len(set(full_physical_arc_ids)) != len(full_physical_arc_ids):
            raise ValueError("Recovered path repeats a physical arc.")

        path_number = len(recovered_paths) + 1

        recovered_paths.append(
            PlannedDemandPath(
                path_id=(f"{plan.fragment_id}::recovery::{plan.event_id}::path::{path_number:04d}"),
                demand_id=plan.demand_id,
                volume=path_volume,
                physical_arc_ids=tuple(full_physical_arc_ids),
                delivery_arc_id=delivery_arc_id,
            )
        )

        for arc_id in selected_arc_ids:
            remaining = residual[arc_id] - path_volume

            residual[arc_id] = 0.0 if abs(remaining) <= EXECUTION_TOLERANCE else remaining

    undecomposed = tuple(
        sorted(arc_id for arc_id, volume in residual.items() if volume > EXECUTION_TOLERANCE)
    )

    if undecomposed:
        raise ValueError(f"Persisted positive recovery flow remains undecomposed: {undecomposed}.")

    return tuple(recovered_paths)


def _delivery_time_for(
    instance: ExperimentInstance,
    path: PlannedDemandPath,
) -> int:
    """Return the destination time encoded by a recovery sink arc."""
    demand = instance.demand_by_id(path.demand_id)

    destination_nodes = tuple(
        node
        for node in instance.graph.nodes
        if isinstance(node, tuple)
        and len(node) == 2
        and node[0] == demand.destination
        and node[1] <= demand.due_time
    )

    # Recovery delivery IDs are deterministic and unique over the
    # candidate destination nodes. Rebuild them rather than parsing
    # the string representation.
    sink_arcs = build_auxiliary_sink_arcs(
        demand_id=(
            path.path_id.rsplit(
                "::recovery::",
                1,
            )[0]
        ),
        destination_nodes=tuple(destination_nodes),
    )

    for sink_arc in sink_arcs:
        if sink_arc.arc_id == path.delivery_arc_id:
            return int(sink_arc.tail[1])

    raise ValueError(f"Could not reconstruct the recovered delivery time for {path.path_id}.")


def _numerical_barge_closure_volume(
    plans: tuple[RecoveredFragmentPlan, ...],
) -> float:
    """Return barge volume closed from numerical-dust recovery plans."""
    return float(
        sum(
            plan.barge_delivered_volume
            for plan in plans
            if (plan.original_remaining_volume <= RECOVERY_NUMERICAL_DUST_TOLERANCE)
        )
    )


def _state_from_recovered_plans(
    instance: ExperimentInstance,
    operational_state: RecoveryOperationalState,
    demand_id: str,
    plans: tuple[RecoveredFragmentPlan, ...],
    physical_time: int,
) -> tuple[
    AcceptedDemandState,
    tuple[PlannedDemandPath, ...],
]:
    """Reconstruct one demand from its latest recovery plans."""
    recovery_time = plans[0].recovery_time
    recovery_event_id = plans[0].event_id

    if any(
        plan.recovery_time != recovery_time or plan.event_id != recovery_event_id for plan in plans
    ):
        raise ValueError("Selected recovery plans must come from one recovery generation.")

    if physical_time < recovery_time:
        raise ValueError("Operational execution cannot apply a recovery before its decision time.")

    event_order = {
        event_id: position for position, event_id in enumerate(operational_state.recovery_event_ids)
    }

    if recovery_event_id not in event_order:
        raise ValueError("Latest recovery plan references an unknown recovery event.")

    recovery_position = event_order[recovery_event_id]

    baseline = build_execution_snapshot(
        instance,
        operational_state.booking_state,
        physical_time=recovery_time,
    )

    baseline_state = baseline.demand_state_for(demand_id)

    # Contractual acceptance remains authoritative, but
    # the original booking route is no longer authoritative
    # for physical delivery after recovery.
    accepted_volume = float(baseline_state.accepted_volume)

    # Volume that physically entered the latest recovery
    # generation. RecoveredFragmentPlan validates that each
    # such volume is subsequently partitioned between barge
    # and truck.
    recovery_remaining_volume = float(sum(plan.original_remaining_volume for plan in plans))

    # Truck allocations from earlier recovery generations are
    # persistent commitments and therefore no longer belong to
    # the volume entering the latest recovery generation.
    prior_truck_volume = float(
        sum(
            transfer.volume
            for transfer in operational_state.truck_transfer_history
            if (
                transfer.demand_id == demand_id
                and event_order[transfer.event_id] < recovery_position
            )
        )
    )

    # A later truck allocation for this demand would contradict
    # the claim that `plans` are its latest recovery generation.
    later_truck_volume = float(
        sum(
            transfer.volume
            for transfer in operational_state.truck_transfer_history
            if (
                transfer.demand_id == demand_id
                and event_order[transfer.event_id] > recovery_position
            )
        )
    )

    if later_truck_volume > EXECUTION_TOLERANCE:
        raise ValueError(
            "Latest recovery generation is inconsistent "
            "with later truck history: "
            f"demand={demand_id}, "
            f"later_truck={later_truck_volume}."
        )

    # Conservation at the instant immediately before the
    # latest recovery:
    #
    # accepted
    #   = previously barge-delivered
    #   + previously truck-allocated
    #   + volume entering latest recovery.
    delivered_barge_before_recovery = float(
        accepted_volume - prior_truck_volume - recovery_remaining_volume
    )

    if delivered_barge_before_recovery < -EXECUTION_TOLERANCE:
        raise ValueError(
            "Recovery-lineage accounting is inconsistent: "
            f"demand={demand_id}, "
            f"accepted={accepted_volume}, "
            f"prior_truck={prior_truck_volume}, "
            f"recovery_remaining="
            f"{recovery_remaining_volume}, "
            f"barge_delivered_before="
            f"{delivered_barge_before_recovery}."
        )

    if abs(delivered_barge_before_recovery) <= EXECUTION_TOLERANCE:
        delivered_barge_before_recovery = 0.0

    # Cross-check persistence of the truck allocation belonging
    # specifically to the latest recovery generation.
    current_generation_truck_history = float(
        sum(
            transfer.volume
            for transfer in operational_state.truck_transfer_history
            if (transfer.demand_id == demand_id and transfer.event_id == recovery_event_id)
        )
    )

    current_generation_truck_plans = float(sum(plan.truck_volume for plan in plans))

    if abs(current_generation_truck_history - current_generation_truck_plans) > EXECUTION_TOLERANCE:
        raise ValueError(
            "Latest recovery plans disagree with "
            "persisted truck history: "
            f"demand={demand_id}, "
            f"plans={current_generation_truck_plans}, "
            f"history="
            f"{current_generation_truck_history}."
        )

    recovered_paths = tuple(
        path
        for plan in plans
        for path in _decompose_recovered_plan(
            instance,
            plan,
        )
    )

    fragments: list[DemandFragment] = []
    delivered_after_recovery = _numerical_barge_closure_volume(plans)

    for path in recovered_paths:
        delivery_time = _delivery_time_for(
            instance,
            path,
        )

        if delivery_time <= physical_time:
            delivered_after_recovery += path.volume
            continue

        network_source = instance.network_index_for(path.demand_id).source

        executed_arc_ids: list[str] = []
        current_node = network_source

        for arc_id in path.physical_arc_ids:
            arc = instance.arc_by_id(arc_id)

            if arc.head[1] <= physical_time:
                executed_arc_ids.append(arc_id)
                current_node = arc.head
            else:
                break

        fragments.append(
            DemandFragment(
                fragment_id=path.path_id,
                demand_id=path.demand_id,
                volume=path.volume,
                current_node=current_node,
                executed_arc_ids=tuple(executed_arc_ids),
            )
        )

    delivered_truck_volume = float(
        sum(
            transfer.volume
            for transfer in operational_state.truck_transfer_history
            if (transfer.demand_id == demand_id and transfer.transfer_time <= physical_time)
        )
    )

    pending_truck_volume = float(
        sum(
            transfer.volume
            for transfer in operational_state.truck_transfer_history
            if (transfer.demand_id == demand_id and transfer.transfer_time > physical_time)
        )
    )

    demand_state = AcceptedDemandState(
        demand=baseline_state.demand,
        acceptance_fraction=(baseline_state.acceptance_fraction),
        fragments=tuple(fragments),
        delivered_barge_volume=(delivered_barge_before_recovery + delivered_after_recovery),
        delivered_truck_volume=(delivered_truck_volume),
        pending_truck_volume=(pending_truck_volume),
    )

    return demand_state, recovered_paths


def build_operational_execution_snapshot(
    instance: ExperimentInstance,
    operational_state: RecoveryOperationalState,
    physical_time: int,
) -> ExecutionSnapshot:
    """Build execution using the latest Phase-10 recovery overlay."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        operational_state,
        RecoveryOperationalState,
    ):
        raise TypeError("operational_state must be a RecoveryOperationalState.")

    validated_time = _validate_nonnegative_integer(
        "physical_time",
        physical_time,
    )

    if operational_state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The operational state belongs to another experiment instance.")

    if operational_state.recovery_event_count == 0:
        return build_execution_snapshot(
            instance,
            operational_state.booking_state,
            physical_time=validated_time,
        )

    latest_plans = _latest_plans_by_demand(operational_state)
    recovered_demand_ids = set(latest_plans)

    ordinary_snapshot = build_execution_snapshot(
        instance,
        operational_state.booking_state,
        physical_time=validated_time,
    )

    demand_states: list[AcceptedDemandState] = []
    planned_paths: list[PlannedDemandPath] = []

    for ordinary_state in ordinary_snapshot.demand_states:
        demand_id = ordinary_state.demand.demand_id

        if demand_id not in recovered_demand_ids:
            demand_states.append(ordinary_state)

            planned_paths.extend(
                path for path in ordinary_snapshot.planned_paths if path.demand_id == demand_id
            )
            continue

        recovered_state, recovered_paths = _state_from_recovered_plans(
            instance,
            operational_state,
            demand_id,
            latest_plans[demand_id],
            validated_time,
        )

        demand_states.append(recovered_state)
        planned_paths.extend(recovered_paths)

    return ExecutionSnapshot(
        physical_time=validated_time,
        instance_fingerprint=instance.demand_fingerprint,
        demand_states=tuple(demand_states),
        planned_paths=tuple(planned_paths),
    )


def _truck_immutable_transport_volume_by_arc(
    instance: ExperimentInstance,
    operational_state: RecoveryOperationalState,
    physical_time: int,
) -> dict[str, float]:
    """Return truck-assigned volume that used immutable barge arcs.

    A truck allocation removes the allocated volume from later
    rerouting. Before the transfer, however, any transport movement
    already completed or locked by the recovery decision remains a
    real physical use of barge capacity.

    Only persisted recovery decisions that already exist at the
    requested physical time are considered.
    """
    volume_by_arc: dict[str, float] = defaultdict(float)

    for plan in operational_state.active_fragment_plans:
        if plan.recovery_time > physical_time:
            continue

        transfer = plan.truck_transfer

        if transfer is None:
            continue

        for arc_id in plan.immutable_arc_ids:
            arc = instance.arc_by_id(arc_id)

            if not arc.is_transport:
                continue

            volume_by_arc[arc_id] += float(transfer.volume)

    return dict(volume_by_arc)


def build_operational_transport_capacity_snapshot(
    instance: ExperimentInstance,
    operational_state: RecoveryOperationalState,
    physical_time: int,
) -> TransportCapacitySnapshot:
    """Build nominal capacity from the full operational cargo state."""
    execution = build_operational_execution_snapshot(
        instance,
        operational_state,
        physical_time,
    )

    base_capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    truck_prefix_volume = _truck_immutable_transport_volume_by_arc(
        instance,
        operational_state,
        physical_time,
    )

    if not truck_prefix_volume:
        return base_capacity

    adjusted_arc_states = []

    for arc_state in base_capacity.arc_states:
        extra_volume = truck_prefix_volume.get(
            arc_state.arc_id,
            0.0,
        )

        if extra_volume <= EXECUTION_TOLERANCE:
            adjusted_arc_states.append(arc_state)
            continue

        arc = instance.arc_by_id(arc_state.arc_id)

        committed_volume = arc_state.committed_volume + extra_volume

        if arc.head[1] <= physical_time:
            adjusted_arc_states.append(
                replace(
                    arc_state,
                    committed_volume=(committed_volume),
                    completed_volume=(arc_state.completed_volume + extra_volume),
                )
            )
            continue

        if arc.tail[1] < physical_time < arc.head[1]:
            adjusted_arc_states.append(
                replace(
                    arc_state,
                    committed_volume=(committed_volume),
                    in_transit_volume=(arc_state.in_transit_volume + extra_volume),
                )
            )
            continue

        raise ValueError(
            "A truck-assigned immutable transport arc cannot still be future-bookable."
        )

    return TransportCapacitySnapshot(
        physical_time=(base_capacity.physical_time),
        instance_fingerprint=(base_capacity.instance_fingerprint),
        arc_states=tuple(adjusted_arc_states),
    )
