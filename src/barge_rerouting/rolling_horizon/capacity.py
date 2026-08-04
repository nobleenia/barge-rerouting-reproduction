"""Time-aware transport-capacity accounting."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import (
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.execution import (
    EXECUTION_TOLERANCE,
    ExecutionSnapshot,
)


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_nonnegative_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite nonnegative float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value < -EXECUTION_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric_value)


@dataclass(frozen=True, slots=True)
class TransportArcCapacityState:
    """Capacity state of one scheduled transport arc at physical time tau."""

    arc_id: str
    service_id: str
    tail: TimeSpaceNode
    head: TimeSpaceNode
    physical_time: int
    nominal_capacity: float
    committed_volume: float
    completed_volume: float
    in_transit_volume: float
    future_reserved_volume: float
    bookable_residual_capacity: float

    def __post_init__(self) -> None:
        """Validate the capacity-state partition."""
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

        tail = validate_time_space_node(
            self.tail,
            field_name="tail",
        )
        head = validate_time_space_node(
            self.head,
            field_name="head",
        )
        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )

        nominal_capacity = _validate_nonnegative_float(
            "nominal_capacity",
            self.nominal_capacity,
        )
        committed_volume = _validate_nonnegative_float(
            "committed_volume",
            self.committed_volume,
        )
        completed_volume = _validate_nonnegative_float(
            "completed_volume",
            self.completed_volume,
        )
        in_transit_volume = _validate_nonnegative_float(
            "in_transit_volume",
            self.in_transit_volume,
        )
        future_reserved_volume = _validate_nonnegative_float(
            "future_reserved_volume",
            self.future_reserved_volume,
        )
        bookable_residual_capacity = _validate_nonnegative_float(
            "bookable_residual_capacity",
            self.bookable_residual_capacity,
        )

        if committed_volume - nominal_capacity > EXECUTION_TOLERANCE:
            raise ValueError("Committed volume exceeds nominal transport capacity.")

        partitioned_volume = completed_volume + in_transit_volume + future_reserved_volume

        if abs(partitioned_volume - committed_volume) > EXECUTION_TOLERANCE:
            raise ValueError(
                "Completed, in-transit, and future-reserved volume must partition committed volume."
            )

        if head[1] <= physical_time:
            if abs(completed_volume - committed_volume) > EXECUTION_TOLERANCE:
                raise ValueError(
                    "A completed service must classify all committed volume as completed."
                )

            if (
                in_transit_volume > EXECUTION_TOLERANCE
                or future_reserved_volume > EXECUTION_TOLERANCE
                or bookable_residual_capacity > EXECUTION_TOLERANCE
            ):
                raise ValueError(
                    "A completed service cannot retain in-transit, future, or bookable capacity."
                )

        elif tail[1] < physical_time < head[1]:
            if abs(in_transit_volume - committed_volume) > EXECUTION_TOLERANCE:
                raise ValueError(
                    "An in-transit service must classify all committed volume as in transit."
                )

            if (
                completed_volume > EXECUTION_TOLERANCE
                or future_reserved_volume > EXECUTION_TOLERANCE
                or bookable_residual_capacity > EXECUTION_TOLERANCE
            ):
                raise ValueError("An in-transit service cannot be completed, future, or bookable.")

        else:
            if abs(future_reserved_volume - committed_volume) > EXECUTION_TOLERANCE:
                raise ValueError(
                    "A future service must classify all committed volume as future reserved."
                )

            expected_residual = nominal_capacity - future_reserved_volume

            if abs(bookable_residual_capacity - expected_residual) > EXECUTION_TOLERANCE:
                raise ValueError(
                    "Future service residual capacity must equal nominal "
                    "capacity minus future reservations."
                )

            if completed_volume > EXECUTION_TOLERANCE or in_transit_volume > EXECUTION_TOLERANCE:
                raise ValueError("A future service cannot contain completed or in-transit volume.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "tail", tail)
        object.__setattr__(self, "head", head)
        object.__setattr__(
            self,
            "physical_time",
            physical_time,
        )
        object.__setattr__(
            self,
            "nominal_capacity",
            nominal_capacity,
        )
        object.__setattr__(
            self,
            "committed_volume",
            committed_volume,
        )
        object.__setattr__(
            self,
            "completed_volume",
            completed_volume,
        )
        object.__setattr__(
            self,
            "in_transit_volume",
            in_transit_volume,
        )
        object.__setattr__(
            self,
            "future_reserved_volume",
            future_reserved_volume,
        )
        object.__setattr__(
            self,
            "bookable_residual_capacity",
            bookable_residual_capacity,
        )

    @property
    def is_completed(self) -> bool:
        """Return whether the service has arrived."""
        head_time = int(self.head[1])
        physical_time = int(self.physical_time)
        return bool(head_time <= physical_time)

    @property
    def is_in_transit(self) -> bool:
        """Return whether the service has departed but not arrived."""
        tail_time = int(self.tail[1])
        head_time = int(self.head[1])
        physical_time = int(self.physical_time)

        return bool(tail_time < physical_time < head_time)

    @property
    def is_bookable(self) -> bool:
        """Return whether the service has not yet departed."""
        tail_time = int(self.tail[1])
        physical_time = int(self.physical_time)
        return bool(tail_time >= physical_time)

    @property
    def historical_unused_capacity(self) -> float:
        """Return capacity that departed unused on a closed service."""
        if self.is_bookable:
            return 0.0

        return float(
            max(
                0.0,
                self.nominal_capacity - self.committed_volume,
            )
        )


@dataclass(frozen=True, slots=True)
class TransportCapacitySnapshot:
    """Capacity states for all scheduled services at one physical time."""

    physical_time: int
    instance_fingerprint: str
    arc_states: tuple[TransportArcCapacityState, ...]

    def __post_init__(self) -> None:
        """Validate snapshot consistency."""
        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.arc_states, tuple):
            raise TypeError("arc_states must be a tuple.")

        for arc_state in self.arc_states:
            if not isinstance(
                arc_state,
                TransportArcCapacityState,
            ):
                raise TypeError("Every arc state must be a TransportArcCapacityState.")

            if arc_state.physical_time != physical_time:
                raise ValueError("Every arc state must use the snapshot physical time.")

        arc_ids = [arc_state.arc_id for arc_state in self.arc_states]

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Transport-capacity arc identifiers must be unique.")

        object.__setattr__(
            self,
            "physical_time",
            physical_time,
        )
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

    @property
    def completed_committed_volume(self) -> float:
        """Return committed volume on completed services."""
        return float(sum(arc_state.completed_volume for arc_state in self.arc_states))

    @property
    def in_transit_committed_volume(self) -> float:
        """Return committed volume currently in transit."""
        return float(sum(arc_state.in_transit_volume for arc_state in self.arc_states))

    @property
    def future_reserved_volume(self) -> float:
        """Return committed volume on services not yet departed."""
        return float(sum(arc_state.future_reserved_volume for arc_state in self.arc_states))

    @property
    def total_bookable_residual_capacity(self) -> float:
        """Return residual capacity across all future services."""
        return float(sum(arc_state.bookable_residual_capacity for arc_state in self.arc_states))

    def state_for(
        self,
        arc_id: str,
    ) -> TransportArcCapacityState:
        """Return time-aware capacity state for one transport arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for arc_state in self.arc_states:
            if arc_state.arc_id == normalised_arc_id:
                return arc_state

        raise KeyError(f"Unknown transport arc identifier: {normalised_arc_id}")

    def bookable_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return capacity available to a new booking."""
        return float(self.state_for(arc_id).bookable_residual_capacity)


def build_transport_capacity_snapshot(
    instance: ExperimentInstance,
    execution_snapshot: ExecutionSnapshot,
) -> TransportCapacitySnapshot:
    """Construct time-aware capacity states from committed paths."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(execution_snapshot, ExecutionSnapshot):
        raise TypeError("execution_snapshot must be an ExecutionSnapshot.")

    if execution_snapshot.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The execution snapshot belongs to another instance.")

    physical_time = execution_snapshot.physical_time
    arc_states: list[TransportArcCapacityState] = []

    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no capacity.")

        if arc.service_id is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no service identifier.")

        committed_volume = float(
            sum(
                path.volume
                for path in execution_snapshot.planned_paths
                if arc.arc_id in path.physical_arc_ids
            )
        )

        if arc.head[1] <= physical_time:
            completed_volume = committed_volume
            in_transit_volume = 0.0
            future_reserved_volume = 0.0
            bookable_residual_capacity = 0.0

        elif arc.tail[1] < physical_time < arc.head[1]:
            completed_volume = 0.0
            in_transit_volume = committed_volume
            future_reserved_volume = 0.0
            bookable_residual_capacity = 0.0

        else:
            completed_volume = 0.0
            in_transit_volume = 0.0
            future_reserved_volume = committed_volume
            bookable_residual_capacity = float(arc.nominal_capacity) - future_reserved_volume

        arc_states.append(
            TransportArcCapacityState(
                arc_id=arc.arc_id,
                service_id=str(arc.service_id),
                tail=arc.tail,
                head=arc.head,
                physical_time=physical_time,
                nominal_capacity=float(arc.nominal_capacity),
                committed_volume=committed_volume,
                completed_volume=completed_volume,
                in_transit_volume=in_transit_volume,
                future_reserved_volume=future_reserved_volume,
                bookable_residual_capacity=(bookable_residual_capacity),
            )
        )

    return TransportCapacitySnapshot(
        physical_time=physical_time,
        instance_fingerprint=instance.demand_fingerprint,
        arc_states=tuple(arc_states),
    )
