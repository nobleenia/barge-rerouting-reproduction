"""Deterministic booking-event timelines for rolling-horizon allocation."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.domain import Demand
from barge_rerouting.instance import ExperimentInstance


def _validate_positive_integer(name: str, value: object) -> int:
    """Validate and return a strictly positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return value


def _validate_nonnegative_integer(name: str, value: object) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


@dataclass(frozen=True, slots=True)
class BookingDecisionEvent:
    """One demand-arrival decision in the rolling-horizon sequence."""

    sequence_number: int
    decision_time: int
    demand: Demand

    def __post_init__(self) -> None:
        """Validate the booking event."""
        sequence_number = _validate_positive_integer(
            "sequence_number",
            self.sequence_number,
        )
        decision_time = _validate_nonnegative_integer(
            "decision_time",
            self.decision_time,
        )

        if not isinstance(self.demand, Demand):
            raise TypeError("demand must be a Demand object.")

        if decision_time != self.demand.reservation_time:
            raise ValueError("decision_time must equal the demand reservation_time.")

        object.__setattr__(
            self,
            "sequence_number",
            sequence_number,
        )
        object.__setattr__(
            self,
            "decision_time",
            decision_time,
        )

    @property
    def event_id(self) -> str:
        """Return a deterministic booking-event identifier."""
        return f"booking::{self.sequence_number:04d}::{self.demand.demand_id}"

    @property
    def demand_id(self) -> str:
        """Return the arriving demand identifier."""
        return str(self.demand.demand_id)


@dataclass(frozen=True, slots=True)
class BookingTimeline:
    """Ordered collection of rolling-horizon booking decisions."""

    events: tuple[BookingDecisionEvent, ...]

    def __post_init__(self) -> None:
        """Validate event ordering and demand uniqueness."""
        if not isinstance(self.events, tuple):
            raise TypeError("events must be a tuple.")

        events = tuple(self.events)

        for event in events:
            if not isinstance(event, BookingDecisionEvent):
                raise TypeError("Every timeline event must be a BookingDecisionEvent.")

        expected_sequence_numbers = tuple(range(1, len(events) + 1))
        actual_sequence_numbers = tuple(event.sequence_number for event in events)

        if actual_sequence_numbers != expected_sequence_numbers:
            raise ValueError("Booking-event sequence numbers must be contiguous and start at one.")

        demand_ids = [event.demand_id for event in events]

        if len(set(demand_ids)) != len(demand_ids):
            raise ValueError("Every demand may appear only once in the booking timeline.")

        expected_order = tuple(
            sorted(
                events,
                key=lambda event: (
                    event.decision_time,
                    event.demand_id,
                ),
            )
        )

        if events != expected_order:
            raise ValueError(
                "Booking events must be ordered by decision time and demand identifier."
            )

        object.__setattr__(self, "events", events)

    @property
    def event_count(self) -> int:
        """Return the number of booking decisions."""
        return len(self.events)

    @property
    def decision_times(self) -> tuple[int, ...]:
        """Return distinct booking times in ascending order."""
        return tuple(sorted({event.decision_time for event in self.events}))

    def event_at_sequence(
        self,
        sequence_number: int,
    ) -> BookingDecisionEvent:
        """Return the event with one-based sequence number."""
        validated_sequence = _validate_positive_integer(
            "sequence_number",
            sequence_number,
        )

        for event in self.events:
            if event.sequence_number == validated_sequence:
                return event

        raise KeyError(f"Unknown booking-event sequence: {validated_sequence}")

    def event_for_demand(
        self,
        demand_id: str,
    ) -> BookingDecisionEvent:
        """Return the event associated with one demand."""
        if not isinstance(demand_id, str):
            raise TypeError("demand_id must be a string.")

        normalised_demand_id = demand_id.strip()

        if not normalised_demand_id:
            raise ValueError("demand_id must be non-empty.")

        for event in self.events:
            if event.demand_id == normalised_demand_id:
                return event

        raise KeyError(f"Demand {normalised_demand_id} is not in the timeline.")

    def events_at_time(
        self,
        decision_time: int,
    ) -> tuple[BookingDecisionEvent, ...]:
        """Return all booking events occurring at one time."""
        validated_time = _validate_nonnegative_integer(
            "decision_time",
            decision_time,
        )

        return tuple(event for event in self.events if event.decision_time == validated_time)

    def prior_demand_ids(
        self,
        sequence_number: int,
    ) -> tuple[str, ...]:
        """Return demands processed before one booking event."""
        event = self.event_at_sequence(sequence_number)

        return tuple(
            previous_event.demand_id
            for previous_event in self.events
            if previous_event.sequence_number < event.sequence_number
        )

    def known_demand_ids(
        self,
        sequence_number: int,
    ) -> tuple[str, ...]:
        """Return demands known immediately after the current arrival."""
        event = self.event_at_sequence(sequence_number)

        return tuple(
            known_event.demand_id
            for known_event in self.events
            if known_event.sequence_number <= event.sequence_number
        )

    def future_demand_ids(
        self,
        sequence_number: int,
    ) -> tuple[str, ...]:
        """Return demands not yet revealed after the current event."""
        event = self.event_at_sequence(sequence_number)

        return tuple(
            future_event.demand_id
            for future_event in self.events
            if future_event.sequence_number > event.sequence_number
        )


def build_booking_timeline(
    instance: ExperimentInstance,
) -> BookingTimeline:
    """Create a deterministic sequential timeline from an instance."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    ordered_demands = tuple(
        sorted(
            instance.demands,
            key=lambda demand: (
                demand.reservation_time,
                demand.demand_id,
            ),
        )
    )

    events = tuple(
        BookingDecisionEvent(
            sequence_number=sequence_number,
            decision_time=demand.reservation_time,
            demand=demand,
        )
        for sequence_number, demand in enumerate(
            ordered_demands,
            start=1,
        )
    )

    return BookingTimeline(events=events)
