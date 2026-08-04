"""Tests for released capacity used by demand rerouting."""

from dataclasses import replace
from pathlib import Path

import pytest

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


def quiet_config():
    """Load the toy configuration without solver logs."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def build_release_example():
    """Build one unfinished route and one delivered route."""
    instance = assemble_experiment_instance(
        quiet_config(),
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
    released_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )

    return (
        instance,
        state,
        current_event,
        ordinary_capacity,
        eligibility,
        released_capacity,
    )


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled transport arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def test_releases_old_future_reservation_on_s2() -> None:
    """K001's old S2 reservation must become jointly usable."""
    (
        instance,
        _,
        _,
        ordinary_capacity,
        _,
        released_capacity,
    ) = build_release_example()

    s2 = service_arc_id(instance, "S2")
    ordinary_s2 = ordinary_capacity.state_for(s2)
    released_s2 = released_capacity.state_for(s2)

    assert ordinary_s2.future_reserved_volume == pytest.approx(4.0)
    assert ordinary_s2.bookable_residual_capacity == pytest.approx(6.0)

    assert released_s2.released_reroutable_volume == pytest.approx(4.0)
    assert released_s2.rerouting_available_capacity == pytest.approx(10.0)
    assert released_s2.fixed_outside_reserved_volume == pytest.approx(0.0)
    assert released_s2.released_fragment_ids == ("K001::path::0001",)


def test_completed_service_is_not_reopened() -> None:
    """Historical unused S1 capacity must remain unavailable."""
    (
        instance,
        _,
        _,
        _,
        _,
        released_capacity,
    ) = build_release_example()

    s1 = service_arc_id(instance, "S1")

    assert s1 not in released_capacity.available_arc_ids

    with pytest.raises(
        KeyError,
        match="not bookable",
    ):
        released_capacity.available_capacity_for(s1)


def test_release_identity_prevents_double_subtraction() -> None:
    """Ordinary capacity plus old reservation gives rerouting capacity."""
    (
        instance,
        _,
        _,
        _,
        _,
        released_capacity,
    ) = build_release_example()

    s2 = service_arc_id(instance, "S2")
    state = released_capacity.state_for(s2)

    assert (state.ordinary_bookable_capacity + state.released_reroutable_volume) == pytest.approx(
        state.rerouting_available_capacity
    )

    assert (
        state.fixed_outside_reserved_volume + state.rerouting_available_capacity
    ) == pytest.approx(state.nominal_capacity)


def test_same_time_event_releases_both_future_services() -> None:
    """At time zero, both S1 and S2 remain releasable."""
    instance = assemble_experiment_instance(
        quiet_config(),
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
                0,
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

    assert solution.is_solved

    state = apply_sequential_booking_solution(
        artifacts,
        solution,
    )

    current_event = timeline.event_at_sequence(2)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
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

    for service_id in ("S1", "S2"):
        arc_id = service_arc_id(instance, service_id)
        arc_state = released_capacity.state_for(arc_id)

        assert arc_state.released_reroutable_volume == pytest.approx(4.0)
        assert arc_state.rerouting_available_capacity == pytest.approx(10.0)


def test_capacity_release_is_deterministic() -> None:
    """Repeated construction must return an identical snapshot."""
    (
        instance,
        _,
        _,
        ordinary_capacity,
        eligibility,
        first,
    ) = build_release_example()

    second = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )

    assert first == second
