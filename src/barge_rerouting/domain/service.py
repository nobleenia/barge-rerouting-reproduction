"""Validated scheduled-service domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain.network import TimeSpaceNode


@dataclass(frozen=True, slots=True)
class ScheduledTransportLeg:
    """One scheduled barge movement used to construct the network."""

    service_id: str
    origin: str
    destination: str
    departure_time: int
    arrival_time: int
    capacity: float
    direction: str = "unspecified"

    def __post_init__(self) -> None:
        """Validate and normalise the scheduled leg."""
        if not isinstance(self.service_id, str):
            raise TypeError("service_id must be a string.")
        if not isinstance(self.origin, str):
            raise TypeError("origin must be a string.")
        if not isinstance(self.destination, str):
            raise TypeError("destination must be a string.")
        if not isinstance(self.direction, str):
            raise TypeError("direction must be a string.")

        service_id = self.service_id.strip()
        origin = self.origin.strip()
        destination = self.destination.strip()
        direction = self.direction.strip()

        if not service_id:
            raise ValueError("service_id must be a non-empty string.")
        if not origin:
            raise ValueError("origin must be a non-empty string.")
        if not destination:
            raise ValueError("destination must be a non-empty string.")
        if origin == destination:
            raise ValueError("A transport leg must connect different terminals.")

        if isinstance(self.departure_time, bool) or not isinstance(
            self.departure_time,
            int,
        ):
            raise TypeError("departure_time must be an integer.")

        if isinstance(self.arrival_time, bool) or not isinstance(
            self.arrival_time,
            int,
        ):
            raise TypeError("arrival_time must be an integer.")

        if self.departure_time < 0:
            raise ValueError("departure_time must be non-negative.")

        if self.arrival_time <= self.departure_time:
            raise ValueError("arrival_time must be strictly greater than departure_time.")

        if isinstance(self.capacity, bool) or not isinstance(
            self.capacity,
            (int, float),
        ):
            raise TypeError("capacity must be a real number.")

        capacity = float(self.capacity)

        if not isfinite(capacity):
            raise ValueError("capacity must be finite.")

        if capacity < 0:
            raise ValueError("capacity must be non-negative.")

        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "direction", direction or "unspecified")
        object.__setattr__(self, "capacity", capacity)

    @property
    def tail(self) -> TimeSpaceNode:
        """Return the departure terminal-time node."""
        return self.origin, self.departure_time

    @property
    def head(self) -> TimeSpaceNode:
        """Return the arrival terminal-time node."""
        return self.destination, self.arrival_time

    @property
    def duration(self) -> int:
        """Return the travel duration in discrete time periods."""
        return self.arrival_time - self.departure_time
