"""Service-status forecast updates for dynamic capacity."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


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


def _validate_water_level_factor(
    value: object,
) -> float:
    """Validate a proportional water-level capacity factor."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("water_level_factor must be a real number.")

    factor = float(value)

    if not isfinite(factor):
        raise ValueError("water_level_factor must be finite.")

    if factor <= 0.0 or factor > 1.0:
        raise ValueError("water_level_factor must be in (0, 1].")

    return factor


def _normalise_service_ids(
    value: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate service identifiers affected by an update."""
    if not isinstance(value, tuple):
        raise TypeError("affected_service_ids must be a tuple.")

    identifiers: list[str] = []

    for identifier in value:
        if not isinstance(identifier, str):
            raise TypeError("Every affected service identifier must be a string.")

        normalised = identifier.strip()

        if not normalised:
            raise ValueError("Affected service identifiers must be non-empty.")

        identifiers.append(normalised)

    if len(set(identifiers)) != len(identifiers):
        raise ValueError("affected_service_ids must not contain duplicates.")

    return tuple(sorted(identifiers))


@dataclass(frozen=True, slots=True)
class ServiceStatusUpdateEvent:
    """One forecast-driven update of service capacities.

    The validity interval is half-open:

    ``[valid_from, valid_until)``.

    An empty ``affected_service_ids`` tuple means that the update
    applies to every scheduled service.
    """

    sequence_number: int
    update_time: int
    valid_from: int
    valid_until: int
    water_level_factor: float
    affected_service_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalise the status event."""
        sequence_number = _validate_positive_integer(
            "sequence_number",
            self.sequence_number,
        )
        update_time = _validate_nonnegative_integer(
            "update_time",
            self.update_time,
        )
        valid_from = _validate_nonnegative_integer(
            "valid_from",
            self.valid_from,
        )
        valid_until = _validate_nonnegative_integer(
            "valid_until",
            self.valid_until,
        )
        factor = _validate_water_level_factor(self.water_level_factor)
        service_ids = _normalise_service_ids(self.affected_service_ids)

        if valid_from < update_time:
            raise ValueError("valid_from must not precede update_time.")

        if valid_until <= valid_from:
            raise ValueError("valid_until must be strictly greater than valid_from.")

        object.__setattr__(
            self,
            "sequence_number",
            sequence_number,
        )
        object.__setattr__(
            self,
            "update_time",
            update_time,
        )
        object.__setattr__(
            self,
            "valid_from",
            valid_from,
        )
        object.__setattr__(
            self,
            "valid_until",
            valid_until,
        )
        object.__setattr__(
            self,
            "water_level_factor",
            factor,
        )
        object.__setattr__(
            self,
            "affected_service_ids",
            service_ids,
        )

    @property
    def event_id(self) -> str:
        """Return a deterministic status-event identifier."""
        return f"status::{self.sequence_number:04d}::{self.update_time:04d}"

    def applies_to_service(
        self,
        service_id: str,
    ) -> bool:
        """Return whether this update affects one service."""
        if not isinstance(service_id, str):
            raise TypeError("service_id must be a string.")

        normalised = service_id.strip()

        if not normalised:
            raise ValueError("service_id must be non-empty.")

        return not self.affected_service_ids or normalised in self.affected_service_ids

    def covers_departure(
        self,
        departure_time: int,
    ) -> bool:
        """Return whether a departure lies in the validity window."""
        validated_time = _validate_nonnegative_integer(
            "departure_time",
            departure_time,
        )

        return bool(self.valid_from <= validated_time < self.valid_until)
