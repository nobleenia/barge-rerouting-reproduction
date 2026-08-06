"""Actual transport capacities under service-status updates."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.domain import (
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.instance import ExperimentInstance

ACTUAL_CAPACITY_TOLERANCE = 1e-6


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


def _validate_nonnegative_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite non-negative float."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric < -ACTUAL_CAPACITY_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric)


def _validate_factor(
    value: object,
) -> float:
    """Validate a water-level capacity factor."""
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


@dataclass(frozen=True, slots=True)
class ActualTransportArcCapacity:
    """Nominal and water-adjusted capacity of one transport arc."""

    arc_id: str
    service_id: str
    tail: TimeSpaceNode
    head: TimeSpaceNode
    physical_time: int
    nominal_capacity: float
    water_level_factor: float
    actual_capacity: float
    source_update_event_id: str | None = None

    def __post_init__(self) -> None:
        """Validate the actual-capacity identity."""
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
        nominal = _validate_nonnegative_float(
            "nominal_capacity",
            self.nominal_capacity,
        )
        factor = _validate_factor(self.water_level_factor)
        actual = _validate_nonnegative_float(
            "actual_capacity",
            self.actual_capacity,
        )

        expected_actual = nominal * factor

        if abs(actual - expected_actual) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError(
                "actual_capacity must equal nominal_capacity times water_level_factor."
            )

        source_event_id = self.source_update_event_id

        if source_event_id is not None:
            if not isinstance(source_event_id, str):
                raise TypeError("source_update_event_id must be a string or None.")

            source_event_id = source_event_id.strip()

            if not source_event_id:
                raise ValueError("source_update_event_id must be non-empty when provided.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(
            self,
            "service_id",
            service_id,
        )
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
            nominal,
        )
        object.__setattr__(
            self,
            "water_level_factor",
            factor,
        )
        object.__setattr__(
            self,
            "actual_capacity",
            actual,
        )
        object.__setattr__(
            self,
            "source_update_event_id",
            source_event_id,
        )

    @property
    def is_future(self) -> bool:
        """Return whether the service has not departed."""
        return bool(self.tail[1] >= self.physical_time)

    @property
    def capacity_reduction(self) -> float:
        """Return nominal capacity lost to the status update."""
        return float(self.nominal_capacity - self.actual_capacity)


@dataclass(frozen=True, slots=True)
class ActualCapacityProfile:
    """Actual capacities known at one operational decision time."""

    physical_time: int
    instance_fingerprint: str
    arc_states: tuple[ActualTransportArcCapacity, ...]

    def __post_init__(self) -> None:
        """Validate profile identity and arc uniqueness."""
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

        for state in self.arc_states:
            if not isinstance(
                state,
                ActualTransportArcCapacity,
            ):
                raise TypeError("Every arc state must be an ActualTransportArcCapacity.")

            if state.physical_time != physical_time:
                raise ValueError("Every arc state must use the profile physical time.")

        arc_ids = tuple(state.arc_id for state in self.arc_states)

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Actual-capacity arc identifiers must be unique.")

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

    def state_for(
        self,
        arc_id: str,
    ) -> ActualTransportArcCapacity:
        """Return actual-capacity state for one arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised = arc_id.strip()

        if not normalised:
            raise ValueError("arc_id must be non-empty.")

        for state in self.arc_states:
            if state.arc_id == normalised:
                return state

        raise KeyError(f"Unknown transport arc identifier: {normalised}")

    def actual_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return the water-adjusted capacity of one arc."""
        return float(self.state_for(arc_id).actual_capacity)

    def nominal_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return the scheduled nominal capacity of one arc."""
        return float(self.state_for(arc_id).nominal_capacity)

    @property
    def affected_arc_ids(self) -> tuple[str, ...]:
        """Return arcs whose actual capacity is below nominal."""
        return tuple(
            state.arc_id
            for state in self.arc_states
            if (state.capacity_reduction > ACTUAL_CAPACITY_TOLERANCE)
        )


def _validate_status_updates(
    updates: Sequence[ServiceStatusUpdateEvent],
) -> tuple[ServiceStatusUpdateEvent, ...]:
    """Validate and deterministically order status updates."""
    if isinstance(updates, (str, bytes)):
        raise TypeError("status_updates must be a sequence of events.")

    normalised = tuple(updates)

    for update in normalised:
        if not isinstance(
            update,
            ServiceStatusUpdateEvent,
        ):
            raise TypeError("Every status update must be a ServiceStatusUpdateEvent.")

    sequence_numbers = tuple(update.sequence_number for update in normalised)

    if len(set(sequence_numbers)) != len(sequence_numbers):
        raise ValueError("Status-update sequence numbers must be unique.")

    return tuple(
        sorted(
            normalised,
            key=lambda update: (
                update.update_time,
                update.sequence_number,
            ),
        )
    )


def _latest_applicable_update(
    *,
    service_id: str,
    departure_time: int,
    physical_time: int,
    updates: tuple[ServiceStatusUpdateEvent, ...],
) -> ServiceStatusUpdateEvent | None:
    """Select the latest known update covering one departure."""
    if departure_time < physical_time:
        return None

    applicable = tuple(
        update
        for update in updates
        if (
            update.update_time <= physical_time
            and update.applies_to_service(service_id)
            and update.covers_departure(departure_time)
        )
    )

    if not applicable:
        return None

    return max(
        applicable,
        key=lambda update: (
            update.update_time,
            update.sequence_number,
        ),
    )


def build_actual_capacity_profile(
    instance: ExperimentInstance,
    *,
    physical_time: int,
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
) -> ActualCapacityProfile:
    """Build actual capacities known at one decision time.

    Updates affect only services that have not yet departed.
    Completed and in-transit service legs retain their historical
    nominal accounting.
    """
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    validated_time = _validate_nonnegative_integer(
        "physical_time",
        physical_time,
    )
    updates = _validate_status_updates(status_updates)
    states: list[ActualTransportArcCapacity] = []

    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no nominal capacity.")

        if arc.service_id is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no service identifier.")

        update = _latest_applicable_update(
            service_id=arc.service_id,
            departure_time=arc.tail[1],
            physical_time=validated_time,
            updates=updates,
        )

        factor = 1.0 if update is None else update.water_level_factor
        actual_capacity = float(arc.nominal_capacity) * factor

        states.append(
            ActualTransportArcCapacity(
                arc_id=arc.arc_id,
                service_id=arc.service_id,
                tail=arc.tail,
                head=arc.head,
                physical_time=validated_time,
                nominal_capacity=float(arc.nominal_capacity),
                water_level_factor=factor,
                actual_capacity=actual_capacity,
                source_update_event_id=(None if update is None else update.event_id),
            )
        )

    return ActualCapacityProfile(
        physical_time=validated_time,
        instance_fingerprint=(instance.demand_fingerprint),
        arc_states=tuple(states),
    )
