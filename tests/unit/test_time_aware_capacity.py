"""Tests for time-aware transport-capacity accounting."""

from dataclasses import replace
from pathlib import Path

import pytest

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


def build_capacity_example():
    """Build one four-TEU A-to-C commitment."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
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
                volume=4.0,
                origin="A",
                destination="C",
                reservation_time=0,
                availability_time=0,
                due_time=2,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10.0,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)
    event = timeline.event_at_sequence(1)

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

    return instance, state


def service_arc_id(instance, service_id: str) -> str:
    """Return one transport arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def capacity_at_time(instance, state, physical_time: int):
    """Build execution and capacity snapshots at one time."""
    execution_snapshot = build_execution_snapshot(
        instance,
        state,
        physical_time=physical_time,
    )

    return build_transport_capacity_snapshot(
        instance,
        execution_snapshot,
    )


def test_time_zero_classifies_both_services_as_future_reserved() -> None:
    """Before departure, reservations reduce bookable capacity."""
    instance, state = build_capacity_example()
    snapshot = capacity_at_time(
        instance,
        state,
        physical_time=0,
    )

    for service_id in ("S1", "S2"):
        arc_state = snapshot.state_for(service_arc_id(instance, service_id))

        assert arc_state.is_bookable
        assert not arc_state.is_completed
        assert not arc_state.is_in_transit
        assert arc_state.future_reserved_volume == pytest.approx(4.0)
        assert arc_state.bookable_residual_capacity == pytest.approx(6.0)
        assert arc_state.completed_volume == pytest.approx(0.0)


def test_time_one_closes_s1_but_keeps_s2_bookable() -> None:
    """An arrived service is closed while a same-time departure remains open."""
    instance, state = build_capacity_example()
    snapshot = capacity_at_time(
        instance,
        state,
        physical_time=1,
    )

    s1_state = snapshot.state_for(service_arc_id(instance, "S1"))
    s2_state = snapshot.state_for(service_arc_id(instance, "S2"))

    assert s1_state.is_completed
    assert not s1_state.is_bookable
    assert s1_state.completed_volume == pytest.approx(4.0)
    assert s1_state.bookable_residual_capacity == pytest.approx(0.0)
    assert s1_state.historical_unused_capacity == pytest.approx(6.0)

    assert not s2_state.is_completed
    assert s2_state.is_bookable
    assert s2_state.future_reserved_volume == pytest.approx(4.0)
    assert s2_state.bookable_residual_capacity == pytest.approx(6.0)


def test_time_two_closes_both_services() -> None:
    """Completed services cannot offer capacity to later bookings."""
    instance, state = build_capacity_example()
    snapshot = capacity_at_time(
        instance,
        state,
        physical_time=2,
    )

    for service_id in ("S1", "S2"):
        arc_state = snapshot.state_for(service_arc_id(instance, service_id))

        assert arc_state.is_completed
        assert not arc_state.is_bookable
        assert arc_state.completed_volume == pytest.approx(4.0)
        assert arc_state.future_reserved_volume == pytest.approx(0.0)
        assert arc_state.bookable_residual_capacity == pytest.approx(0.0)
        assert arc_state.historical_unused_capacity == pytest.approx(6.0)


def test_unused_past_capacity_is_not_reopened() -> None:
    """A departed service remains unavailable even with no committed cargo."""
    instance, _ = build_capacity_example()
    empty_state = RollingBookingState.empty(instance)

    snapshot = capacity_at_time(
        instance,
        empty_state,
        physical_time=2,
    )
    s1_state = snapshot.state_for(service_arc_id(instance, "S1"))

    assert s1_state.committed_volume == pytest.approx(0.0)
    assert s1_state.historical_unused_capacity == pytest.approx(10.0)
    assert s1_state.bookable_residual_capacity == pytest.approx(0.0)


def test_committed_volume_is_not_double_counted() -> None:
    """Each arc's committed volume belongs to exactly one timing category."""
    instance, state = build_capacity_example()

    for physical_time in (0, 1, 2):
        snapshot = capacity_at_time(
            instance,
            state,
            physical_time=physical_time,
        )

        for arc_state in snapshot.arc_states:
            partitioned_volume = (
                arc_state.completed_volume
                + arc_state.in_transit_volume
                + arc_state.future_reserved_volume
            )

            assert partitioned_volume == pytest.approx(arc_state.committed_volume)
            assert arc_state.committed_volume <= arc_state.nominal_capacity + 1e-6


def test_future_unreserved_service_retains_full_capacity() -> None:
    """A future service unused by the demand remains fully bookable."""
    instance, state = build_capacity_example()
    snapshot = capacity_at_time(
        instance,
        state,
        physical_time=0,
    )

    s3_state = snapshot.state_for(service_arc_id(instance, "S3"))

    assert s3_state.is_bookable
    assert s3_state.committed_volume == pytest.approx(0.0)
    assert s3_state.bookable_residual_capacity == pytest.approx(10.0)
