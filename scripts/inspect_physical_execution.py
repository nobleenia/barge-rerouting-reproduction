"""Demonstrate physical execution of one accepted two-leg route."""

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
    solve_sequential_booking_model,
)


def main() -> None:
    """Book one A-C demand and inspect execution at times zero, one, and two."""
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
                demand_id="KEXEC",
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

    print("Physical execution demonstration")
    print("Route: A@0 --S1--> B@1 --S2--> C@2 --delivery--> sink")
    print()

    for physical_time in (0, 1, 2):
        snapshot = build_execution_snapshot(
            instance,
            booking_state,
            physical_time=physical_time,
        )
        demand_state = snapshot.demand_state_for("KEXEC")

        print(f"Physical time: {physical_time}")
        print(
            f"  remaining={demand_state.remaining_volume:.2f}, "
            f"delivered={demand_state.delivered_barge_volume:.2f}, "
            f"complete={demand_state.is_complete}"
        )

        if demand_state.fragments:
            for fragment in demand_state.fragments:
                print(
                    f"  fragment={fragment.fragment_id}, "
                    f"location={fragment.current_node}, "
                    f"executed={fragment.executed_arc_ids}"
                )
        else:
            print("  no unfinished fragments")

        for service_id in ("S1", "S2"):
            arc_id = service_arcs[service_id]

            print(
                f"  {service_id}: "
                f"executed="
                f"{snapshot.executed_transport_volume(instance, arc_id):.2f}, "
                f"unexecuted="
                f"{snapshot.unexecuted_transport_volume(instance, arc_id):.2f}"
            )

        print()


if __name__ == "__main__":
    main()
