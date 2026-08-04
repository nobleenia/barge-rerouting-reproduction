"""Demonstrate time-aware capacity accounting."""

from __future__ import annotations

from dataclasses import replace

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
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
    """Book one route and inspect S1/S2 capacity over time."""
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
                demand_id="KCAP",
                volume=4,
                origin="A",
                destination="C",
                reservation_time=0,
                availability_time=0,
                due_time=2,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    booking_state = RollingBookingState.empty(instance)
    event = timeline.event_at_sequence(1)

    artifacts = build_sequential_booking_model(
        instance,
        booking_state,
        event,
    )
    solution = solve_sequential_booking_model(
        artifacts,
    )
    booking_state = apply_sequential_booking_solution(
        artifacts,
        solution,
    )

    service_arcs = {
        str(arc.service_id): arc.arc_id for arc in instance.arcs if arc.service_id in {"S1", "S2"}
    }

    print("Time-aware transport-capacity accounting")
    print("Committed route: 4 TEU on S1 followed by S2")
    print()

    for physical_time in (0, 1, 2):
        execution_snapshot = build_execution_snapshot(
            instance,
            booking_state,
            physical_time=physical_time,
        )
        capacity_snapshot = build_transport_capacity_snapshot(
            instance,
            execution_snapshot,
        )

        print(f"Physical time: {physical_time}")

        for service_id in ("S1", "S2"):
            arc_state = capacity_snapshot.state_for(service_arcs[service_id])

            if arc_state.is_completed:
                timing_status = "completed"
            elif arc_state.is_in_transit:
                timing_status = "in-transit"
            else:
                timing_status = "future/bookable"

            print(
                f"  {service_id}: "
                f"status={timing_status}, "
                f"committed={arc_state.committed_volume:.2f}, "
                f"completed={arc_state.completed_volume:.2f}, "
                f"in-transit={arc_state.in_transit_volume:.2f}, "
                f"future-reserved="
                f"{arc_state.future_reserved_volume:.2f}, "
                f"bookable-residual="
                f"{arc_state.bookable_residual_capacity:.2f}, "
                f"historical-unused="
                f"{arc_state.historical_unused_capacity:.2f}"
            )

        print()


if __name__ == "__main__":
    main()
