"""Demonstrate persistent accepted bookings and residual capacity."""

from __future__ import annotations

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
    commitment_from_dca_solution,
)


def main() -> None:
    """Solve a controlled plan and persist its booking decisions."""
    config = load_experiment_config("configs/toy_experiment.yaml")

    instance = assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "F001",
                8,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
            Demand(
                "P001",
                6,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                20,
            ),
            Demand(
                "R001",
                4,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
        ),
    )

    solution = solve_dca_model(build_dca_model(instance))
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    service_arc = next(arc for arc in instance.arcs if arc.service_id == "S6")

    print("Booking-commitment persistence demonstration")
    print(
        "Note: the decisions come from one controlled static solution; "
        "sequential re-optimisation is the next checkpoint."
    )
    print()

    for event in timeline.events:
        commitment = commitment_from_dca_solution(
            instance,
            event,
            solution,
        )

        state = state.advance(
            instance,
            event=event,
            commitment=commitment,
        )

        decision = "accepted" if commitment is not None else "rejected"
        accepted_volume = commitment.accepted_volume if commitment is not None else 0.0

        print(
            f"{event.sequence_number:02d} "
            f"| demand={event.demand_id} "
            f"| decision={decision} "
            f"| accepted volume={accepted_volume:.2f} "
            f"| reserved S6="
            f"{state.reserved_transport_volume(instance, service_arc.arc_id):.2f} "
            f"| residual S6="
            f"{state.residual_transport_capacity(instance, service_arc.arc_id):.2f}"
        )

    print()
    print("Accepted commitments:", state.accepted_demand_ids)
    print("Rejected demands:", state.rejected_demand_ids)


if __name__ == "__main__":
    main()
