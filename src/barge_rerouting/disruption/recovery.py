"""Execution-aware recovery context for service-status changes."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.domain import DemandFragment
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.eligibility import (
    ReroutableFragmentState,
)
from barge_rerouting.rerouting.in_transit import (
    ReroutingFragmentDecisionState,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    PlannedDemandPath,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


@dataclass(frozen=True, slots=True)
class RecoveryFragmentSnapshot:
    """Unfinished accepted fragments at one status-update event."""

    event: ServiceStatusUpdateEvent
    physical_time: int
    instance_fingerprint: str
    fragments: tuple[ReroutingFragmentDecisionState, ...]

    def __post_init__(self) -> None:
        """Validate recovery-event and fragment consistency."""
        if not isinstance(
            self.event,
            ServiceStatusUpdateEvent,
        ):
            raise TypeError("event must be a ServiceStatusUpdateEvent.")

        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if self.physical_time != self.event.update_time:
            raise ValueError("Recovery time must equal status update time.")

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.fragments, tuple):
            raise TypeError("fragments must be a tuple.")

        for fragment in self.fragments:
            if not isinstance(
                fragment,
                ReroutingFragmentDecisionState,
            ):
                raise TypeError("Every recovery fragment must be a ReroutingFragmentDecisionState.")

            if fragment.physical_time != self.physical_time:
                raise ValueError("Every recovery fragment must use the recovery physical time.")

        fragment_ids = tuple(fragment.fragment_id for fragment in self.fragments)

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Recovery fragment identifiers must be unique.")

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
                    self.fragments,
                    key=lambda fragment: fragment.fragment_id,
                )
            ),
        )

    @property
    def event_id(self) -> str:
        """Return the status event identifier."""
        return str(self.event.event_id)

    @property
    def fragment_ids(self) -> tuple[str, ...]:
        """Return all unfinished recovery fragments."""
        return tuple(fragment.fragment_id for fragment in self.fragments)

    @property
    def demand_ids(self) -> tuple[str, ...]:
        """Return accepted demands requiring recovery."""
        return tuple(sorted({fragment.demand_id for fragment in self.fragments}))

    @property
    def total_remaining_volume(self) -> float:
        """Return volume still requiring delivery."""
        return float(sum(fragment.volume for fragment in self.fragments))

    @property
    def locked_fragment_ids(self) -> tuple[str, ...]:
        """Return fragments already onboard a barge."""
        return tuple(
            fragment.fragment_id
            for fragment in self.fragments
            if fragment.has_locked_in_transit_movement
        )

    def fragment_state_for(
        self,
        fragment_id: str,
    ) -> ReroutingFragmentDecisionState:
        """Return one recovery fragment."""
        if not isinstance(fragment_id, str):
            raise TypeError("fragment_id must be a string.")

        normalised = fragment_id.strip()

        if not normalised:
            raise ValueError("fragment_id must be non-empty.")

        for fragment in self.fragments:
            if fragment.fragment_id == normalised:
                return fragment

        raise KeyError(f"Unknown recovery fragment: {normalised}")


def _reroutable_fragment_state(
    instance: ExperimentInstance,
    *,
    fragment: DemandFragment,
    old_path: PlannedDemandPath,
) -> ReroutableFragmentState:
    """Reconstruct the old unexecuted suffix of one fragment."""
    executed_arc_ids = fragment.executed_arc_ids
    executed_count = len(executed_arc_ids)

    if old_path.physical_arc_ids[:executed_count] != executed_arc_ids:
        raise ValueError("Executed fragment history is not a prefix of its stored path.")

    if executed_arc_ids:
        expected_current_node = instance.arc_by_id(executed_arc_ids[-1]).head
    else:
        expected_current_node = instance.network_index_for(fragment.demand_id).source

    if fragment.current_node != expected_current_node:
        raise ValueError("Fragment current node does not match its execution history.")

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


def _decision_state(
    instance: ExperimentInstance,
    ordinary_capacity: TransportCapacitySnapshot,
    fragment_state: ReroutableFragmentState,
) -> ReroutingFragmentDecisionState:
    """Lock any departed movement and release future movements."""
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
                f"An unfinished fragment suffix contains a completed transport arc: {arc_id}."
            )

    if len(locked_arc_ids) > 1:
        raise ValueError("One fragment cannot occupy multiple in-transit services.")

    locked_arc_id = locked_arc_ids[0] if locked_arc_ids else None

    if locked_arc_id is None:
        rerouting_source = fragment_state.current_node
    else:
        first_transport_arc = fragment_state.old_unexecuted_transport_arc_ids[0]

        if locked_arc_id != first_transport_arc:
            raise ValueError("An in-transit movement must be the first unexecuted transport arc.")

        rerouting_source = instance.arc_by_id(locked_arc_id).head

    return ReroutingFragmentDecisionState(
        fragment_state=fragment_state,
        physical_time=ordinary_capacity.physical_time,
        rerouting_source=rerouting_source,
        locked_in_transit_arc_id=locked_arc_id,
        releasable_future_transport_arc_ids=tuple(releasable_arc_ids),
    )


def build_recovery_fragment_snapshot(
    instance: ExperimentInstance,
    booking_state: RollingBookingState,
    execution_snapshot: ExecutionSnapshot,
    ordinary_capacity: TransportCapacitySnapshot,
    event: ServiceStatusUpdateEvent,
) -> RecoveryFragmentSnapshot:
    """Build recovery fragments without inventing a booking event."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        booking_state,
        RollingBookingState,
    ):
        raise TypeError("booking_state must be a RollingBookingState.")

    if not isinstance(
        execution_snapshot,
        ExecutionSnapshot,
    ):
        raise TypeError("execution_snapshot must be an ExecutionSnapshot.")

    if not isinstance(
        ordinary_capacity,
        TransportCapacitySnapshot,
    ):
        raise TypeError("ordinary_capacity must be a TransportCapacitySnapshot.")

    if not isinstance(
        event,
        ServiceStatusUpdateEvent,
    ):
        raise TypeError("event must be a ServiceStatusUpdateEvent.")

    fingerprint = instance.demand_fingerprint

    if booking_state.instance_fingerprint != fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if execution_snapshot.instance_fingerprint != fingerprint:
        raise ValueError("The execution snapshot belongs to another instance.")

    if ordinary_capacity.instance_fingerprint != fingerprint:
        raise ValueError("The capacity snapshot belongs to another instance.")

    if execution_snapshot.physical_time != ordinary_capacity.physical_time:
        raise ValueError("Execution and ordinary capacity must use the same physical time.")

    if execution_snapshot.physical_time != event.update_time:
        raise ValueError("Status-update time must equal the recovery snapshot time.")

    path_by_id = {path.path_id: path for path in execution_snapshot.planned_paths}

    commitment_by_demand_id = {
        commitment.demand_id: commitment
        for commitment in booking_state.commitments
        if commitment.decision_time <= event.update_time
    }

    decision_states: list[ReroutingFragmentDecisionState] = []

    for execution_state in execution_snapshot.demand_states:
        if execution_state.is_complete:
            continue

        demand_id = execution_state.demand.demand_id

        if demand_id not in commitment_by_demand_id:
            raise ValueError(
                f"Execution state has no corresponding booking commitment: {demand_id}."
            )

        for fragment in execution_state.fragments:
            try:
                old_path = path_by_id[fragment.fragment_id]
            except KeyError as error:
                raise ValueError(
                    f"Execution snapshot has no stored path for fragment {fragment.fragment_id}."
                ) from error

            reroutable = _reroutable_fragment_state(
                instance,
                fragment=fragment,
                old_path=old_path,
            )

            decision_states.append(
                _decision_state(
                    instance,
                    ordinary_capacity,
                    reroutable,
                )
            )

    return RecoveryFragmentSnapshot(
        event=event,
        physical_time=event.update_time,
        instance_fingerprint=fingerprint,
        fragments=tuple(decision_states),
    )
