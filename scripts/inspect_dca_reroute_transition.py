"""Demonstrate persistence of a solved DCA-Reroute event."""

from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.rerouting import (
    apply_dca_reroute_solution,
    build_dca_reroute_model,
    build_fragment_network_snapshot,
    build_rerouting_capacity_snapshot,
    build_rerouting_decision_snapshot,
    detect_reroutable_demands,
    solve_dca_reroute_model,
)
from barge_rerouting.rolling_horizon import (
    DemandCommitment,
    PlannedArcFlow,
    RollingBookingState,
    build_booking_timeline,
    build_execution_snapshot,
    build_transport_capacity_snapshot,
    decompose_commitment_paths,
)


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled service arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def main() -> None:
    """Persist and inspect the controlled rerouting decision."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    old = Demand(
        "KOLD",
        4,
        "A",
        "C",
        0,
        0,
        3,
        CustomerCategory.REGULAR,
        10,
    )
    current = Demand(
        "KNEW",
        4,
        "B",
        "C",
        1,
        1,
        2,
        CustomerCategory.FULLY_SPOT,
        100,
    )
    instance = assemble_experiment_instance(
        config,
        demands=(old, current),
    )
    timeline = build_booking_timeline(instance)

    prefix = service_arc_id(instance, "S_PREFIX")
    bottleneck = service_arc_id(
        instance,
        "S_BOTTLENECK",
    )
    alt1 = service_arc_id(instance, "S_ALT1")
    alt2 = service_arc_id(instance, "S_ALT2")

    old_network = instance.network_index_for("KOLD")
    old_delivery = str(next(arc.arc_id for arc in old_network.sink_arcs if arc.tail == ("C", 2)))

    state = RollingBookingState.empty(instance)
    state = state.advance(
        instance,
        event=timeline.event_at_sequence(1),
        commitment=DemandCommitment(
            decision_sequence=1,
            decision_time=0,
            demand=old,
            acceptance_fraction=1.0,
            planned_arc_flows=(
                PlannedArcFlow(prefix, 4.0),
                PlannedArcFlow(bottleneck, 4.0),
                PlannedArcFlow(old_delivery, 4.0),
            ),
        ),
    )

    event = timeline.event_at_sequence(2)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution,
        event,
    )
    decision = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    rerouting_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    networks = build_fragment_network_snapshot(
        instance,
        decision,
        rerouting_capacity,
    )
    artifacts = build_dca_reroute_model(
        instance,
        state,
        event,
        rerouting_capacity,
        networks,
    )
    solution = solve_dca_reroute_model(artifacts)
    transition = apply_dca_reroute_solution(
        artifacts,
        solution,
    )

    execution_after = build_execution_snapshot(
        instance,
        transition.state_after,
        physical_time=1,
    )
    capacity_after = build_transport_capacity_snapshot(
        instance,
        execution_after,
    )

    old_after = next(
        commitment
        for commitment in transition.state_after.commitments
        if commitment.demand_id == "KOLD"
    )
    current_after = next(
        commitment
        for commitment in transition.state_after.commitments
        if commitment.demand_id == "KNEW"
    )

    old_path = decompose_commitment_paths(
        instance,
        old_after,
    )[0]
    current_path = decompose_commitment_paths(
        instance,
        current_after,
    )[0]

    print("Phase 7 persistent DCA-Reroute transition")
    print(
        "Processed events:       "
        f"{state.processed_event_count} -> "
        f"{transition.state_after.processed_event_count}"
    )
    print(f"KOLD route:            {old_path.physical_arc_ids}")
    print(f"KNEW route:            {current_path.physical_arc_ids}")
    print(
        "KOLD decision metadata: "
        f"sequence={old_after.decision_sequence}, "
        f"time={old_after.decision_time}"
    )
    print(f"S_PREFIX completed:     {capacity_after.state_for(prefix).completed_volume:.1f}")
    print(
        f"S_BOTTLENECK reserved:  {capacity_after.state_for(bottleneck).future_reserved_volume:.1f}"
    )
    print(f"S_ALT1 reserved:        {capacity_after.state_for(alt1).future_reserved_volume:.1f}")
    print(f"S_ALT2 reserved:        {capacity_after.state_for(alt2).future_reserved_volume:.1f}")


if __name__ == "__main__":
    main()
