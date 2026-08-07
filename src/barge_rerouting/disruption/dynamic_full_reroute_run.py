"""Operational orchestration for dynamic Full-Reroute."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from barge_rerouting.disruption.capacity import (
    ActualCapacityProfile,
    build_actual_capacity_profile,
)
from barge_rerouting.disruption.dynamic_full_reroute import (
    DynamicFullRerouteSolution,
    build_dynamic_full_reroute_model,
    solve_dynamic_full_reroute_model,
)
from barge_rerouting.disruption.dynamic_full_reroute_transition import (
    DynamicFullRerouteTransitionResult,
    apply_dynamic_full_reroute_solution,
)
from barge_rerouting.disruption.operational_execution import (
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
)
from barge_rerouting.disruption.recovery import (
    build_recovery_fragment_snapshot,
)
from barge_rerouting.disruption.recovery_capacity import (
    build_recovery_capacity_snapshot,
)
from barge_rerouting.disruption.recovery_network import (
    build_recovery_fragment_network_snapshot,
)
from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
    TruckRecourseTransitionResult,
    apply_truck_recourse_solution,
)
from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.disruption.timeline import (
    OperationalTimeline,
    OperationalTimelineEntry,
    build_operational_timeline,
)
from barge_rerouting.disruption.truck_recourse import (
    TruckRecourseSolution,
    build_truck_recourse_model,
    solve_truck_recourse_model,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteEventResult:
    """Result of one dynamic Full-Reroute operational event."""

    entry: OperationalTimelineEntry
    state_before: RecoveryOperationalState
    state_after: RecoveryOperationalState
    actual_capacity_profile: ActualCapacityProfile
    event_was_processed: bool
    booking_solution: DynamicFullRerouteSolution | None = None
    booking_transition: DynamicFullRerouteTransitionResult | None = None
    status_solution: TruckRecourseSolution | None = None
    status_transition: TruckRecourseTransitionResult | None = None

    def __post_init__(self) -> None:
        """Validate event/result consistency."""
        if not isinstance(
            self.entry,
            OperationalTimelineEntry,
        ):
            raise TypeError("entry must be an OperationalTimelineEntry.")

        if not isinstance(
            self.state_before,
            RecoveryOperationalState,
        ):
            raise TypeError("state_before must be a RecoveryOperationalState.")

        if not isinstance(
            self.state_after,
            RecoveryOperationalState,
        ):
            raise TypeError("state_after must be a RecoveryOperationalState.")

        if not isinstance(
            self.actual_capacity_profile,
            ActualCapacityProfile,
        ):
            raise TypeError("actual_capacity_profile must be an ActualCapacityProfile.")

        if not isinstance(self.event_was_processed, bool):
            raise TypeError("event_was_processed must be a boolean.")

        fingerprint = self.state_before.instance_fingerprint

        if self.state_after.instance_fingerprint != fingerprint:
            raise ValueError("Operational states must belong to the same instance.")

        if self.actual_capacity_profile.instance_fingerprint != fingerprint:
            raise ValueError("Actual capacity belongs to another experiment instance.")

        if self.actual_capacity_profile.physical_time != self.entry.physical_time:
            raise ValueError("Actual capacity must use the operational-event time.")

        if self.entry.is_booking:
            if self.booking_solution is None:
                raise ValueError("A booking event requires a dynamic Full-Reroute solution.")

            if self.status_solution is not None:
                raise ValueError("A booking event cannot contain a status-recovery solution.")

            if self.status_transition is not None:
                raise ValueError("A booking event cannot contain a status-recovery transition.")

            if self.event_was_processed:
                if self.booking_transition is None:
                    raise ValueError("A processed booking requires a booking transition.")

                if (
                    self.state_after.booking_state.processed_event_count
                    != self.state_before.booking_state.processed_event_count + 1
                ):
                    raise ValueError(
                        "A processed Full-Reroute booking must append exactly one booking event."
                    )
            else:
                if self.booking_transition is not None:
                    raise ValueError("An unprocessed booking cannot contain a transition.")

                if self.state_after != self.state_before:
                    raise ValueError("An unprocessed booking cannot change operational state.")

        elif self.entry.is_status_update:
            if self.booking_solution is not None:
                raise ValueError("A status event cannot contain a booking solution.")

            if self.booking_transition is not None:
                raise ValueError("A status event cannot contain a booking transition.")

            if self.status_transition is not None and self.status_solution is None:
                raise ValueError("A status transition requires a status solution.")

    @property
    def event_id(self) -> str:
        """Return source-event identifier."""
        return str(self.entry.event_id)

    @property
    def accepted_volume(self) -> float:
        """Return newly accepted current-demand volume."""
        if (
            not self.entry.is_booking
            or self.booking_solution is None
            or self.booking_solution.acceptance_fraction is None
        ):
            return 0.0

        event = self.entry.booking_event

        if event is None:
            return 0.0

        return float(event.demand.volume * self.booking_solution.acceptance_fraction)

    @property
    def realised_revenue(self) -> float:
        """Return revenue earned from current acceptance."""
        if (
            not self.entry.is_booking
            or self.booking_solution is None
            or self.booking_solution.acceptance_fraction is None
        ):
            return 0.0

        event = self.entry.booking_event

        if event is None:
            return 0.0

        return float(event.demand.maximum_revenue * self.booking_solution.acceptance_fraction)

    @property
    def additional_truck_volume(self) -> float:
        """Return truck volume newly assigned at this event."""
        if self.entry.is_booking:
            if self.booking_transition is None:
                return 0.0

            return float(self.booking_transition.additional_truck_volume)

        if self.status_transition is None:
            return 0.0

        return float(sum(transfer.volume for transfer in self.status_transition.truck_transfers))

    @property
    def additional_truck_penalty(self) -> float:
        """Return truck penalty newly incurred at this event."""
        if self.entry.is_booking:
            if self.booking_transition is None:
                return 0.0

            return float(self.booking_transition.additional_truck_penalty)

        if self.status_transition is None:
            return 0.0

        return float(
            sum(transfer.penalty_value for transfer in self.status_transition.truck_transfers)
        )


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteRun:
    """One operational dynamic Full-Reroute run."""

    timeline: OperationalTimeline
    event_results: tuple[
        DynamicFullRerouteEventResult,
        ...,
    ]
    final_state: RecoveryOperationalState

    def __post_init__(self) -> None:
        """Validate timeline ordering and state chaining."""
        if not isinstance(
            self.timeline,
            OperationalTimeline,
        ):
            raise TypeError("timeline must be an OperationalTimeline.")

        if not isinstance(self.event_results, tuple):
            raise TypeError("event_results must be a tuple.")

        if not isinstance(
            self.final_state,
            RecoveryOperationalState,
        ):
            raise TypeError("final_state must be a RecoveryOperationalState.")

        if len(self.event_results) > self.timeline.event_count:
            raise ValueError("Run results cannot exceed the operational timeline.")

        for position, result in enumerate(
            self.event_results,
            start=1,
        ):
            if not isinstance(
                result,
                DynamicFullRerouteEventResult,
            ):
                raise TypeError("Every result must be a DynamicFullRerouteEventResult.")

            if result.entry != self.timeline.entries[position - 1]:
                raise ValueError("Dynamic Full-Reroute results must follow timeline order.")

        for previous, current in zip(
            self.event_results,
            self.event_results[1:],
            strict=False,
        ):
            if current.state_before != previous.state_after:
                raise ValueError(
                    "Each operational event must start from the previous event's state."
                )

        if self.event_results:
            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the state after the final recorded event.")

        unprocessed = tuple(
            result for result in self.event_results if not result.event_was_processed
        )

        if len(unprocessed) > 1:
            raise ValueError("A run may contain at most one unprocessed event.")

        if unprocessed and self.event_results[-1].event_was_processed:
            raise ValueError("An unprocessed event must terminate the run.")

    @property
    def completed(self) -> bool:
        """Return whether every operational event was processed."""
        return len(self.event_results) == self.timeline.event_count and all(
            result.event_was_processed for result in self.event_results
        )

    @property
    def processed_booking_count(self) -> int:
        """Return successfully processed booking events."""
        return sum(
            1
            for result in self.event_results
            if (result.entry.is_booking and result.event_was_processed)
        )

    @property
    def processed_status_count(self) -> int:
        """Return successfully processed status updates."""
        return sum(
            1
            for result in self.event_results
            if (result.entry.is_status_update and result.event_was_processed)
        )

    @property
    def accepted_volume(self) -> float:
        """Return total newly accepted volume."""
        return float(sum(result.accepted_volume for result in self.event_results))

    @property
    def total_revenue(self) -> float:
        """Return realised booking revenue."""
        return float(sum(result.realised_revenue for result in self.event_results))

    @property
    def total_truck_volume(self) -> float:
        """Return cumulative terminal truck volume."""
        return float(self.final_state.total_truck_volume)

    @property
    def total_truck_penalty(self) -> float:
        """Return cumulative truck penalty."""
        return float(self.final_state.total_truck_penalty)

    @property
    def net_realised_value(self) -> float:
        """Return realised booking revenue less truck penalties."""
        return float(self.total_revenue - self.total_truck_penalty)


def _penalties_for(
    demand_ids: set[str],
    supplied: Mapping[str, float],
) -> dict[str, float]:
    """Select explicit penalties for one optimisation."""
    missing = tuple(sorted(demand_id for demand_id in demand_ids if demand_id not in supplied))

    if missing:
        raise ValueError(f"Missing explicit truck penalties for demands: {missing}.")

    return {demand_id: float(supplied[demand_id]) for demand_id in sorted(demand_ids)}


def _status_result(
    instance: ExperimentInstance,
    state: RecoveryOperationalState,
    entry: OperationalTimelineEntry,
    known_status_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ],
    truck_penalties: Mapping[str, float],
) -> DynamicFullRerouteEventResult:
    """Process one status update under dynamic Full-Reroute."""
    status_event = entry.status_update

    if status_event is None:
        raise ValueError("Status processing requires a status event.")

    execution = build_operational_execution_snapshot(
        instance,
        state,
        physical_time=entry.physical_time,
    )

    ordinary_capacity = build_operational_transport_capacity_snapshot(
        instance,
        state,
        physical_time=entry.physical_time,
    )

    actual_capacity = build_actual_capacity_profile(
        instance,
        physical_time=entry.physical_time,
        status_updates=known_status_updates,
    )

    fragments = build_recovery_fragment_snapshot(
        instance,
        state.booking_state,
        execution,
        ordinary_capacity,
        status_event,
    )

    if not fragments.fragments:
        return DynamicFullRerouteEventResult(
            entry=entry,
            state_before=state,
            state_after=state,
            actual_capacity_profile=actual_capacity,
            event_was_processed=True,
        )

    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary_capacity,
        actual_capacity,
        fragments,
    )

    networks = build_recovery_fragment_network_snapshot(
        instance,
        fragments,
        recovery_capacity,
    )

    penalties = _penalties_for(
        set(fragments.demand_ids),
        truck_penalties,
    )

    artifacts = build_truck_recourse_model(
        instance,
        fragments,
        recovery_capacity,
        networks,
        truck_penalty_per_teu_by_demand=penalties,
    )

    try:
        solution = solve_truck_recourse_model(artifacts)

        if not solution.is_solved:
            return DynamicFullRerouteEventResult(
                entry=entry,
                state_before=state,
                state_after=state,
                actual_capacity_profile=actual_capacity,
                event_was_processed=False,
                status_solution=solution,
            )

        transition = apply_truck_recourse_solution(
            artifacts,
            solution,
            state,
        )

        return DynamicFullRerouteEventResult(
            entry=entry,
            state_before=state,
            state_after=transition.state_after,
            actual_capacity_profile=actual_capacity,
            event_was_processed=True,
            status_solution=solution,
            status_transition=transition,
        )
    finally:
        artifacts.model.end()


def _booking_result(
    instance: ExperimentInstance,
    state: RecoveryOperationalState,
    entry: OperationalTimelineEntry,
    known_status_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ],
    truck_penalties: Mapping[str, float],
) -> DynamicFullRerouteEventResult:
    """Process one booking-triggered dynamic Full-Reroute."""
    booking_event = entry.booking_event

    if booking_event is None:
        raise ValueError("Booking processing requires a booking event.")

    execution = build_operational_execution_snapshot(
        instance,
        state,
        physical_time=entry.physical_time,
    )

    ordinary_capacity = build_operational_transport_capacity_snapshot(
        instance,
        state,
        physical_time=entry.physical_time,
    )

    actual_capacity = build_actual_capacity_profile(
        instance,
        physical_time=entry.physical_time,
        status_updates=known_status_updates,
    )

    fragments = build_recovery_fragment_snapshot(
        instance,
        state.booking_state,
        execution,
        ordinary_capacity,
        booking_event,
    )

    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary_capacity,
        actual_capacity,
        fragments,
    )

    networks = build_recovery_fragment_network_snapshot(
        instance,
        fragments,
        recovery_capacity,
    )

    affected_demand_ids = {
        booking_event.demand_id,
        *(index.demand_id for index in networks.indexes),
    }

    penalties = _penalties_for(
        affected_demand_ids,
        truck_penalties,
    )

    artifacts = build_dynamic_full_reroute_model(
        instance,
        state.booking_state,
        booking_event,
        recovery_capacity,
        networks,
        truck_penalty_per_teu_by_demand=penalties,
        # Operational baseline:
        # truck recourse applies to already accepted
        # unfinished cargo, not directly to the newly
        # arriving request.
        allow_current_truck=False,
    )

    try:
        solution = solve_dynamic_full_reroute_model(artifacts)

        if not solution.is_solved:
            return DynamicFullRerouteEventResult(
                entry=entry,
                state_before=state,
                state_after=state,
                actual_capacity_profile=actual_capacity,
                event_was_processed=False,
                booking_solution=solution,
            )

        transition = apply_dynamic_full_reroute_solution(
            artifacts,
            solution,
            state,
        )

        return DynamicFullRerouteEventResult(
            entry=entry,
            state_before=state,
            state_after=transition.state_after,
            actual_capacity_profile=actual_capacity,
            event_was_processed=True,
            booking_solution=solution,
            booking_transition=transition,
        )
    finally:
        artifacts.model.end()


def run_dynamic_full_reroute(
    instance: ExperimentInstance,
    *,
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
    truck_penalty_per_teu_by_demand: Mapping[
        str,
        float,
    ],
    timeline: OperationalTimeline | None = None,
) -> DynamicFullRerouteRun:
    """Run dynamic Full-Reroute over all operational events."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        truck_penalty_per_teu_by_demand,
        Mapping,
    ):
        raise TypeError("truck_penalty_per_teu_by_demand must be a mapping.")

    selected_timeline = (
        build_operational_timeline(
            instance,
            status_updates=status_updates,
        )
        if timeline is None
        else timeline
    )

    if not isinstance(
        selected_timeline,
        OperationalTimeline,
    ):
        raise TypeError("timeline must be an OperationalTimeline.")

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    known_updates: list[ServiceStatusUpdateEvent] = []
    results: list[DynamicFullRerouteEventResult] = []

    for entry in selected_timeline.entries:
        if entry.is_status_update:
            status_event = entry.status_update

            if status_event is None:
                raise ValueError("Status timeline entry has no status event.")

            # Status first on a timestamp means every
            # later booking at that same time sees it.
            known_updates.append(status_event)

            result = _status_result(
                instance,
                state,
                entry,
                tuple(known_updates),
                truck_penalty_per_teu_by_demand,
            )
        else:
            result = _booking_result(
                instance,
                state,
                entry,
                tuple(known_updates),
                truck_penalty_per_teu_by_demand,
            )

        results.append(result)

        if not result.event_was_processed:
            break

        state = result.state_after

    return DynamicFullRerouteRun(
        timeline=selected_timeline,
        event_results=tuple(results),
        final_state=state,
    )
