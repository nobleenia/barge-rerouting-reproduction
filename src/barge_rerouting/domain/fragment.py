"""Domain objects for accepted-demand commitments and unfinished fragments."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain.demand import Demand
from barge_rerouting.domain.network import (
    TimeSpaceArc,
    TimeSpaceNode,
    validate_time_space_node,
)

VOLUME_TOLERANCE = 1e-6


def _validate_nonnegative_finite_number(
    name: str,
    value: object,
) -> float:
    """Validate and return a nonnegative finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return numeric_value


def _validate_positive_finite_number(
    name: str,
    value: object,
) -> float:
    """Validate and return a strictly positive finite number."""
    numeric_value = _validate_nonnegative_finite_number(name, value)

    if numeric_value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class DemandFragment:
    """One unfinished portion of an accepted transportation demand.

    A demand may contain several fragments when its accepted TEU have been
    split across different executed itineraries or locations.

    Attributes:
        fragment_id:
            Unique identifier for this cargo fragment.
        demand_id:
            Identifier of the original customer demand.
        volume:
            Undelivered volume represented by this fragment.
        current_node:
            Current terminal-time position from which rerouting must begin.
        executed_arc_ids:
            Historical arcs already traversed by this fragment.
    """

    fragment_id: str
    demand_id: str
    volume: float
    current_node: TimeSpaceNode
    executed_arc_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalise fragment attributes."""
        if not isinstance(self.fragment_id, str):
            raise TypeError("fragment_id must be a string.")

        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")

        fragment_id = self.fragment_id.strip()
        demand_id = self.demand_id.strip()

        if not fragment_id:
            raise ValueError("fragment_id must be non-empty.")

        if not demand_id:
            raise ValueError("demand_id must be non-empty.")

        volume = _validate_positive_finite_number("volume", self.volume)
        current_node = validate_time_space_node(
            self.current_node,
            field_name="current_node",
        )

        if not isinstance(self.executed_arc_ids, tuple):
            raise TypeError("executed_arc_ids must be a tuple.")

        executed_arc_ids: list[str] = []

        for arc_id in self.executed_arc_ids:
            if not isinstance(arc_id, str):
                raise TypeError("Every executed arc identifier must be a string.")

            normalised_arc_id = arc_id.strip()

            if not normalised_arc_id:
                raise ValueError("Every executed arc identifier must be non-empty.")

            executed_arc_ids.append(normalised_arc_id)

        if len(set(executed_arc_ids)) != len(executed_arc_ids):
            raise ValueError("A fragment's executed arc history must not contain duplicates.")

        object.__setattr__(self, "fragment_id", fragment_id)
        object.__setattr__(self, "demand_id", demand_id)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "current_node", current_node)
        object.__setattr__(
            self,
            "executed_arc_ids",
            tuple(executed_arc_ids),
        )

    @property
    def current_terminal(self) -> str:
        """Return the physical terminal containing the fragment."""
        return str(self.current_node[0])

    @property
    def current_time(self) -> int:
        """Return the fragment's current time period."""
        return int(self.current_node[1])

    def move_along(self, arc: TimeSpaceArc) -> DemandFragment:
        """Return a new fragment after executing one additional arc.

        The original object remains unchanged because fragments are immutable.

        Args:
            arc:
                Arc whose tail must equal the fragment's current node.

        Returns:
            A new fragment positioned at the arc head.

        Raises:
            ValueError:
                If the arc does not leave the fragment's current node.
        """
        if arc.tail != self.current_node:
            raise ValueError("The executed arc tail must equal the fragment's current node.")

        return DemandFragment(
            fragment_id=self.fragment_id,
            demand_id=self.demand_id,
            volume=self.volume,
            current_node=arc.head,
            executed_arc_ids=(
                *self.executed_arc_ids,
                arc.arc_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class AcceptedDemandState:
    """Current execution state of one positively accepted demand.

    The accounting identity is:

        accepted volume
        =
        remaining barge-fragment volume
        + pending-truck volume
        + barge-delivered volume
        + truck-delivered volume.
    """

    demand: Demand
    acceptance_fraction: float
    fragments: tuple[DemandFragment, ...]
    delivered_barge_volume: float = 0.0
    delivered_truck_volume: float = 0.0
    pending_truck_volume: float = 0.0

    def __post_init__(self) -> None:
        """Validate the commitment and its volume accounting."""
        if not isinstance(self.demand, Demand):
            raise TypeError("demand must be a Demand object.")

        acceptance_fraction = self.demand.normalize_acceptance_fraction(self.acceptance_fraction)

        if acceptance_fraction <= VOLUME_TOLERANCE:
            raise ValueError("AcceptedDemandState requires a positively accepted demand.")

        if not isinstance(self.fragments, tuple):
            raise TypeError("fragments must be a tuple.")

        fragments = tuple(self.fragments)

        delivered_barge_volume = _validate_nonnegative_finite_number(
            "delivered_barge_volume",
            self.delivered_barge_volume,
        )
        delivered_truck_volume = _validate_nonnegative_finite_number(
            "delivered_truck_volume",
            self.delivered_truck_volume,
        )
        pending_truck_volume = _validate_nonnegative_finite_number(
            "pending_truck_volume",
            self.pending_truck_volume,
        )

        fragment_ids = [fragment.fragment_id for fragment in fragments]

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Fragment identifiers must be unique within a demand.")

        for fragment in fragments:
            if not isinstance(fragment, DemandFragment):
                raise TypeError("Every fragment must be a DemandFragment object.")

            if fragment.demand_id != self.demand.demand_id:
                raise ValueError("Every fragment must reference the state's demand identifier.")

            if fragment.current_time < self.demand.availability_time:
                raise ValueError("A fragment cannot exist before the demand availability time.")

        accepted_volume = self.demand.volume * acceptance_fraction
        remaining_volume = sum(fragment.volume for fragment in fragments)

        accounted_volume = (
            remaining_volume
            + pending_truck_volume
            + delivered_barge_volume
            + delivered_truck_volume
        )

        if abs(accounted_volume - accepted_volume) > VOLUME_TOLERANCE:
            raise ValueError(
                "Accepted-volume accounting is inconsistent: "
                f"accepted={accepted_volume}, accounted={accounted_volume}."
            )

        object.__setattr__(
            self,
            "acceptance_fraction",
            acceptance_fraction,
        )
        object.__setattr__(self, "fragments", fragments)
        object.__setattr__(
            self,
            "delivered_barge_volume",
            delivered_barge_volume,
        )
        object.__setattr__(
            self,
            "delivered_truck_volume",
            delivered_truck_volume,
        )
        object.__setattr__(
            self,
            "pending_truck_volume",
            pending_truck_volume,
        )

    @classmethod
    def at_origin(
        cls,
        demand: Demand,
        acceptance_fraction: float,
        *,
        fragment_id: str | None = None,
    ) -> AcceptedDemandState:
        """Create a newly accepted commitment at its origin and availability time."""
        normalised_fraction = demand.normalize_acceptance_fraction(acceptance_fraction)

        if normalised_fraction <= VOLUME_TOLERANCE:
            raise ValueError("A rejected demand does not create an accepted-demand state.")

        accepted_volume = demand.volume * normalised_fraction
        initial_fragment_id = (
            fragment_id if fragment_id is not None else f"{demand.demand_id}::fragment::0"
        )

        fragment = DemandFragment(
            fragment_id=initial_fragment_id,
            demand_id=demand.demand_id,
            volume=accepted_volume,
            current_node=(
                demand.origin,
                demand.availability_time,
            ),
        )

        return cls(
            demand=demand,
            acceptance_fraction=normalised_fraction,
            fragments=(fragment,),
        )

    @property
    def accepted_volume(self) -> float:
        """Return the committed accepted volume."""
        demand_volume: float = float(self.demand.volume)
        acceptance_fraction: float = float(self.acceptance_fraction)

        return demand_volume * acceptance_fraction

    @property
    def remaining_volume(self) -> float:
        """Return total accepted volume not yet delivered."""
        total_volume: float = 0.0

        for fragment in self.fragments:
            total_volume += float(fragment.volume)

        return total_volume + self.pending_truck_volume

    @property
    def delivered_volume(self) -> float:
        """Return total delivered volume across all permitted modes."""
        return self.delivered_barge_volume + self.delivered_truck_volume

    @property
    def is_complete(self) -> bool:
        """Return whether no unfinished fragments remain."""
        return self.remaining_volume <= VOLUME_TOLERANCE
