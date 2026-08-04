"""Demonstrate one execution-aware fragment network."""

from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    build_fragment_network_snapshot,
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
    """Build a fragment network after its first service executes."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    config = replace(
        config,
        solver=replace(config.solver, log_output=False),
    )

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
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                1,
                "B",
                "C",
                1,
                1,
                2,
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
    decision = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    released = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    networks = build_fragment_network_snapshot(
        instance,
        decision,
        released,
    )

    fragment = decision.fragments[0]
    index = networks.index_for(fragment.fragment_id)

    transport_services = tuple(
        str(instance.arc_by_id(arc_id).service_id)
        for arc_id in index.feasible_arc_ids
        if instance.arc_by_id(arc_id).is_transport
    )

    print("Phase 7 fragment-specific network")
    print(f"Fragment:             {index.fragment_id}")
    print(f"Original source:       {instance.network_index_for(index.demand_id).source}")
    print(f"Rerouting source:      {index.source}")
    print(f"Destination nodes:     {index.destination_nodes}")
    print(f"Feasible services:     {transport_services}")
    print(f"Physical arc count:    {index.feasible_arc_count}")
    print(f"Delivery arc count:    {len(index.sink_arc_ids)}")
    print(f"Immutable history:     {fragment.immutable_arc_ids}")


if __name__ == "__main__":
    main()
