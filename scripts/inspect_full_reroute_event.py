"""Demonstrate one complete Full-Reroute event pipeline."""

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
    run_full_reroute_event,
)
from barge_rerouting.rolling_horizon import (
    DemandCommitment,
    PlannedArcFlow,
    RollingBookingState,
    build_booking_timeline,
    decompose_commitment_paths,
)


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled service arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def main() -> None:
    """Run and display one Full-Reroute event."""
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

    result = run_full_reroute_event(
        instance,
        state,
        timeline.event_at_sequence(2),
    )

    old_after = next(
        commitment
        for commitment in result.state_after.commitments
        if commitment.demand_id == "KOLD"
    )
    new_after = next(
        commitment
        for commitment in result.state_after.commitments
        if commitment.demand_id == "KNEW"
    )

    old_path = decompose_commitment_paths(
        instance,
        old_after,
    )[0]
    new_path = decompose_commitment_paths(
        instance,
        new_after,
    )[0]

    print("Phase 7 Full-Reroute event orchestration")
    print(f"Event:                    {result.event.event_id}")
    print(f"Ordinary acceptance:      {result.ordinary_acceptance_fraction:.0f}")
    print(f"Full-Reroute acceptance:  {result.reroute_acceptance_fraction:.0f}")
    print(f"Rerouted demands:         {result.rerouted_demand_ids}")
    print(f"Released arcs:            {result.released_arc_ids}")
    print(f"KOLD old route:           {('transport::0::S_PREFIX', 'transport::1::S_BOTTLENECK')}")
    print(f"KOLD new route:           {old_path.physical_arc_ids}")
    print(f"KNEW route:               {new_path.physical_arc_ids}")
    print(
        "Processed events:         "
        f"{result.state_before.processed_event_count} -> "
        f"{result.state_after.processed_event_count}"
    )


if __name__ == "__main__":
    main()
