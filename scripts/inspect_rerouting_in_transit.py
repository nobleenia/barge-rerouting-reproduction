"""Demonstrate irreversible in-transit fragment state."""

from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    build_rerouting_capacity_snapshot,
    build_rerouting_decision_snapshot,
    detect_reroutable_demands,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def main() -> None:
    """Show a fragment onboard a long-duration service."""
    config = load_experiment_config(Path("tests/fixtures/long_leg_experiment.yaml"))
    instance = assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "C",
                0,
                0,
                3,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                1,
                "B",
                "C",
                1,
                2,
                3,
                CustomerCategory.REGULAR,
                20,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    first_event = timeline.event_at_sequence(1)
    artifacts = build_sequential_booking_model(
        instance,
        state,
        first_event,
    )
    solution = solve_sequential_booking_model(artifacts)
    state = apply_sequential_booking_solution(
        artifacts,
        solution,
    )

    current_event = timeline.event_at_sequence(2)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution,
        current_event,
    )
    decision = build_rerouting_decision_snapshot(
        instance,
        capacity,
        eligibility,
    )
    released = build_rerouting_capacity_snapshot(
        instance,
        capacity,
        eligibility,
    )

    fragment = decision.fragments[0]

    print("Phase 7 locked in-transit movement")
    print(f"Physical time:            {decision.physical_time}")
    print(f"Stored fragment node:     {fragment.fragment_state.current_node}")
    print(f"Completed arcs:           {fragment.completed_arc_ids}")
    print(f"Locked in-transit arc:    {fragment.locked_in_transit_arc_id}")
    print(f"Effective reroute source: {fragment.rerouting_source}")
    print(f"Releasable future arcs:   {fragment.releasable_future_transport_arc_ids}")
    print(f"Released-capacity arcs:   {released.available_arc_ids}")


if __name__ == "__main__":
    main()
