"""Tests for the combined operational event timeline."""

import pytest

from barge_rerouting.config import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    NetworkConfig,
    SolverConfig,
)
from barge_rerouting.disruption import (
    OperationalEventKind,
    ServiceStatusUpdateEvent,
    build_operational_timeline,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    ScheduledTransportLeg,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)


def build_instance():
    """Build a small instance with simultaneous bookings."""
    config = ExperimentConfig(
        experiment_name="phase10-timeline-test",
        random_seed=10,
        network=NetworkConfig(
            terminals=("A", "B", "C"),
            time_periods=(0, 1, 2, 3, 4, 5, 6),
            transport_legs=(
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="A",
                    destination="B",
                    departure_time=1,
                    arrival_time=2,
                    capacity=10,
                ),
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="B",
                    destination="C",
                    departure_time=2,
                    arrival_time=3,
                    capacity=10,
                ),
                ScheduledTransportLeg(
                    service_id="S2",
                    origin="A",
                    destination="C",
                    departure_time=3,
                    arrival_time=4,
                    capacity=10,
                ),
            ),
        ),
        demand_generation=DemandGenerationConfig(
            number_of_demands=3,
            minimum_volume=1,
            maximum_volume=1,
            minimum_fare_per_teu=10,
            maximum_fare_per_teu=10,
            minimum_reservation_time=0,
            maximum_reservation_time=2,
            minimum_availability_lag=0,
            maximum_availability_lag=0,
            minimum_due_slack=2,
            maximum_due_slack=4,
            customer_mix=CustomerMix(
                regular_probability=1.0,
                partially_spot_probability=0.0,
                fully_spot_probability=0.0,
            ),
        ),
        solver=SolverConfig(
            time_limit_seconds=30,
            relative_mip_gap=0.0,
            log_output=False,
        ),
    )

    return assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "K0",
                1,
                "A",
                "C",
                0,
                0,
                4,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K2",
                1,
                "A",
                "C",
                2,
                2,
                4,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K1",
                1,
                "A",
                "C",
                2,
                2,
                4,
                CustomerCategory.REGULAR,
                10,
            ),
        ),
    )


def test_status_update_precedes_booking_at_same_time() -> None:
    """Bookings must observe a status update at the same epoch."""
    instance = build_instance()

    timeline = build_operational_timeline(
        instance,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=2,
                valid_from=2,
                valid_until=4,
                water_level_factor=0.8,
            ),
        ),
    )

    at_two = timeline.entries_at_time(2)

    assert tuple(entry.kind for entry in at_two) == (
        OperationalEventKind.STATUS_UPDATE,
        OperationalEventKind.BOOKING,
        OperationalEventKind.BOOKING,
    )

    assert tuple(entry.event_id for entry in at_two) == (
        "status::0001::0002",
        "booking::0002::K1",
        "booking::0003::K2",
    )


def test_booking_sequence_is_not_changed() -> None:
    """Operational events must preserve booking numbering."""
    instance = build_instance()

    timeline = build_operational_timeline(
        instance,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=1,
                valid_from=1,
                valid_until=4,
                water_level_factor=0.9,
            ),
        ),
    )

    assert tuple(event.sequence_number for event in timeline.booking_events) == (1, 2, 3)

    assert tuple(event.demand_id for event in timeline.booking_events) == ("K0", "K1", "K2")

    assert timeline.booking_timeline.event_count == 3


def test_operational_sequence_is_independent() -> None:
    """Global event numbering includes both event families."""
    instance = build_instance()

    timeline = build_operational_timeline(
        instance,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=1,
                valid_from=1,
                valid_until=3,
                water_level_factor=0.9,
            ),
            ServiceStatusUpdateEvent(
                sequence_number=2,
                update_time=3,
                valid_from=3,
                valid_until=4,
                water_level_factor=0.8,
            ),
        ),
    )

    assert timeline.event_count == 5
    assert timeline.booking_event_count == 3
    assert timeline.status_update_count == 2

    assert tuple(entry.operational_sequence_number for entry in timeline.entries) == (1, 2, 3, 4, 5)


def test_status_only_times_remain_in_timeline() -> None:
    """Forecast updates need not coincide with bookings."""
    instance = build_instance()

    timeline = build_operational_timeline(
        instance,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=1,
                valid_from=1,
                valid_until=4,
                water_level_factor=0.8,
            ),
        ),
    )

    assert timeline.physical_times == (0, 1, 2)

    entries = timeline.entries_at_time(1)

    assert len(entries) == 1
    assert entries[0].is_status_update
    assert not entries[0].is_booking


def test_known_status_updates_are_time_aware() -> None:
    """Only already-published forecasts are visible."""
    instance = build_instance()

    timeline = build_operational_timeline(
        instance,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=1,
                valid_from=1,
                valid_until=3,
                water_level_factor=0.9,
            ),
            ServiceStatusUpdateEvent(
                sequence_number=2,
                update_time=3,
                valid_from=3,
                valid_until=4,
                water_level_factor=0.7,
            ),
        ),
    )

    assert timeline.known_status_updates(0) == ()

    assert tuple(update.event_id for update in timeline.known_status_updates(2)) == (
        "status::0001::0001",
    )

    assert tuple(update.event_id for update in timeline.known_status_updates(3)) == (
        "status::0001::0001",
        "status::0002::0003",
    )


def test_status_sequences_must_be_chronological() -> None:
    """Status numbering cannot run backwards in time."""
    instance = build_instance()

    with pytest.raises(
        ValueError,
        match="contiguous, chronological",
    ):
        build_operational_timeline(
            instance,
            status_updates=(
                ServiceStatusUpdateEvent(
                    sequence_number=2,
                    update_time=1,
                    valid_from=1,
                    valid_until=3,
                    water_level_factor=0.9,
                ),
                ServiceStatusUpdateEvent(
                    sequence_number=1,
                    update_time=3,
                    valid_from=3,
                    valid_until=4,
                    water_level_factor=0.8,
                ),
            ),
        )
