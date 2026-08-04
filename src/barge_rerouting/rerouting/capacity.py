"""Capacity accounting after releasing reroutable future reservations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.eligibility import (
    ReroutingEligibilitySnapshot,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)

REROUTING_CAPACITY_TOLERANCE = 1e-6


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

    if numeric_value < -REROUTING_CAPACITY_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric_value)


def _normalise_identifiers(
    value: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate, normalise, and sort unique identifiers."""
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    identifiers: list[str] = []

    for identifier in value:
        if not isinstance(identifier, str):
            raise TypeError(f"Every identifier in {field_name} must be a string.")

        normalised_identifier = identifier.strip()

        if not normalised_identifier:
            raise ValueError(f"Every identifier in {field_name} must be non-empty.")

        identifiers.append(normalised_identifier)

    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{field_name} must not contain duplicates.")

    return tuple(sorted(identifiers))


@dataclass(frozen=True, slots=True)
class ReleasedTransportArcCapacity:
    """Bookable capacity after releasing selected old reservations."""

    arc_id: str
    service_id: str
    physical_time: int
    nominal_capacity: float
    ordinary_bookable_capacity: float
    released_reroutable_volume: float
    fixed_outside_reserved_volume: float
    rerouting_available_capacity: float
    released_fragment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the capacity-release accounting identity."""
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

        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )
        nominal_capacity = _validate_nonnegative_float(
            "nominal_capacity",
            self.nominal_capacity,
        )
        ordinary_bookable_capacity = _validate_nonnegative_float(
            "ordinary_bookable_capacity",
            self.ordinary_bookable_capacity,
        )
        released_reroutable_volume = _validate_nonnegative_float(
            "released_reroutable_volume",
            self.released_reroutable_volume,
        )
        fixed_outside_reserved_volume = _validate_nonnegative_float(
            "fixed_outside_reserved_volume",
            self.fixed_outside_reserved_volume,
        )
        rerouting_available_capacity = _validate_nonnegative_float(
            "rerouting_available_capacity",
            self.rerouting_available_capacity,
        )
        released_fragment_ids = _normalise_identifiers(
            self.released_fragment_ids,
            field_name="released_fragment_ids",
        )

        expected_available_capacity = ordinary_bookable_capacity + released_reroutable_volume

        if (
            abs(rerouting_available_capacity - expected_available_capacity)
            > REROUTING_CAPACITY_TOLERANCE
        ):
            raise ValueError(
                "Rerouting capacity must equal ordinary bookable "
                "capacity plus released reroutable volume."
            )

        accounted_nominal_capacity = fixed_outside_reserved_volume + rerouting_available_capacity

        if abs(accounted_nominal_capacity - nominal_capacity) > REROUTING_CAPACITY_TOLERANCE:
            raise ValueError(
                "Fixed outside reservations and rerouting capacity must reproduce nominal capacity."
            )

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "service_id", service_id)
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
            "ordinary_bookable_capacity",
            ordinary_bookable_capacity,
        )
        object.__setattr__(
            self,
            "released_reroutable_volume",
            released_reroutable_volume,
        )
        object.__setattr__(
            self,
            "fixed_outside_reserved_volume",
            fixed_outside_reserved_volume,
        )
        object.__setattr__(
            self,
            "rerouting_available_capacity",
            rerouting_available_capacity,
        )
        object.__setattr__(
            self,
            "released_fragment_ids",
            released_fragment_ids,
        )

    @property
    def has_released_reservation(self) -> bool:
        """Return whether at least one old reservation was released."""
        return self.released_reroutable_volume > REROUTING_CAPACITY_TOLERANCE


@dataclass(frozen=True, slots=True)
class ReroutingCapacitySnapshot:
    """Released capacities available to one rerouting optimisation."""

    current_event_id: str
    physical_time: int
    instance_fingerprint: str
    released_demand_ids: tuple[str, ...]
    arc_states: tuple[ReleasedTransportArcCapacity, ...]

    def __post_init__(self) -> None:
        """Validate snapshot identity and arc-state consistency."""
        if not isinstance(self.current_event_id, str):
            raise TypeError("current_event_id must be a string.")

        current_event_id = self.current_event_id.strip()

        if not current_event_id:
            raise ValueError("current_event_id must be non-empty.")

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

        released_demand_ids = _normalise_identifiers(
            self.released_demand_ids,
            field_name="released_demand_ids",
        )

        if not isinstance(self.arc_states, tuple):
            raise TypeError("arc_states must be a tuple.")

        arc_states = tuple(self.arc_states)

        for arc_state in arc_states:
            if not isinstance(
                arc_state,
                ReleasedTransportArcCapacity,
            ):
                raise TypeError("Every arc state must be a ReleasedTransportArcCapacity.")

            if arc_state.physical_time != physical_time:
                raise ValueError("Every arc state must use the snapshot time.")

        arc_ids = tuple(arc_state.arc_id for arc_state in arc_states)

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Released-capacity arc identifiers must be unique.")

        object.__setattr__(
            self,
            "current_event_id",
            current_event_id,
        )
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
            "released_demand_ids",
            released_demand_ids,
        )
        object.__setattr__(
            self,
            "arc_states",
            tuple(
                sorted(
                    arc_states,
                    key=lambda state: state.arc_id,
                )
            ),
        )

    @property
    def available_arc_ids(self) -> tuple[str, ...]:
        """Return future transport arcs available to rerouting."""
        return tuple(arc_state.arc_id for arc_state in self.arc_states)

    @property
    def total_released_volume(self) -> float:
        """Return reservations released across transport arcs."""
        return float(sum(arc_state.released_reroutable_volume for arc_state in self.arc_states))

    def state_for(
        self,
        arc_id: str,
    ) -> ReleasedTransportArcCapacity:
        """Return released-capacity state for one future arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for arc_state in self.arc_states:
            if arc_state.arc_id == normalised_arc_id:
                return arc_state

        raise KeyError(f"Transport arc {normalised_arc_id} is not bookable at this rerouting time.")

    def available_capacity_for(
        self,
        arc_id: str,
    ) -> float:
        """Return capacity usable by the joint rerouting model."""
        return float(self.state_for(arc_id).rerouting_available_capacity)

    def released_volume_on(
        self,
        arc_id: str,
    ) -> float:
        """Return old reroutable reservation released from one arc."""
        return float(self.state_for(arc_id).released_reroutable_volume)


def build_rerouting_capacity_snapshot(
    instance: ExperimentInstance,
    ordinary_capacity: TransportCapacitySnapshot,
    eligibility: ReroutingEligibilitySnapshot,
) -> ReroutingCapacitySnapshot:
    """Release old future reservations of selected fragments."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        ordinary_capacity,
        TransportCapacitySnapshot,
    ):
        raise TypeError("ordinary_capacity must be a TransportCapacitySnapshot.")

    if not isinstance(
        eligibility,
        ReroutingEligibilitySnapshot,
    ):
        raise TypeError("eligibility must be a ReroutingEligibilitySnapshot.")

    if ordinary_capacity.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The ordinary capacity snapshot belongs to another instance.")

    if eligibility.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The eligibility snapshot belongs to another instance.")

    if ordinary_capacity.physical_time != eligibility.physical_time:
        raise ValueError("Capacity and eligibility snapshots must use the same physical time.")

    arc_states: list[ReleasedTransportArcCapacity] = []

    for ordinary_arc_state in ordinary_capacity.arc_states:
        if not ordinary_arc_state.is_bookable:
            continue

        released_fragment_ids: list[str] = []
        released_volume = 0.0

        for demand_state in eligibility.reroutable_demands:
            for fragment_state in demand_state.fragments:
                if ordinary_arc_state.arc_id not in fragment_state.old_unexecuted_transport_arc_ids:
                    continue

                released_fragment_ids.append(fragment_state.fragment_id)
                released_volume += fragment_state.volume

        if (
            released_volume - ordinary_arc_state.future_reserved_volume
            > REROUTING_CAPACITY_TOLERANCE
        ):
            raise ValueError(
                "Released reroutable volume exceeds the future "
                f"reservation on {ordinary_arc_state.arc_id}."
            )

        ordinary_bookable_capacity = float(ordinary_arc_state.bookable_residual_capacity)
        rerouting_available_capacity = ordinary_bookable_capacity + released_volume
        fixed_outside_reserved_volume = max(
            0.0,
            float(ordinary_arc_state.nominal_capacity) - rerouting_available_capacity,
        )

        arc_states.append(
            ReleasedTransportArcCapacity(
                arc_id=ordinary_arc_state.arc_id,
                service_id=ordinary_arc_state.service_id,
                physical_time=ordinary_capacity.physical_time,
                nominal_capacity=float(ordinary_arc_state.nominal_capacity),
                ordinary_bookable_capacity=(ordinary_bookable_capacity),
                released_reroutable_volume=released_volume,
                fixed_outside_reserved_volume=(fixed_outside_reserved_volume),
                rerouting_available_capacity=(rerouting_available_capacity),
                released_fragment_ids=tuple(released_fragment_ids),
            )
        )

    return ReroutingCapacitySnapshot(
        current_event_id=eligibility.current_event.event_id,
        physical_time=eligibility.physical_time,
        instance_fingerprint=instance.demand_fingerprint,
        released_demand_ids=(eligibility.reroutable_demand_ids),
        arc_states=tuple(arc_states),
    )
