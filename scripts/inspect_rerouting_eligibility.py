"""Demonstrate execution-aware detection of reroutable demand."""

from __future__ import annotations

from dataclasses import replace

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import detect_reroutable_demands
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)


def main() -> None:
    """Build one unfinished and one delivered prior commitment."""
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
    execution_snapshot = build_execution_snapshot(
        instance,
        state,
        physical_time=current_event.decision_time,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )

    print("Phase 7 rerouting eligibility")
    print(f"Current event:       {current_event.event_id}")
    print(f"Physical time:       {eligibility.physical_time}")
    print(f"Reroutable demands: {eligibility.reroutable_demand_ids}")
    print(f"Excluded demands:   {eligibility.excluded_demand_ids}")
    print()

    for demand_state in eligibility.reroutable_demands:
        print(f"Demand {demand_state.demand_id}")
        print(
            f"  accepted={demand_state.accepted_volume:.2f}, "
            f"remaining={demand_state.remaining_volume:.2f}, "
            f"delivered={demand_state.delivered_volume:.2f}"
        )

        for fragment_state in demand_state.fragments:
            executed_services = tuple(
                instance.arc_by_id(arc_id).service_id
                for arc_id in fragment_state.executed_arc_ids
                if instance.arc_by_id(arc_id).is_transport
            )
            future_services = tuple(
                instance.arc_by_id(arc_id).service_id
                for arc_id in (fragment_state.old_unexecuted_transport_arc_ids)
            )

            print(f"  fragment={fragment_state.fragment_id}, volume={fragment_state.volume:.2f}")
            print(f"    current-node={fragment_state.current_node}")
            print(f"    executed-services={executed_services}")
            print(f"    old-future-services={future_services}")

    print()

    for exclusion in eligibility.exclusions:
        print(f"Excluded {exclusion.demand_id}: {exclusion.reason.value}")


if __name__ == "__main__":
    main()
