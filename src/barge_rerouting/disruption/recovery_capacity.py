"""Actual capacity available after releasing recovery fragments."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.capacity import (
    ACTUAL_CAPACITY_TOLERANCE,
    ActualCapacityProfile,
)
from barge_rerouting.disruption.recovery import (
    RecoveryFragmentSnapshot,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)


def _nonnegative(
    name: str,
    value: object,
) -> float:
    """Validate a finite non-negative number."""
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


@dataclass(frozen=True, slots=True)
class RecoveryTransportArcCapacity:
    """Actual future capacity after releasing flexible reservations."""

    arc_id: str
    service_id: str
    nominal_capacity: float
    actual_capacity: float
    ordinary_reserved_volume: float
    released_recovery_volume: float
    fixed_outside_reserved_volume: float
    recovery_available_capacity: float
    fixed_overload_volume: float
    released_fragment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate recovery-capacity identities."""
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

        nominal = _nonnegative(
            "nominal_capacity",
            self.nominal_capacity,
        )
        actual = _nonnegative(
            "actual_capacity",
            self.actual_capacity,
        )
        ordinary_reserved = _nonnegative(
            "ordinary_reserved_volume",
            self.ordinary_reserved_volume,
        )
        released = _nonnegative(
            "released_recovery_volume",
            self.released_recovery_volume,
        )
        fixed = _nonnegative(
            "fixed_outside_reserved_volume",
            self.fixed_outside_reserved_volume,
        )
        available = _nonnegative(
            "recovery_available_capacity",
            self.recovery_available_capacity,
        )
        fixed_overload = _nonnegative(
            "fixed_overload_volume",
            self.fixed_overload_volume,
        )

        if actual - nominal > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Actual capacity cannot exceed nominal capacity.")

        if released - ordinary_reserved > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Released recovery volume cannot exceed ordinary future reservations.")

        expected_fixed = max(
            0.0,
            ordinary_reserved - released,
        )

        if abs(fixed - expected_fixed) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Fixed outside reservation accounting is inconsistent.")

        expected_available = max(
            0.0,
            actual - fixed,
        )
        expected_fixed_overload = max(
            0.0,
            fixed - actual,
        )

        if abs(available - expected_available) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Recovery available capacity is inconsistent.")

        if abs(fixed_overload - expected_fixed_overload) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Fixed overload accounting is inconsistent.")

        if not isinstance(
            self.released_fragment_ids,
            tuple,
        ):
            raise TypeError("released_fragment_ids must be a tuple.")

        fragment_ids = tuple(sorted(self.released_fragment_ids))

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("released_fragment_ids must be unique.")

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
            "ordinary_reserved_volume",
            ordinary_reserved,
        )
        object.__setattr__(
            self,
            "released_recovery_volume",
            released,
        )
        object.__setattr__(
            self,
            "fixed_outside_reserved_volume",
            fixed,
        )
        object.__setattr__(
            self,
            "recovery_available_capacity",
            available,
        )
        object.__setattr__(
            self,
            "fixed_overload_volume",
            fixed_overload,
        )
        object.__setattr__(
            self,
            "released_fragment_ids",
            fragment_ids,
        )

    @property
    def has_fixed_overload(self) -> bool:
        """Return whether non-released reservations exceed actual capacity."""
        return bool(self.fixed_overload_volume > ACTUAL_CAPACITY_TOLERANCE)


@dataclass(frozen=True, slots=True)
class RecoveryCapacitySnapshot:
    """Actual capacities available to one recovery optimisation."""

    event_id: str
    physical_time: int
    instance_fingerprint: str
    arc_states: tuple[RecoveryTransportArcCapacity, ...]

    def __post_init__(self) -> None:
        """Validate snapshot identity."""
        if not isinstance(self.event_id, str):
            raise TypeError("event_id must be a string.")

        event_id = self.event_id.strip()

        if not event_id:
            raise ValueError("event_id must be non-empty.")

        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if not isinstance(self.arc_states, tuple):
            raise TypeError("arc_states must be a tuple.")

        for state in self.arc_states:
            if not isinstance(
                state,
                RecoveryTransportArcCapacity,
            ):
                raise TypeError("Every arc state must be a RecoveryTransportArcCapacity.")

        arc_ids = tuple(state.arc_id for state in self.arc_states)

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Recovery arc identifiers must be unique.")

        object.__setattr__(self, "event_id", event_id)
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
    def available_arc_ids(self) -> tuple[str, ...]:
        """Return future transport arcs in the recovery epoch."""
        return tuple(state.arc_id for state in self.arc_states)

    @property
    def fixed_overload_arc_ids(self) -> tuple[str, ...]:
        """Return capacity failures that were not released."""
        return tuple(state.arc_id for state in self.arc_states if state.has_fixed_overload)

    def state_for(
        self,
        arc_id: str,
    ) -> RecoveryTransportArcCapacity:
        """Return one recovery capacity state."""
        for state in self.arc_states:
            if state.arc_id == arc_id:
                return state

        raise KeyError(f"Unknown recovery arc: {arc_id}")

    def available_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return actual capacity usable after release."""
        return float(self.state_for(arc_id).recovery_available_capacity)


def build_recovery_capacity_snapshot(
    instance: ExperimentInstance,
    ordinary_capacity: TransportCapacitySnapshot,
    actual_capacity: ActualCapacityProfile,
    recovery_fragments: RecoveryFragmentSnapshot,
) -> RecoveryCapacitySnapshot:
    """Release flexible future bookings against actual capacity."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    fingerprint = instance.demand_fingerprint

    snapshots = (
        ordinary_capacity,
        actual_capacity,
        recovery_fragments,
    )

    for snapshot in snapshots:
        if snapshot.instance_fingerprint != fingerprint:
            raise ValueError("Recovery inputs belong to different instances.")

        if snapshot.physical_time != recovery_fragments.physical_time:
            raise ValueError("Recovery inputs must use the same physical time.")

    states: list[RecoveryTransportArcCapacity] = []

    for ordinary_state in ordinary_capacity.arc_states:
        if not ordinary_state.is_bookable:
            continue

        actual_state = actual_capacity.state_for(ordinary_state.arc_id)

        released_fragment_ids: list[str] = []
        released_volume = 0.0

        for fragment in recovery_fragments.fragments:
            if ordinary_state.arc_id not in fragment.releasable_future_transport_arc_ids:
                continue

            released_fragment_ids.append(fragment.fragment_id)
            released_volume += fragment.volume

        ordinary_reserved = float(ordinary_state.future_reserved_volume)

        if released_volume - ordinary_reserved > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError(
                "Released fragment volume exceeds the "
                f"ordinary reservation on {ordinary_state.arc_id}."
            )

        fixed_outside = max(
            0.0,
            ordinary_reserved - released_volume,
        )
        actual_value = float(actual_state.actual_capacity)

        states.append(
            RecoveryTransportArcCapacity(
                arc_id=ordinary_state.arc_id,
                service_id=ordinary_state.service_id,
                nominal_capacity=float(ordinary_state.nominal_capacity),
                actual_capacity=actual_value,
                ordinary_reserved_volume=ordinary_reserved,
                released_recovery_volume=released_volume,
                fixed_outside_reserved_volume=fixed_outside,
                recovery_available_capacity=max(
                    0.0,
                    actual_value - fixed_outside,
                ),
                fixed_overload_volume=max(
                    0.0,
                    fixed_outside - actual_value,
                ),
                released_fragment_ids=tuple(released_fragment_ids),
            )
        )

    return RecoveryCapacitySnapshot(
        event_id=recovery_fragments.event_id,
        physical_time=recovery_fragments.physical_time,
        instance_fingerprint=fingerprint,
        arc_states=tuple(states),
    )
