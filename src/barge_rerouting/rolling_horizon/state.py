"""Immutable persistent state for sequential booking decisions."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
    validate_commitment_against_instance,
)
from barge_rerouting.rolling_horizon.timeline import BookingDecisionEvent


@dataclass(frozen=True, slots=True)
class BookingDecisionRecord:
    """Persistent result of one booking event."""

    event: BookingDecisionEvent
    commitment: DemandCommitment | None

    def __post_init__(self) -> None:
        """Validate event and commitment consistency."""
        if not isinstance(self.event, BookingDecisionEvent):
            raise TypeError("event must be a BookingDecisionEvent.")

        if self.commitment is None:
            return

        if not isinstance(self.commitment, DemandCommitment):
            raise TypeError("commitment must be a DemandCommitment or None.")

        if self.commitment.decision_sequence != self.event.sequence_number:
            raise ValueError("Commitment sequence must match its booking event.")

        if self.commitment.decision_time != self.event.decision_time:
            raise ValueError("Commitment time must match its booking event.")

        if self.commitment.demand != self.event.demand:
            raise ValueError("Commitment demand must match its booking event.")

    @property
    def is_accepted(self) -> bool:
        """Return whether this event created a positive commitment."""
        return self.commitment is not None

    @property
    def demand_id(self) -> str:
        """Return the processed demand identifier."""
        return str(self.event.demand_id)


@dataclass(frozen=True, slots=True)
class RollingBookingState:
    """Persistent sequence of accepted and rejected booking decisions."""

    instance_fingerprint: str
    records: tuple[BookingDecisionRecord, ...] = ()

    def __post_init__(self) -> None:
        """Validate fingerprint and record sequence."""
        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple.")

        records = tuple(self.records)

        for record in records:
            if not isinstance(record, BookingDecisionRecord):
                raise TypeError("Every state record must be a BookingDecisionRecord.")

        expected_sequences = tuple(range(1, len(records) + 1))
        actual_sequences = tuple(record.event.sequence_number for record in records)

        if actual_sequences != expected_sequences:
            raise ValueError("State records must be contiguous and start at sequence one.")

        demand_ids = [record.demand_id for record in records]

        if len(set(demand_ids)) != len(demand_ids):
            raise ValueError("A demand may be processed only once in booking state.")

        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(self, "records", records)

    @classmethod
    def empty(
        cls,
        instance: ExperimentInstance,
    ) -> RollingBookingState:
        """Create an empty state for one canonical experiment instance."""
        if not isinstance(instance, ExperimentInstance):
            raise TypeError("instance must be an ExperimentInstance.")

        return cls(
            instance_fingerprint=instance.demand_fingerprint,
        )

    @property
    def processed_event_count(self) -> int:
        """Return the number of recorded booking decisions."""
        return len(self.records)

    @property
    def next_sequence_number(self) -> int:
        """Return the sequence number expected next."""
        return self.processed_event_count + 1

    @property
    def commitments(self) -> tuple[DemandCommitment, ...]:
        """Return all positive accepted commitments."""
        return tuple(record.commitment for record in self.records if record.commitment is not None)

    @property
    def accepted_demand_ids(self) -> tuple[str, ...]:
        """Return positively accepted demand identifiers."""
        return tuple(commitment.demand_id for commitment in self.commitments)

    @property
    def rejected_demand_ids(self) -> tuple[str, ...]:
        """Return rejected demand identifiers."""
        return tuple(record.demand_id for record in self.records if not record.is_accepted)

    def advance(
        self,
        instance: ExperimentInstance,
        *,
        event: BookingDecisionEvent,
        commitment: DemandCommitment | None,
    ) -> RollingBookingState:
        """Return a new state containing one additional booking decision."""
        if not isinstance(instance, ExperimentInstance):
            raise TypeError("instance must be an ExperimentInstance.")

        if instance.demand_fingerprint != self.instance_fingerprint:
            raise ValueError("The booking state belongs to another experiment instance.")

        if not isinstance(event, BookingDecisionEvent):
            raise TypeError("event must be a BookingDecisionEvent.")

        if event.sequence_number != self.next_sequence_number:
            raise ValueError("Booking decisions must be recorded in sequence order.")

        if commitment is not None:
            report = validate_commitment_against_instance(
                instance,
                commitment,
            )

            if not report.is_valid:
                raise ValueError("The commitment failed independent validation.")

        record = BookingDecisionRecord(
            event=event,
            commitment=commitment,
        )

        return RollingBookingState(
            instance_fingerprint=self.instance_fingerprint,
            records=(*self.records, record),
        )

    def reserved_transport_volume(
        self,
        instance: ExperimentInstance,
        arc_id: str,
    ) -> float:
        """Return total planned commitment on one transport arc."""
        if instance.demand_fingerprint != self.instance_fingerprint:
            raise ValueError("The booking state belongs to another experiment instance.")

        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Reserved capacity is defined only for transport arcs.")

        total_volume: float = 0.0

        for commitment in self.commitments:
            total_volume += commitment.planned_volume_on(arc_id)

        return total_volume

    def residual_transport_capacity(
        self,
        instance: ExperimentInstance,
        arc_id: str,
    ) -> float:
        """Return nominal capacity not reserved by accepted commitments."""
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Residual capacity is defined only for transport arcs.")

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no nominal capacity.")

        residual_capacity = arc.nominal_capacity - self.reserved_transport_volume(instance, arc_id)

        if residual_capacity < -COMMITMENT_TOLERANCE:
            raise ValueError(f"Committed flow exceeds capacity on arc {arc_id}.")

        return float(max(0.0, residual_capacity))
