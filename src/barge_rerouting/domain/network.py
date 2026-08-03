"""Validated domain objects for time-space nodes and arcs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

type TimeSpaceNode = tuple[str, int]


class ArcType(StrEnum):
    """Supported time-space-network arc types."""

    HOLDING = "holding"
    TRANSPORT = "transport"


def validate_time_space_node(
    node: object,
    *,
    field_name: str = "node",
) -> TimeSpaceNode:
    """Validate and normalise a terminal-time node.

    Args:
        node:
            Candidate pair containing a terminal and nonnegative time.
        field_name:
            Name used in validation messages.

    Returns:
        A validated ``(terminal, time)`` tuple.

    Raises:
        TypeError:
            If the value is not a valid terminal-time tuple.
        ValueError:
            If the terminal is empty or the time is negative.
    """
    if not isinstance(node, tuple) or len(node) != 2:
        raise TypeError(f"{field_name} must be a (terminal, time) tuple.")

    terminal, time_period = node

    if not isinstance(terminal, str):
        raise TypeError(f"{field_name} terminal must be a string.")

    if isinstance(time_period, bool) or not isinstance(time_period, int):
        raise TypeError(f"{field_name} time must be an integer.")

    terminal = terminal.strip()

    if not terminal:
        raise ValueError(f"{field_name} terminal must be non-empty.")

    if time_period < 0:
        raise ValueError(f"{field_name} time must be non-negative.")

    return terminal, time_period


@dataclass(frozen=True, slots=True)
class TimeSpaceArc:
    """Immutable, solver-ready representation of a time-space arc.

    Attributes:
        arc_id:
            Unique identifier used for CPLEX variable and constraint indexing.
        tail:
            Departure terminal-time node.
        head:
            Arrival terminal-time node.
        arc_type:
            Holding or scheduled transport.
        nominal_capacity:
            Transport capacity in TEU. ``None`` for uncapacitated holding arcs.
        service_id:
            Scheduled service identifier for transport arcs.
        direction:
            Optional operational direction label.
    """

    arc_id: str
    tail: TimeSpaceNode
    head: TimeSpaceNode
    arc_type: ArcType
    nominal_capacity: float | None
    service_id: str | None = None
    direction: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalise the arc."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        arc_id = self.arc_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        if not isinstance(self.arc_type, ArcType):
            raise TypeError("arc_type must be an ArcType.")

        tail = validate_time_space_node(self.tail, field_name="tail")
        head = validate_time_space_node(self.head, field_name="head")

        if head[1] <= tail[1]:
            raise ValueError("Every arc must move strictly forward in time.")

        service_id = self.service_id
        direction = self.direction

        if service_id is not None:
            if not isinstance(service_id, str):
                raise TypeError("service_id must be a string or None.")
            service_id = service_id.strip()
            if not service_id:
                raise ValueError("service_id must be non-empty when provided.")

        if direction is not None:
            if not isinstance(direction, str):
                raise TypeError("direction must be a string or None.")
            direction = direction.strip()
            if not direction:
                direction = None

        capacity = self.nominal_capacity

        if self.arc_type is ArcType.HOLDING:
            if tail[0] != head[0]:
                raise ValueError("A holding arc must remain at the same physical terminal.")
            if capacity is not None:
                raise ValueError("An uncapacitated holding arc must use nominal_capacity=None.")
            if service_id is not None:
                raise ValueError("A holding arc must not have a service_id.")

        if self.arc_type is ArcType.TRANSPORT:
            if tail[0] == head[0]:
                raise ValueError("A transport arc must connect different physical terminals.")
            if capacity is None:
                raise ValueError("A transport arc requires nominal capacity.")
            if isinstance(capacity, bool) or not isinstance(capacity, (int, float)):
                raise TypeError("nominal_capacity must be a real number.")
            capacity = float(capacity)
            if not isfinite(capacity):
                raise ValueError("nominal_capacity must be finite.")
            if capacity < 0:
                raise ValueError("nominal_capacity must be non-negative.")
            if service_id is None:
                raise ValueError("A transport arc requires a service_id.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "tail", tail)
        object.__setattr__(self, "head", head)
        object.__setattr__(self, "nominal_capacity", capacity)
        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "direction", direction)

    @property
    def duration(self) -> int:
        """Return the number of time periods traversed by the arc."""
        return self.head[1] - self.tail[1]

    @property
    def is_holding(self) -> bool:
        """Return whether the arc represents waiting."""
        return self.arc_type is ArcType.HOLDING

    @property
    def is_transport(self) -> bool:
        """Return whether the arc represents a scheduled service movement."""
        return self.arc_type is ArcType.TRANSPORT
