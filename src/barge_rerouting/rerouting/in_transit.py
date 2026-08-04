"""Irreversible in-transit state used before fragment rerouting."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.domain import (
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.eligibility import (
    ReroutableFragmentState,
    ReroutingEligibilitySnapshot,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
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


def _normalise_arc_ids(
    value: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate arc identifiers while preserving route order."""
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    arc_ids: list[str] = []

    for arc_id in value:
        if not isinstance(arc_id, str):
            raise TypeError(f"Every identifier in {field_name} must be a string.")

        normalised_arc_id = arc_id.strip()

        if not normalised_arc_id:
            raise ValueError(f"Every identifier in {field_name} must be non-empty.")

        arc_ids.append(normalised_arc_id)

    if len(set(arc_ids)) != len(arc_ids):
        raise ValueError(f"{field_name} must not contain duplicates.")

    return tuple(arc_ids)


@dataclass(frozen=True, slots=True)
class ReroutingFragmentDecisionState:
    """Effective rerouting state of one unfinished fragment.

    Completed arcs are stored by the underlying fragment state.

    An already departed but not yet arrived transport arc is represented
    separately as a locked in-transit movement. Rerouting begins only after
    that movement reaches its head node.
    """

    fragment_state: ReroutableFragmentState
    physical_time: int
    rerouting_source: TimeSpaceNode
    locked_in_transit_arc_id: str | None
    releasable_future_transport_arc_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate locked movement and effective rerouting source."""
        if not isinstance(
            self.fragment_state,
            ReroutableFragmentState,
        ):
            raise TypeError("fragment_state must be a ReroutableFragmentState.")

        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )
        rerouting_source = validate_time_space_node(
            self.rerouting_source,
            field_name="rerouting_source",
        )

        locked_arc_id = self.locked_in_transit_arc_id

        if locked_arc_id is not None:
            if not isinstance(locked_arc_id, str):
                raise TypeError("locked_in_transit_arc_id must be a string or None.")

            locked_arc_id = locked_arc_id.strip()

            if not locked_arc_id:
                raise ValueError("locked_in_transit_arc_id must be non-empty when supplied.")

        releasable_arc_ids = _normalise_arc_ids(
            self.releasable_future_transport_arc_ids,
            field_name="releasable_future_transport_arc_ids",
        )

        old_transport_arc_ids = set(self.fragment_state.old_unexecuted_transport_arc_ids)

        if not set(releasable_arc_ids).issubset(old_transport_arc_ids):
            raise ValueError("Releasable transport arcs must belong to the old unexecuted route.")

        if locked_arc_id is not None and locked_arc_id not in old_transport_arc_ids:
            raise ValueError("The locked in-transit arc must belong to the old unexecuted route.")

        if locked_arc_id in releasable_arc_ids:
            raise ValueError("A locked in-transit arc cannot be releasable.")

        if locked_arc_id is None and rerouting_source != self.fragment_state.current_node:
            raise ValueError(
                "Without an in-transit movement, rerouting must begin "
                "at the fragment's current node."
            )

        object.__setattr__(
            self,
            "physical_time",
            physical_time,
        )
        object.__setattr__(
            self,
            "rerouting_source",
            rerouting_source,
        )
        object.__setattr__(
            self,
            "locked_in_transit_arc_id",
            locked_arc_id,
        )
        object.__setattr__(
            self,
            "releasable_future_transport_arc_ids",
            releasable_arc_ids,
        )

    @property
    def fragment_id(self) -> str:
        """Return the fragment identifier."""
        return str(self.fragment_state.fragment_id)

    @property
    def demand_id(self) -> str:
        """Return the parent demand identifier."""
        return str(self.fragment_state.demand_id)

    @property
    def volume(self) -> float:
        """Return the fixed unfinished volume."""
        return float(self.fragment_state.volume)

    @property
    def completed_arc_ids(self) -> tuple[str, ...]:
        """Return movements completed before the decision time."""
        return tuple(str(arc_id) for arc_id in self.fragment_state.executed_arc_ids)

    @property
    def immutable_arc_ids(self) -> tuple[str, ...]:
        """Return completed and locked transport movements."""
        if self.locked_in_transit_arc_id is None:
            return self.completed_arc_ids

        return (
            *self.completed_arc_ids,
            self.locked_in_transit_arc_id,
        )

    @property
    def has_locked_in_transit_movement(self) -> bool:
        """Return whether cargo is currently onboard a service."""
        return self.locked_in_transit_arc_id is not None


@dataclass(frozen=True, slots=True)
class ReroutingDecisionSnapshot:
    """Fragment decision states at one Full-Reroute event."""

    current_event_id: str
    physical_time: int
    instance_fingerprint: str
    fragments: tuple[ReroutingFragmentDecisionState, ...]

    def __post_init__(self) -> None:
        """Validate event and fragment-state consistency."""
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

        if not isinstance(self.fragments, tuple):
            raise TypeError("fragments must be a tuple.")

        fragments = tuple(self.fragments)

        for fragment in fragments:
            if not isinstance(
                fragment,
                ReroutingFragmentDecisionState,
            ):
                raise TypeError("Every fragment must be a ReroutingFragmentDecisionState.")

            if fragment.physical_time != physical_time:
                raise ValueError("Every fragment must use the snapshot time.")

        fragment_ids = tuple(fragment.fragment_id for fragment in fragments)

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Rerouting fragment identifiers must be unique.")

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
            "fragments",
            tuple(
                sorted(
                    fragments,
                    key=lambda fragment: fragment.fragment_id,
                )
            ),
        )

    @property
    def locked_fragment_ids(self) -> tuple[str, ...]:
        """Return fragments currently locked in transport."""
        return tuple(
            fragment.fragment_id
            for fragment in self.fragments
            if fragment.has_locked_in_transit_movement
        )

    def fragment_state_for(
        self,
        fragment_id: str,
    ) -> ReroutingFragmentDecisionState:
        """Return one fragment's effective rerouting state."""
        if not isinstance(fragment_id, str):
            raise TypeError("fragment_id must be a string.")

        normalised_fragment_id = fragment_id.strip()

        for fragment in self.fragments:
            if fragment.fragment_id == normalised_fragment_id:
                return fragment

        raise KeyError(f"Unknown rerouting fragment: {normalised_fragment_id}")


def build_rerouting_decision_snapshot(
    instance: ExperimentInstance,
    ordinary_capacity: TransportCapacitySnapshot,
    eligibility: ReroutingEligibilitySnapshot,
) -> ReroutingDecisionSnapshot:
    """Lock in-transit movements and derive effective fragment sources."""
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
        raise ValueError("The capacity snapshot belongs to another instance.")

    if eligibility.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The eligibility snapshot belongs to another instance.")

    if ordinary_capacity.physical_time != eligibility.physical_time:
        raise ValueError("Capacity and eligibility snapshots must use the same time.")

    fragment_states: list[ReroutingFragmentDecisionState] = []

    for demand_state in eligibility.reroutable_demands:
        for fragment_state in demand_state.fragments:
            locked_arc_ids: list[str] = []
            releasable_arc_ids: list[str] = []

            for arc_id in fragment_state.old_unexecuted_transport_arc_ids:
                capacity_state = ordinary_capacity.state_for(arc_id)

                if capacity_state.is_in_transit:
                    locked_arc_ids.append(arc_id)
                    continue

                if capacity_state.is_bookable:
                    releasable_arc_ids.append(arc_id)
                    continue

                if capacity_state.is_completed:
                    raise ValueError(
                        "An unexecuted fragment suffix contains a "
                        f"completed transport arc: {arc_id}."
                    )

            if len(locked_arc_ids) > 1:
                raise ValueError(
                    "One fragment cannot occupy multiple in-transit services simultaneously."
                )

            locked_arc_id = locked_arc_ids[0] if locked_arc_ids else None

            if locked_arc_id is None:
                rerouting_source = fragment_state.current_node
            else:
                first_unexecuted_transport_arc_id = fragment_state.old_unexecuted_transport_arc_ids[
                    0
                ]

                if locked_arc_id != first_unexecuted_transport_arc_id:
                    raise ValueError(
                        "An in-transit movement must be the first unexecuted transport arc."
                    )

                rerouting_source = instance.arc_by_id(locked_arc_id).head

            fragment_states.append(
                ReroutingFragmentDecisionState(
                    fragment_state=fragment_state,
                    physical_time=eligibility.physical_time,
                    rerouting_source=rerouting_source,
                    locked_in_transit_arc_id=locked_arc_id,
                    releasable_future_transport_arc_ids=tuple(releasable_arc_ids),
                )
            )

    return ReroutingDecisionSnapshot(
        current_event_id=eligibility.current_event.event_id,
        physical_time=eligibility.physical_time,
        instance_fingerprint=instance.demand_fingerprint,
        fragments=tuple(fragment_states),
    )
