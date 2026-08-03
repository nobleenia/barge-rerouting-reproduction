"""Tests for deterministic rolling-horizon booking timelines."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)


def load_toy_instance():
    """Assemble the canonical toy instance."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    return assemble_experiment_instance(config)


def test_canonical_timeline_contains_every_demand_once() -> None:
    """Every canonical demand must produce exactly one booking event."""
    instance = load_toy_instance()
    timeline = build_booking_timeline(instance)

    assert timeline.event_count == instance.demand_count

    event_demand_ids = {event.demand_id for event in timeline.events}
    instance_demand_ids = {demand.demand_id for demand in instance.demands}

    assert event_demand_ids == instance_demand_ids


def test_timeline_is_sorted_by_reservation_time_then_identifier() -> None:
    """Equal-time booking requests use deterministic demand-ID order."""
    timeline = build_booking_timeline(load_toy_instance())

    ordering_keys = tuple(
        (
            event.decision_time,
            event.demand_id,
        )
        for event in timeline.events
    )

    assert ordering_keys == tuple(sorted(ordering_keys))


def test_sequence_numbers_are_contiguous_and_one_based() -> None:
    """Booking sequence must be suitable for rolling iteration."""
    timeline = build_booking_timeline(load_toy_instance())

    assert tuple(event.sequence_number for event in timeline.events) == tuple(
        range(1, timeline.event_count + 1)
    )


def test_event_time_matches_demand_reservation_time() -> None:
    """A request becomes visible at its configured reservation time."""
    timeline = build_booking_timeline(load_toy_instance())

    for event in timeline.events:
        assert event.decision_time == event.demand.reservation_time


def test_visibility_partition_at_one_event() -> None:
    """Prior, current, and future demand sets must form a partition."""
    timeline = build_booking_timeline(load_toy_instance())
    sequence_number = 5

    prior_ids = timeline.prior_demand_ids(sequence_number)
    known_ids = timeline.known_demand_ids(sequence_number)
    future_ids = timeline.future_demand_ids(sequence_number)
    current_id = timeline.event_at_sequence(sequence_number).demand_id

    assert len(prior_ids) == 4
    assert known_ids == (*prior_ids, current_id)
    assert len(known_ids) + len(future_ids) == timeline.event_count
    assert set(known_ids).isdisjoint(future_ids)


def test_same_time_demands_are_processed_sequentially_by_id() -> None:
    """The deterministic tie-breaking assumption must be explicit."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    demands = (
        Demand(
            demand_id="K003",
            volume=1.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=10.0,
        ),
        Demand(
            demand_id="K001",
            volume=1.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=10.0,
        ),
        Demand(
            demand_id="K002",
            volume=1.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=10.0,
        ),
    )

    instance = assemble_experiment_instance(
        config,
        demands=demands,
    )
    timeline = build_booking_timeline(instance)

    assert tuple(event.demand_id for event in timeline.events) == ("K001", "K002", "K003")


def test_events_at_time_returns_only_matching_requests() -> None:
    """Time filtering must not reveal later requests."""
    timeline = build_booking_timeline(load_toy_instance())

    for decision_time in timeline.decision_times:
        matching_events = timeline.events_at_time(decision_time)

        assert matching_events
        assert all(event.decision_time == decision_time for event in matching_events)


def test_event_rejects_time_different_from_reservation() -> None:
    """A booking event cannot reveal a request at the wrong time."""
    demand = Demand(
        demand_id="KTEST",
        volume=1.0,
        origin="B",
        destination="A",
        reservation_time=0,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10.0,
    )

    with pytest.raises(ValueError, match="reservation_time"):
        BookingDecisionEvent(
            sequence_number=1,
            decision_time=1,
            demand=demand,
        )


def test_timeline_rejects_noncontiguous_sequences() -> None:
    """Timeline sequence numbers cannot contain gaps."""
    demand = Demand(
        demand_id="KTEST",
        volume=1.0,
        origin="B",
        destination="A",
        reservation_time=0,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10.0,
    )

    event = BookingDecisionEvent(
        sequence_number=2,
        decision_time=0,
        demand=demand,
    )

    with pytest.raises(ValueError, match="contiguous"):
        BookingTimeline(events=(event,))
