"""Run a controlled event-by-event DCA booking process."""

from __future__ import annotations

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)


def main() -> None:
    """Solve three bookings sequentially under one shared capacity."""
    config = load_experiment_config("configs/toy_experiment.yaml")

    instance = assemble_experiment_instance(
        config,
        demands=(
            Demand(
                demand_id="K001",
                volume=4,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10,
            ),
            Demand(
                demand_id="K002",
                volume=8,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.PARTIALLY_SPOT,
                fare_per_teu=20,
            ),
            Demand(
                demand_id="K003",
                volume=6,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.FULLY_SPOT,
                fare_per_teu=100,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    service_arc = next(arc for arc in instance.arcs if arc.service_id == "S6")

    total_revenue = 0.0

    print("Sequential DCA booking demonstration")
    print(f"Shared capacity: {service_arc.nominal_capacity:.2f} TEU")
    print()

    for event in timeline.events:
        capacity_before = state.residual_transport_capacity(
            instance,
            service_arc.arc_id,
        )

        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)

        if not solution.is_solved:
            print(f"{event.event_id}: no feasible booking decision ({solution.solve_status})")
            break

        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

        acceptance = float(solution.acceptance_fraction or 0.0)
        accepted_volume = event.demand.volume * acceptance
        event_revenue = float(solution.objective_value or 0.0)
        total_revenue += event_revenue

        capacity_after = state.residual_transport_capacity(
            instance,
            service_arc.arc_id,
        )

        print(
            f"{event.sequence_number:02d} "
            f"| demand={event.demand_id} "
            f"| category={event.demand.category.value} "
            f"| requested={event.demand.volume:.2f} "
            f"| residual before={capacity_before:.2f} "
            f"| acceptance={acceptance:.2f} "
            f"| accepted={accepted_volume:.2f} "
            f"| residual after={capacity_after:.2f} "
            f"| revenue={event_revenue:.2f}"
        )

    print()
    print(f"Accepted commitments: {state.accepted_demand_ids}")
    print(f"Rejected demands:     {state.rejected_demand_ids}")
    print(f"Total revenue:        {total_revenue:.2f}")
    print(
        f"Reserved S6:        {state.reserved_transport_volume(instance, service_arc.arc_id):.2f}"
    )
    print(
        f"Residual S6:        {state.residual_transport_capacity(instance, service_arc.arc_id):.2f}"
    )


if __name__ == "__main__":
    main()
