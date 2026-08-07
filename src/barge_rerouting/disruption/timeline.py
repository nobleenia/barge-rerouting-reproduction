"""Combined operational timeline for bookings and service-status updates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)

type OperationalSourceEvent = BookingDecisionEvent | ServiceStatusUpdateEvent


class OperationalEventKind(StrEnum):
    """Kinds of event supported by the operational timeline."""

    STATUS_UPDATE = "status_update"
    BOOKING = "booking"


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    """Validate and return a strictly positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return value


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate and return a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _event_physical_time(
    event: OperationalSourceEvent,
) -> int:
    """Return the physical time represented by one source event."""
    if isinstance(event, ServiceStatusUpdateEvent):
        return int(event.update_time)

    if isinstance(event, BookingDecisionEvent):
        return int(event.decision_time)

    raise TypeError("Operational source events must be booking or service-status events.")


def _event_kind(
    event: OperationalSourceEvent,
) -> OperationalEventKind:
    """Return the kind of one source event."""
    if isinstance(event, ServiceStatusUpdateEvent):
        return OperationalEventKind.STATUS_UPDATE

    if isinstance(event, BookingDecisionEvent):
        return OperationalEventKind.BOOKING

    raise TypeError("Operational source events must be booking or service-status events.")


def _event_local_sequence(
    event: OperationalSourceEvent,
) -> int:
    """Return the event's own booking/status sequence."""
    return int(event.sequence_number)


def _source_sort_key(
    event: OperationalSourceEvent,
) -> tuple[int, int, int]:
    """Return deterministic operational ordering.

    Status changes precede bookings occurring at the same physical
    time so the booking observes the newest service information.
    """
    kind = _event_kind(event)

    priority = 0 if kind is OperationalEventKind.STATUS_UPDATE else 1

    return (
        _event_physical_time(event),
        priority,
        _event_local_sequence(event),
    )


@dataclass(frozen=True, slots=True)
class OperationalTimelineEntry:
    """One globally ordered operational event."""

    operational_sequence_number: int
    physical_time: int
    source_event: OperationalSourceEvent

    def __post_init__(self) -> None:
        """Validate entry identity and source-event time."""
        sequence_number = _validate_positive_integer(
            "operational_sequence_number",
            self.operational_sequence_number,
        )
        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )

        if not isinstance(
            self.source_event,
            (BookingDecisionEvent, ServiceStatusUpdateEvent),
        ):
            raise TypeError(
                "source_event must be a BookingDecisionEvent or ServiceStatusUpdateEvent."
            )

        expected_time = _event_physical_time(self.source_event)

        if physical_time != expected_time:
            raise ValueError("Operational entry physical time must equal its source-event time.")

        object.__setattr__(
            self,
            "operational_sequence_number",
            sequence_number,
        )
        object.__setattr__(
            self,
            "physical_time",
            physical_time,
        )

    @property
    def event_id(self) -> str:
        """Return the source event's deterministic identifier."""
        return str(self.source_event.event_id)

    @property
    def kind(self) -> OperationalEventKind:
        """Return whether this is a status or booking event."""
        return _event_kind(self.source_event)

    @property
    def is_status_update(self) -> bool:
        """Return whether this entry changes service status."""
        return self.kind is OperationalEventKind.STATUS_UPDATE

    @property
    def is_booking(self) -> bool:
        """Return whether this entry is a booking decision."""
        return self.kind is OperationalEventKind.BOOKING

    @property
    def booking_event(
        self,
    ) -> BookingDecisionEvent | None:
        """Return the booking event when applicable."""
        if isinstance(
            self.source_event,
            BookingDecisionEvent,
        ):
            return self.source_event

        return None

    @property
    def status_update(
        self,
    ) -> ServiceStatusUpdateEvent | None:
        """Return the status update when applicable."""
        if isinstance(
            self.source_event,
            ServiceStatusUpdateEvent,
        ):
            return self.source_event

        return None


@dataclass(frozen=True, slots=True)
class OperationalTimeline:
    """Merged status-update and booking-event timeline."""

    entries: tuple[OperationalTimelineEntry, ...]

    def __post_init__(self) -> None:
        """Validate global and source-specific ordering."""
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple.")

        entries = tuple(self.entries)

        for entry in entries:
            if not isinstance(
                entry,
                OperationalTimelineEntry,
            ):
                raise TypeError("Every entry must be an OperationalTimelineEntry.")

        expected_operational_sequences = tuple(range(1, len(entries) + 1))
        actual_operational_sequences = tuple(entry.operational_sequence_number for entry in entries)

        if actual_operational_sequences != expected_operational_sequences:
            raise ValueError("Operational sequence numbers must be contiguous and start at one.")

        event_ids = tuple(entry.event_id for entry in entries)

        if len(set(event_ids)) != len(event_ids):
            raise ValueError("Operational event identifiers must be unique.")

        expected_order = tuple(
            sorted(
                entries,
                key=lambda entry: _source_sort_key(entry.source_event),
            )
        )

        if entries != expected_order:
            raise ValueError(
                "Operational events are not in deterministic time/status/booking order."
            )

        booking_events = tuple(
            entry.source_event
            for entry in entries
            if isinstance(
                entry.source_event,
                BookingDecisionEvent,
            )
        )

        # Reuse the existing BookingTimeline validator. This
        # guarantees that integrating status events has not altered
        # the original booking sequence.
        BookingTimeline(events=booking_events)

        status_updates = tuple(
            entry.source_event
            for entry in entries
            if isinstance(
                entry.source_event,
                ServiceStatusUpdateEvent,
            )
        )

        expected_status_sequences = tuple(range(1, len(status_updates) + 1))
        actual_status_sequences = tuple(update.sequence_number for update in status_updates)

        if actual_status_sequences != expected_status_sequences:
            raise ValueError(
                "Status-update sequence numbers must be "
                "contiguous, chronological, and start at one."
            )

        object.__setattr__(
            self,
            "entries",
            entries,
        )

    @property
    def event_count(self) -> int:
        """Return all operational events."""
        return len(self.entries)

    @property
    def booking_event_count(self) -> int:
        """Return the number of booking decisions."""
        return sum(1 for entry in self.entries if entry.is_booking)

    @property
    def status_update_count(self) -> int:
        """Return the number of status updates."""
        return sum(1 for entry in self.entries if entry.is_status_update)

    @property
    def physical_times(self) -> tuple[int, ...]:
        """Return distinct operational times."""
        return tuple(sorted({entry.physical_time for entry in self.entries}))

    @property
    def booking_events(
        self,
    ) -> tuple[BookingDecisionEvent, ...]:
        """Return booking events in their original sequence."""
        return tuple(
            entry.source_event
            for entry in self.entries
            if isinstance(
                entry.source_event,
                BookingDecisionEvent,
            )
        )

    @property
    def status_updates(
        self,
    ) -> tuple[ServiceStatusUpdateEvent, ...]:
        """Return status updates in chronological sequence."""
        return tuple(
            entry.source_event
            for entry in self.entries
            if isinstance(
                entry.source_event,
                ServiceStatusUpdateEvent,
            )
        )

    @property
    def booking_timeline(self) -> BookingTimeline:
        """Reconstruct the original booking-only timeline."""
        return BookingTimeline(events=self.booking_events)

    def entries_at_time(
        self,
        physical_time: int,
    ) -> tuple[OperationalTimelineEntry, ...]:
        """Return all operational events at one time."""
        validated_time = _validate_nonnegative_integer(
            "physical_time",
            physical_time,
        )

        return tuple(entry for entry in self.entries if entry.physical_time == validated_time)

    def known_status_updates(
        self,
        physical_time: int,
    ) -> tuple[ServiceStatusUpdateEvent, ...]:
        """Return forecasts published by one physical time."""
        validated_time = _validate_nonnegative_integer(
            "physical_time",
            physical_time,
        )

        return tuple(
            update for update in self.status_updates if update.update_time <= validated_time
        )


def _validate_status_updates(
    value: Sequence[ServiceStatusUpdateEvent],
) -> tuple[ServiceStatusUpdateEvent, ...]:
    """Validate status-update input."""
    if isinstance(value, (str, bytes)):
        raise TypeError("status_updates must be a sequence of ServiceStatusUpdateEvent objects.")

    updates = tuple(value)

    for update in updates:
        if not isinstance(
            update,
            ServiceStatusUpdateEvent,
        ):
            raise TypeError("Every status update must be a ServiceStatusUpdateEvent.")

    return updates


def build_operational_timeline(
    instance: ExperimentInstance,
    *,
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
) -> OperationalTimeline:
    """Merge booking decisions and forecast-update events."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    booking_timeline = build_booking_timeline(instance)
    updates = _validate_status_updates(status_updates)

    source_events: tuple[OperationalSourceEvent, ...] = (
        *booking_timeline.events,
        *updates,
    )

    ordered_events = tuple(
        sorted(
            source_events,
            key=_source_sort_key,
        )
    )

    entries = tuple(
        OperationalTimelineEntry(
            operational_sequence_number=sequence_number,
            physical_time=_event_physical_time(event),
            source_event=event,
        )
        for sequence_number, event in enumerate(
            ordered_events,
            start=1,
        )
    )

    return OperationalTimeline(entries=entries)
