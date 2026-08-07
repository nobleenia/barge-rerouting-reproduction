"""Actual bookable capacity after water-level updates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.capacity import (
    ActualCapacityProfile,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)

ACTUAL_BOOKING_CAPACITY_TOLERANCE = 1e-6


def _nonnegative_finite(
    name: str,
    value: object,
) -> float:
    """Validate a finite non-negative value."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric < -ACTUAL_BOOKING_CAPACITY_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric)


@dataclass(frozen=True, slots=True)
class ActualBookableArcCapacity:
    """Actual residual capacity of one scheduled transport arc."""

    arc_id: str
    service_id: str
    nominal_capacity: float
    actual_capacity: float
    future_reserved_volume: float
    bookable_residual_capacity: float
    is_bookable: bool

    def __post_init__(self) -> None:
        """Validate one actual booking-capacity state."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        if not isinstance(self.service_id, str):
            raise TypeError("service_id must be a string.")

        arc_id = self.arc_id.strip()
        service_id = self.service_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        if not service_id:
            raise ValueError("service_id must be non-empty.")

        nominal = _nonnegative_finite(
            "nominal_capacity",
            self.nominal_capacity,
        )
        actual = _nonnegative_finite(
            "actual_capacity",
            self.actual_capacity,
        )
        reserved = _nonnegative_finite(
            "future_reserved_volume",
            self.future_reserved_volume,
        )
        residual = _nonnegative_finite(
            "bookable_residual_capacity",
            self.bookable_residual_capacity,
        )

        if not isinstance(self.is_bookable, bool):
            raise TypeError("is_bookable must be a boolean.")

        if actual - nominal > ACTUAL_BOOKING_CAPACITY_TOLERANCE:
            raise ValueError("Actual capacity cannot exceed nominal capacity.")

        if self.is_bookable:
            if reserved - actual > ACTUAL_BOOKING_CAPACITY_TOLERANCE:
                raise ValueError(
                    "Future reservations exceed current actual "
                    "capacity; disruption recovery must occur "
                    "before another booking."
                )

            expected = max(
                0.0,
                actual - reserved,
            )

            if abs(residual - expected) > ACTUAL_BOOKING_CAPACITY_TOLERANCE:
                raise ValueError(
                    "Actual booking residual must equal actual capacity minus future reservations."
                )
        elif residual > ACTUAL_BOOKING_CAPACITY_TOLERANCE:
            raise ValueError("A departed transport leg cannot retain bookable residual capacity.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(
            self,
            "service_id",
            service_id,
        )
        object.__setattr__(
            self,
            "nominal_capacity",
            nominal,
        )
        object.__setattr__(
            self,
            "actual_capacity",
            actual,
        )
        object.__setattr__(
            self,
            "future_reserved_volume",
            reserved,
        )
        object.__setattr__(
            self,
            "bookable_residual_capacity",
            residual,
        )


@dataclass(frozen=True, slots=True)
class ActualBookableCapacitySnapshot:
    """Actual residual capacities available to one booking epoch."""

    physical_time: int
    instance_fingerprint: str
    arc_states: tuple[ActualBookableArcCapacity, ...]

    def __post_init__(self) -> None:
        """Validate actual booking-capacity snapshot."""
        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if not isinstance(
            self.instance_fingerprint,
            str,
        ):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.arc_states, tuple):
            raise TypeError("arc_states must be a tuple.")

        for state in self.arc_states:
            if not isinstance(
                state,
                ActualBookableArcCapacity,
            ):
                raise TypeError("Every arc state must be an ActualBookableArcCapacity.")

        arc_ids = tuple(state.arc_id for state in self.arc_states)

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Actual booking-capacity arc identifiers must be unique.")

        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "arc_states",
            tuple(
                sorted(
                    self.arc_states,
                    key=lambda state: state.arc_id,
                )
            ),
        )

    def state_for(
        self,
        arc_id: str,
    ) -> ActualBookableArcCapacity:
        """Return one actual booking-capacity state."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised = arc_id.strip()

        for state in self.arc_states:
            if state.arc_id == normalised:
                return state

        raise KeyError(f"Unknown transport arc identifier: {normalised}")

    def bookable_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return actual residual capacity for booking."""
        return float(self.state_for(arc_id).bookable_residual_capacity)

    def as_residual_capacity_overrides(
        self,
    ) -> dict[str, float]:
        """Return residual capacities for the booking solver."""
        return {state.arc_id: float(state.bookable_residual_capacity) for state in self.arc_states}


def build_actual_bookable_capacity_snapshot(
    instance: ExperimentInstance,
    operational_capacity: TransportCapacitySnapshot,
    actual_capacity: ActualCapacityProfile,
) -> ActualBookableCapacitySnapshot:
    """Combine operational reservations with actual capacity."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        operational_capacity,
        TransportCapacitySnapshot,
    ):
        raise TypeError("operational_capacity must be a TransportCapacitySnapshot.")

    if not isinstance(
        actual_capacity,
        ActualCapacityProfile,
    ):
        raise TypeError("actual_capacity must be an ActualCapacityProfile.")

    fingerprint = instance.demand_fingerprint

    if operational_capacity.instance_fingerprint != fingerprint:
        raise ValueError("Operational capacity belongs to another instance.")

    if actual_capacity.instance_fingerprint != fingerprint:
        raise ValueError("Actual capacity belongs to another instance.")

    if operational_capacity.physical_time != actual_capacity.physical_time:
        raise ValueError("Operational and actual capacity must use the same physical time.")

    states: list[ActualBookableArcCapacity] = []

    for ordinary in operational_capacity.arc_states:
        actual = actual_capacity.state_for(ordinary.arc_id)

        if ordinary.is_bookable:
            reserved = float(ordinary.future_reserved_volume)
            actual_value = float(actual.actual_capacity)

            if reserved - actual_value > ACTUAL_BOOKING_CAPACITY_TOLERANCE:
                raise ValueError(
                    "Operational reservations exceed actual "
                    f"capacity on {ordinary.arc_id}; "
                    "run disruption recovery before booking."
                )

            residual = max(
                0.0,
                actual_value - reserved,
            )
        else:
            reserved = 0.0
            actual_value = float(actual.actual_capacity)
            residual = 0.0

        states.append(
            ActualBookableArcCapacity(
                arc_id=ordinary.arc_id,
                service_id=ordinary.service_id,
                nominal_capacity=(ordinary.nominal_capacity),
                actual_capacity=actual_value,
                future_reserved_volume=reserved,
                bookable_residual_capacity=residual,
                is_bookable=ordinary.is_bookable,
            )
        )

    return ActualBookableCapacitySnapshot(
        physical_time=(operational_capacity.physical_time),
        instance_fingerprint=fingerprint,
        arc_states=tuple(states),
    )
