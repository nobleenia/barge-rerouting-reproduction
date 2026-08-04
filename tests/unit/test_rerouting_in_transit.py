"""Tests for irreversible in-transit fragment movements."""

from pathlib import Path

import pytest

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


def long_leg_config():
    """Load the controlled multi-period transport network."""
    return load_experiment_config(Path("tests/fixtures/long_leg_experiment.yaml"))


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled transport-arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def build_in_transit_example():
    """Build one prior commitment onboard S_LONG at time one."""
    instance = assemble_experiment_instance(
        long_leg_config(),
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
    decision_snapshot = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    released_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )

    return (
        instance,
        execution,
        ordinary_capacity,
        eligibility,
        decision_snapshot,
        released_capacity,
    )


def test_detects_locked_in_transit_service() -> None:
    """S_LONG has departed and must remain irreversible."""
    (
        instance,
        _,
        ordinary_capacity,
        _,
        decision_snapshot,
        _,
    ) = build_in_transit_example()

    s_long = service_arc_id(instance, "S_LONG")
    capacity_state = ordinary_capacity.state_for(s_long)

    assert capacity_state.is_in_transit
    assert not capacity_state.is_bookable
    assert capacity_state.in_transit_volume == pytest.approx(4.0)

    fragment = decision_snapshot.fragments[0]

    assert fragment.locked_in_transit_arc_id == s_long
    assert fragment.has_locked_in_transit_movement
    assert fragment.immutable_arc_ids == (s_long,)


def test_rerouting_begins_after_in_transit_arrival() -> None:
    """Onboard cargo may reroute only from B at time two."""
    (
        _,
        execution,
        _,
        _,
        decision_snapshot,
        _,
    ) = build_in_transit_example()

    stored_fragment = execution.demand_state_for("K001").fragments[0]
    decision_fragment = decision_snapshot.fragments[0]

    assert stored_fragment.current_node == ("A", 0)
    assert stored_fragment.executed_arc_ids == ()

    assert decision_fragment.rerouting_source == ("B", 2)


def test_only_future_service_is_releasable() -> None:
    """S_LONG remains fixed while S_FUTURE may be replanned."""
    (
        instance,
        _,
        _,
        _,
        decision_snapshot,
        released_capacity,
    ) = build_in_transit_example()

    s_long = service_arc_id(instance, "S_LONG")
    s_future = service_arc_id(instance, "S_FUTURE")
    fragment = decision_snapshot.fragments[0]

    assert fragment.releasable_future_transport_arc_ids == (s_future,)

    assert s_long not in released_capacity.available_arc_ids
    assert released_capacity.released_volume_on(s_future) == pytest.approx(4.0)


def test_in_transit_state_is_deterministic() -> None:
    """Repeated reconstruction must produce identical decision state."""
    (
        instance,
        _,
        ordinary_capacity,
        eligibility,
        first,
        _,
    ) = build_in_transit_example()

    second = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )

    assert first == second
