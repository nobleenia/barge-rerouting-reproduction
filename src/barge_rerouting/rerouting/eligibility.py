"""Detection of accepted demands and fragments eligible for rerouting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from barge_rerouting.domain import (
    AcceptedDemandState,
    DemandFragment,
    TimeSpaceNode,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
)
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    PlannedDemandPath,
)
from barge_rerouting.rolling_horizon.state import RollingBookingState
from barge_rerouting.rolling_horizon.timeline import BookingDecisionEvent

REROUTING_ELIGIBILITY_TOLERANCE = 1e-6


def _validate_positive_finite_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a strictly positive finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric_value


class ReroutingExclusionReason(StrEnum):
    """Reason why one previously accepted commitment is not reroutable."""

    FULLY_DELIVERED = "fully-delivered"
    DEADLINE_PASSED = "deadline-passed"


@dataclass(frozen=True, slots=True)
class ReroutingExclusion:
    """One accepted demand excluded from the current rerouting set."""

    demand_id: str
    reason: ReroutingExclusionReason

    def __post_init__(self) -> None:
        """Validate and normalise exclusion information."""
        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")

        demand_id = self.demand_id.strip()

        if not demand_id:
            raise ValueError("demand_id must be non-empty.")

        if not isinstance(self.reason, ReroutingExclusionReason):
            raise TypeError("reason must be a ReroutingExclusionReason.")

        object.__setattr__(self, "demand_id", demand_id)


@dataclass(frozen=True, slots=True)
class ReroutableFragmentState:
    """Execution and old-plan state of one unfinished cargo fragment."""

    fragment: DemandFragment
    old_path: PlannedDemandPath
    old_unexecuted_arc_ids: tuple[str, ...]
    old_unexecuted_transport_arc_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate fragment and old-plan consistency."""
        if not isinstance(self.fragment, DemandFragment):
            raise TypeError("fragment must be a DemandFragment.")

        if not isinstance(self.old_path, PlannedDemandPath):
            raise TypeError("old_path must be a PlannedDemandPath.")

        if self.fragment.fragment_id != self.old_path.path_id:
            raise ValueError("Fragment identifier must match its decomposed path.")

        if self.fragment.demand_id != self.old_path.demand_id:
            raise ValueError("Fragment and old path must belong to the same demand.")

        if not isinstance(self.old_unexecuted_arc_ids, tuple):
            raise TypeError("old_unexecuted_arc_ids must be a tuple.")

        if not isinstance(
            self.old_unexecuted_transport_arc_ids,
            tuple,
        ):
            raise TypeError("old_unexecuted_transport_arc_ids must be a tuple.")

        old_unexecuted_arc_ids = _normalise_arc_ids(
            self.old_unexecuted_arc_ids,
            field_name="old_unexecuted_arc_ids",
        )
        old_unexecuted_transport_arc_ids = _normalise_arc_ids(
            self.old_unexecuted_transport_arc_ids,
            field_name="old_unexecuted_transport_arc_ids",
        )

        executed_arc_ids = self.fragment.executed_arc_ids
        executed_count = len(executed_arc_ids)

        if self.old_path.physical_arc_ids[:executed_count] != executed_arc_ids:
            raise ValueError("Executed fragment history must be a prefix of its old path.")

        expected_unexecuted_arc_ids = self.old_path.physical_arc_ids[executed_count:]

        if old_unexecuted_arc_ids != expected_unexecuted_arc_ids:
            raise ValueError(
                "Old unexecuted arcs must equal the path suffix after the executed history."
            )

        if not set(old_unexecuted_transport_arc_ids).issubset(old_unexecuted_arc_ids):
            raise ValueError(
                "Old unexecuted transport arcs must be a subset of all "
                "old unexecuted physical arcs."
            )

        object.__setattr__(
            self,
            "old_unexecuted_arc_ids",
            old_unexecuted_arc_ids,
        )
        object.__setattr__(
            self,
            "old_unexecuted_transport_arc_ids",
            old_unexecuted_transport_arc_ids,
        )

    @property
    def fragment_id(self) -> str:
        """Return the deterministic fragment identifier."""
        return str(self.fragment.fragment_id)

    @property
    def demand_id(self) -> str:
        """Return the parent demand identifier."""
        return str(self.fragment.demand_id)

    @property
    def volume(self) -> float:
        """Return fixed unfinished fragment volume."""
        return float(self.fragment.volume)

    @property
    def current_node(self) -> TimeSpaceNode:
        """Return the fragment's actual terminal-time position."""
        return self.fragment.current_node

    @property
    def executed_arc_ids(self) -> tuple[str, ...]:
        """Return immutable historical arcs."""
        return tuple(str(arc_id) for arc_id in self.fragment.executed_arc_ids)

    @property
    def old_delivery_arc_id(self) -> str:
        """Return the delivery arc terminating the old path."""
        return str(self.old_path.delivery_arc_id)


@dataclass(frozen=True, slots=True)
class ReroutableDemandState:
    """One accepted unfinished demand selected for rerouting."""

    commitment: DemandCommitment
    execution_state: AcceptedDemandState
    fragments: tuple[ReroutableFragmentState, ...]

    def __post_init__(self) -> None:
        """Validate accepted-volume and fragment consistency."""
        if not isinstance(self.commitment, DemandCommitment):
            raise TypeError("commitment must be a DemandCommitment.")

        if not isinstance(
            self.execution_state,
            AcceptedDemandState,
        ):
            raise TypeError("execution_state must be an AcceptedDemandState.")

        if self.commitment.demand != self.execution_state.demand:
            raise ValueError("Commitment and execution state must use the same demand.")

        if (
            abs(self.commitment.acceptance_fraction - self.execution_state.acceptance_fraction)
            > REROUTING_ELIGIBILITY_TOLERANCE
        ):
            raise ValueError("Commitment and execution state acceptance fractions differ.")

        if not isinstance(self.fragments, tuple):
            raise TypeError("fragments must be a tuple.")

        if not self.fragments:
            raise ValueError("A reroutable demand requires unfinished fragments.")

        for fragment_state in self.fragments:
            if not isinstance(
                fragment_state,
                ReroutableFragmentState,
            ):
                raise TypeError("Every fragment must be a ReroutableFragmentState.")

            if fragment_state.demand_id != self.commitment.demand_id:
                raise ValueError("Every fragment must belong to the commitment demand.")

        fragment_ids = tuple(fragment_state.fragment_id for fragment_state in self.fragments)

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Reroutable fragment identifiers must be unique.")

        detected_fragment_volume = sum(fragment_state.volume for fragment_state in self.fragments)

        if (
            abs(detected_fragment_volume - self.execution_state.remaining_volume)
            > REROUTING_ELIGIBILITY_TOLERANCE
        ):
            raise ValueError("Detected fragments do not reproduce remaining volume.")

        object.__setattr__(
            self,
            "fragments",
            tuple(
                sorted(
                    self.fragments,
                    key=lambda item: item.fragment_id,
                )
            ),
        )

    @property
    def demand_id(self) -> str:
        """Return the accepted demand identifier."""
        return str(self.commitment.demand_id)

    @property
    def accepted_volume(self) -> float:
        """Return the original fixed accepted quantity."""
        return float(self.commitment.accepted_volume)

    @property
    def remaining_volume(self) -> float:
        """Return accepted volume still requiring delivery."""
        return float(self.execution_state.remaining_volume)

    @property
    def delivered_volume(self) -> float:
        """Return volume delivered before this rerouting decision."""
        return float(self.execution_state.delivered_volume)


@dataclass(frozen=True, slots=True)
class ReroutingEligibilitySnapshot:
    """Reroutable and excluded prior commitments for one current event."""

    current_event: BookingDecisionEvent
    physical_time: int
    instance_fingerprint: str
    reroutable_demands: tuple[ReroutableDemandState, ...]
    exclusions: tuple[ReroutingExclusion, ...]

    def __post_init__(self) -> None:
        """Validate event, time, and demand partition."""
        if not isinstance(
            self.current_event,
            BookingDecisionEvent,
        ):
            raise TypeError("current_event must be a BookingDecisionEvent.")

        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if self.physical_time != self.current_event.decision_time:
            raise ValueError("physical_time must equal the current decision time.")

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.reroutable_demands, tuple):
            raise TypeError("reroutable_demands must be a tuple.")

        if not isinstance(self.exclusions, tuple):
            raise TypeError("exclusions must be a tuple.")

        for demand_state in self.reroutable_demands:
            if not isinstance(
                demand_state,
                ReroutableDemandState,
            ):
                raise TypeError("Every reroutable demand must be a ReroutableDemandState.")

        for exclusion in self.exclusions:
            if not isinstance(exclusion, ReroutingExclusion):
                raise TypeError("Every exclusion must be a ReroutingExclusion.")

        reroutable_ids = tuple(demand_state.demand_id for demand_state in self.reroutable_demands)
        excluded_ids = tuple(exclusion.demand_id for exclusion in self.exclusions)

        if len(set(reroutable_ids)) != len(reroutable_ids):
            raise ValueError("Reroutable demand identifiers must be unique.")

        if len(set(excluded_ids)) != len(excluded_ids):
            raise ValueError("Excluded demand identifiers must be unique.")

        if set(reroutable_ids).intersection(excluded_ids):
            raise ValueError("A demand cannot be reroutable and excluded.")

        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "reroutable_demands",
            tuple(
                sorted(
                    self.reroutable_demands,
                    key=lambda item: (
                        item.commitment.decision_sequence,
                        item.demand_id,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "exclusions",
            tuple(
                sorted(
                    self.exclusions,
                    key=lambda item: item.demand_id,
                )
            ),
        )

    @property
    def reroutable_demand_ids(self) -> tuple[str, ...]:
        """Return selected accepted-demand identifiers."""
        return tuple(demand_state.demand_id for demand_state in self.reroutable_demands)

    @property
    def excluded_demand_ids(self) -> tuple[str, ...]:
        """Return accepted demands excluded from rerouting."""
        return tuple(exclusion.demand_id for exclusion in self.exclusions)

    @property
    def reroutable_fragment_count(self) -> int:
        """Return the number of unfinished fragments selected."""
        return sum(len(demand_state.fragments) for demand_state in self.reroutable_demands)

    def demand_state_for(
        self,
        demand_id: str,
    ) -> ReroutableDemandState:
        """Return one reroutable accepted-demand state."""
        if not isinstance(demand_id, str):
            raise TypeError("demand_id must be a string.")

        normalised_demand_id = demand_id.strip()

        for demand_state in self.reroutable_demands:
            if demand_state.demand_id == normalised_demand_id:
                return demand_state

        raise KeyError(f"Demand {normalised_demand_id} is not reroutable.")


def _normalise_arc_ids(
    value: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate arc identifiers while preserving route order."""
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


def _fragment_state(
    instance: ExperimentInstance,
    fragment: DemandFragment,
    old_path: PlannedDemandPath,
) -> ReroutableFragmentState:
    """Construct one reroutable fragment from execution and path state."""
    executed_arc_ids = fragment.executed_arc_ids
    executed_count = len(executed_arc_ids)

    if old_path.physical_arc_ids[:executed_count] != executed_arc_ids:
        raise ValueError("Executed fragment history is not a prefix of its old path.")

    if executed_arc_ids:
        expected_current_node = instance.arc_by_id(executed_arc_ids[-1]).head
    else:
        expected_current_node = instance.network_index_for(fragment.demand_id).source

    if fragment.current_node != expected_current_node:
        raise ValueError("Fragment current node does not match its executed history.")

    old_unexecuted_arc_ids = old_path.physical_arc_ids[executed_count:]
    old_unexecuted_transport_arc_ids = tuple(
        arc_id for arc_id in old_unexecuted_arc_ids if instance.arc_by_id(arc_id).is_transport
    )

    return ReroutableFragmentState(
        fragment=fragment,
        old_path=old_path,
        old_unexecuted_arc_ids=old_unexecuted_arc_ids,
        old_unexecuted_transport_arc_ids=(old_unexecuted_transport_arc_ids),
    )


def detect_reroutable_demands(
    instance: ExperimentInstance,
    booking_state: RollingBookingState,
    execution_snapshot: ExecutionSnapshot,
    current_event: BookingDecisionEvent,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> ReroutingEligibilitySnapshot:
    """Detect eligible accepted unfinished demands for Full-Reroute."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(booking_state, RollingBookingState):
        raise TypeError("booking_state must be a RollingBookingState.")

    if not isinstance(execution_snapshot, ExecutionSnapshot):
        raise TypeError("execution_snapshot must be an ExecutionSnapshot.")

    if not isinstance(current_event, BookingDecisionEvent):
        raise TypeError("current_event must be a BookingDecisionEvent.")

    validated_tolerance = _validate_positive_finite_float(
        "tolerance",
        tolerance,
    )

    if booking_state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if execution_snapshot.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The execution snapshot belongs to another instance.")

    if current_event.sequence_number != booking_state.next_sequence_number:
        raise ValueError("The current event must be the next unprocessed event.")

    if execution_snapshot.physical_time != current_event.decision_time:
        raise ValueError("Execution snapshot time must equal current decision time.")

    path_by_id = {
        planned_path.path_id: planned_path for planned_path in execution_snapshot.planned_paths
    }

    reroutable_demands: list[ReroutableDemandState] = []
    exclusions: list[ReroutingExclusion] = []

    for commitment in booking_state.commitments:
        if commitment.decision_sequence >= current_event.sequence_number:
            raise ValueError("Rerouting may include only prior commitments.")

        if commitment.acceptance_fraction <= validated_tolerance:
            raise ValueError("Booking state contains a nonpositive commitment.")

        execution_state = execution_snapshot.demand_state_for(commitment.demand_id)

        if execution_state.is_complete:
            exclusions.append(
                ReroutingExclusion(
                    demand_id=commitment.demand_id,
                    reason=(ReroutingExclusionReason.FULLY_DELIVERED),
                )
            )
            continue

        if current_event.decision_time > commitment.demand.due_time:
            exclusions.append(
                ReroutingExclusion(
                    demand_id=commitment.demand_id,
                    reason=(ReroutingExclusionReason.DEADLINE_PASSED),
                )
            )
            continue

        fragment_states: list[ReroutableFragmentState] = []

        for fragment in execution_state.fragments:
            try:
                old_path = path_by_id[fragment.fragment_id]
            except KeyError as error:
                raise ValueError(
                    "Execution snapshot has no path for unfinished "
                    f"fragment {fragment.fragment_id}."
                ) from error

            fragment_states.append(
                _fragment_state(
                    instance,
                    fragment,
                    old_path,
                )
            )

        reroutable_demands.append(
            ReroutableDemandState(
                commitment=commitment,
                execution_state=execution_state,
                fragments=tuple(fragment_states),
            )
        )

    return ReroutingEligibilitySnapshot(
        current_event=current_event,
        physical_time=current_event.decision_time,
        instance_fingerprint=instance.demand_fingerprint,
        reroutable_demands=tuple(reroutable_demands),
        exclusions=tuple(exclusions),
    )
