"""Demonstrate release of old future reservations."""

from __future__ import annotations

from dataclasses import replace

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    build_rerouting_capacity_snapshot,
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
    """Show ordinary and released capacity for S2 at time one."""
    config = load_experiment_config("configs/toy_experiment.yaml")
    quiet_config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(
        quiet_config,
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                2,
                "A",
                "B",
                0,
                0,
                1,
                CustomerCategory.REGULAR,
                20,
            ),
            Demand(
                "K003",
                1,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.REGULAR,
                30,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    for sequence_number in (1, 2):
        event = timeline.event_at_sequence(sequence_number)
        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)
        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

    current_event = timeline.event_at_sequence(3)
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
        current_event,
    )
    released_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )

    print("Phase 7 rerouting-capacity release")
    print(f"Current event: {current_event.event_id}")
    print(f"Released demands: {released_capacity.released_demand_ids}")
    print()

    for arc_state in released_capacity.arc_states:
        if not arc_state.has_released_reservation:
            continue

        print(f"{arc_state.arc_id} | service={arc_state.service_id}")
        print(f"  nominal={arc_state.nominal_capacity:.2f}")
        print(f"  ordinary-bookable={arc_state.ordinary_bookable_capacity:.2f}")
        print(f"  released-old-reservation={arc_state.released_reroutable_volume:.2f}")
        print(f"  rerouting-available={arc_state.rerouting_available_capacity:.2f}")
        print(f"  fixed-outside-reservation={arc_state.fixed_outside_reserved_volume:.2f}")
        print(f"  released-fragments={arc_state.released_fragment_ids}")


if __name__ == "__main__":
    main()
