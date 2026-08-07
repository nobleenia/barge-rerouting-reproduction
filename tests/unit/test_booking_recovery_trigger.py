"""Tests for booking-triggered recovery fragments."""

import pytest
from test_dynamic_booking_capacity import (
    build_status_then_booking_example,
)

from barge_rerouting.disruption import (
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
    build_recovery_fragment_snapshot,
)


def test_booking_event_can_trigger_recovery_snapshot() -> None:
    """FR may reconstruct unfinished cargo at a booking event."""
    example = build_status_then_booking_example()

    try:
        state = example["transition"].state_after
        event = example["current_event"]
        instance = example["instance"]

        execution = build_operational_execution_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )

        capacity = build_operational_transport_capacity_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )

        recovery = build_recovery_fragment_snapshot(
            instance,
            state.booking_state,
            execution,
            capacity,
            event,
        )

        assert recovery.event_id == event.event_id
        assert recovery.physical_time == event.decision_time

        assert recovery.demand_ids == ("K1",)
        assert recovery.total_remaining_volume == pytest.approx(7.0)

        assert len(recovery.fragments) == 1

        fragment = recovery.fragments[0]

        assert fragment.demand_id == "K1"
        assert fragment.volume == pytest.approx(7.0)
    finally:
        example["recovery_artifacts"].model.end()


def test_booking_recovery_releases_only_remaining_barge_volume() -> None:
    """Previously trucked cargo must not re-enter FR recovery."""
    example = build_status_then_booking_example()

    try:
        state = example["transition"].state_after
        event = example["current_event"]
        instance = example["instance"]

        assert state.total_truck_volume == pytest.approx(3.0)

        execution = build_operational_execution_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )

        capacity = build_operational_transport_capacity_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )

        recovery = build_recovery_fragment_snapshot(
            instance,
            state.booking_state,
            execution,
            capacity,
            event,
        )

        # Original acceptance = 10.
        # Status recovery already transferred 3 to truck.
        # Therefore booking-triggered FR sees exactly 7.
        assert recovery.total_remaining_volume == pytest.approx(7.0)

        assert recovery.total_remaining_volume + state.total_truck_volume == pytest.approx(10.0)
    finally:
        example["recovery_artifacts"].model.end()
