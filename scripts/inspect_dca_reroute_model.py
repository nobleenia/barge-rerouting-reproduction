"""Demonstrate the controlled DCA-Reroute capacity switch."""

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
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def service_arc_id(instance, service_id: str) -> str:
    """Return a scheduled transport arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def main() -> None:
    """Compare ordinary DCA with joint DCA-Reroute."""
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
    delivery_c2 = str(next(arc.arc_id for arc in old_network.sink_arcs if arc.tail == ("C", 2)))

    first_event = timeline.event_at_sequence(1)
    commitment = DemandCommitment(
        decision_sequence=1,
        decision_time=0,
        demand=old,
        acceptance_fraction=1.0,
        planned_arc_flows=(
            PlannedArcFlow(prefix, 4.0),
            PlannedArcFlow(bottleneck, 4.0),
            PlannedArcFlow(delivery_c2, 4.0),
        ),
    )

    state = RollingBookingState.empty(instance)
    state = state.advance(
        instance,
        event=first_event,
        commitment=commitment,
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

    ordinary_artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
        capacity_snapshot=ordinary_capacity,
    )
    ordinary_solution = solve_sequential_booking_model(ordinary_artifacts)

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

    fragment_id = decision.fragments[0].fragment_id

    print("Phase 7 joint DCA-Reroute")
    print(f"Ordinary DCA acceptance: {ordinary_solution.acceptance_fraction:.0f}")
    print(f"Reroute acceptance:      {solution.acceptance_fraction:.0f}")
    print(f"Current on bottleneck:   {solution.current_flow_on(bottleneck):.1f}")
    print(f"Old on bottleneck:       {solution.fragment_flow_on(fragment_id, bottleneck):.1f}")
    print(f"Old on S_ALT1:           {solution.fragment_flow_on(fragment_id, alt1):.1f}")
    print(f"Old on S_ALT2:           {solution.fragment_flow_on(fragment_id, alt2):.1f}")
    print(f"Immutable prefix:        {decision.fragments[0].immutable_arc_ids}")
    print(f"Current revenue:         {solution.objective_value:.1f}")


if __name__ == "__main__":
    main()
