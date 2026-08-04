"""Tests for execution-aware fragment-specific rerouting networks."""

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


def quiet_toy_config():
    """Load the toy configuration without solver output."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled transport arc ID."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def build_completed_prefix_example():
    """Build K001 after S1 has completed and before S2 departs."""
    instance = assemble_experiment_instance(
        quiet_toy_config(),
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

        assert solution.is_solved

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
    decision = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    released_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    networks = build_fragment_network_snapshot(
        instance,
        decision,
        released_capacity,
    )

    return instance, decision, released_capacity, networks


def build_in_transit_example():
    """Build K001 onboard S_LONG at time one."""
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

    assert solution.is_solved

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
    released_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    networks = build_fragment_network_snapshot(
        instance,
        decision,
        released_capacity,
    )

    return instance, decision, networks


def test_completed_arc_is_absent_from_fragment_network() -> None:
    """S1 is historical and the fragment starts from B at time one."""
    instance, decision, _, networks = build_completed_prefix_example()

    fragment_id = decision.fragments[0].fragment_id
    index = networks.index_for(fragment_id)

    assert index.source == ("B", 1)
    assert ("A", 0) not in tuple(node_index.node for node_index in index.node_flow_indexes)
    assert service_arc_id(instance, "S1") not in index.feasible_arc_ids


def test_future_reachable_service_is_present() -> None:
    """S2 remains a feasible decision arc from B at time one."""
    instance, decision, released_capacity, networks = build_completed_prefix_example()

    fragment_id = decision.fragments[0].fragment_id
    index = networks.index_for(fragment_id)
    s2 = service_arc_id(instance, "S2")

    assert s2 in released_capacity.available_arc_ids
    assert s2 in index.feasible_arc_ids
    assert index.destination_nodes == (("C", 2),)
    assert len(index.sink_arc_ids) == 1


def test_late_service_is_removed_by_deadline() -> None:
    """S4 cannot serve a fragment whose due time is two."""
    instance, decision, _, networks = build_completed_prefix_example()

    index = networks.index_for(decision.fragments[0].fragment_id)

    assert service_arc_id(instance, "S4") not in index.feasible_arc_ids


def test_in_transit_fragment_network_starts_after_arrival() -> None:
    """Locked S_LONG is absent and rerouting begins from B at time two."""
    instance, decision, networks = build_in_transit_example()

    fragment = decision.fragments[0]
    index = networks.index_for(fragment.fragment_id)

    assert index.source == ("B", 2)
    assert service_arc_id(instance, "S_LONG") not in index.feasible_arc_ids
    assert service_arc_id(instance, "S_FUTURE") in index.feasible_arc_ids


def test_fragment_network_construction_is_deterministic() -> None:
    """Repeated construction must produce identical indexes."""
    instance, decision, released_capacity, first = build_completed_prefix_example()

    second = build_fragment_network_snapshot(
        instance,
        decision,
        released_capacity,
    )

    assert first == second
