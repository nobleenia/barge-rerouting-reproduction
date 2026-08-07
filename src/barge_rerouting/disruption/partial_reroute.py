"""Dynamic Partial-Reroute orchestration.

Partial-Reroute reacts to service-status / forecast updates by
reoptimising unfinished accepted cargo. Ordinary booking events do
not trigger rerouting of prior accepted demand.

This module is specific to the dynamic service-status scenario.
The stable-capacity Phase-7 Full-Reroute implementation remains
unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from barge_rerouting.disruption.booking_capacity import (
    ActualBookableCapacitySnapshot,
    build_actual_bookable_capacity_snapshot,
)
from barge_rerouting.disruption.capacity import (
    ActualCapacityProfile,
    build_actual_capacity_profile,
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
from barge_rerouting.rolling_horizon.sequential import (
    SequentialBookingSolution,
    apply_sequential_booking_solution,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


@dataclass(frozen=True, slots=True)
class PartialRerouteEventResult:
    """Result of one dynamic Partial-Reroute operational event."""

    entry: OperationalTimelineEntry
    state_before: RecoveryOperationalState
    state_after: RecoveryOperationalState
    actual_capacity_profile: ActualCapacityProfile
    event_was_processed: bool
    booking_solution: SequentialBookingSolution | None = None
    actual_bookable_capacity: ActualBookableCapacitySnapshot | None = None
    recovery_solution: TruckRecourseSolution | None = None
    recovery_transition: TruckRecourseTransitionResult | None = None

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
            raise ValueError(
                "Actual capacity and operational state must belong to the same instance."
            )

        if self.actual_capacity_profile.physical_time != self.entry.physical_time:
            raise ValueError("Actual capacity must use the event physical time.")

        if self.entry.is_booking:
            if self.booking_solution is None:
                raise ValueError("A booking event requires a booking solution.")

            if self.recovery_solution is not None:
                raise ValueError("A PR booking event cannot contain a recovery solution.")

            if self.recovery_transition is not None:
                raise ValueError("A PR booking event cannot contain a recovery transition.")

            if self.actual_bookable_capacity is None:
                raise ValueError("A booking event requires actual bookable capacity.")

            if self.event_was_processed:
                if (
                    self.state_after.booking_state.processed_event_count
                    != self.state_before.booking_state.processed_event_count + 1
                ):
                    raise ValueError("A processed booking must append exactly one booking record.")

                if self.state_after.recovery_event_count != self.state_before.recovery_event_count:
                    raise ValueError(
                        "Partial-Reroute must not reroute prior cargo at a booking event."
                    )
            elif self.state_after != self.state_before:
                raise ValueError("An unprocessed booking event must not change operational state.")

        elif self.entry.is_status_update:
            if self.booking_solution is not None:
                raise ValueError("A status event cannot contain a booking solution.")

            if self.actual_bookable_capacity is not None:
                raise ValueError("A status event does not create a booking-capacity snapshot.")

            if self.recovery_transition is not None:
                if self.recovery_solution is None:
                    raise ValueError("A recovery transition requires a recovery solution.")

                if (
                    self.state_after.recovery_event_count
                    != self.state_before.recovery_event_count + 1
                ):
                    raise ValueError(
                        "A recovered status event must append exactly one recovery event."
                    )
            elif self.event_was_processed and self.state_after != self.state_before:
                raise ValueError(
                    "A status event without recovery must leave operational state unchanged."
                )

    @property
    def event_id(self) -> str:
        """Return the operational source-event identifier."""
        return str(self.entry.event_id)

    @property
    def accepted_volume(self) -> float:
        """Return volume newly accepted at this event."""
        if (
            not self.entry.is_booking
            or self.booking_solution is None
            or self.booking_solution.acceptance_fraction is None
        ):
            return 0.0

        booking_event = self.entry.booking_event

        if booking_event is None:
            return 0.0

        return float(booking_event.demand.volume * self.booking_solution.acceptance_fraction)

    @property
    def realised_revenue(self) -> float:
        """Return current-demand revenue from this event."""
        if (
            not self.entry.is_booking
            or self.booking_solution is None
            or self.booking_solution.objective_value is None
        ):
            return 0.0

        return float(self.booking_solution.objective_value)

    @property
    def truck_volume(self) -> float:
        """Return truck volume assigned at this status event."""
        if self.recovery_solution is None:
            return 0.0

        return float(self.recovery_solution.total_truck_volume)


@dataclass(frozen=True, slots=True)
class PartialRerouteRun:
    """Complete or partial dynamic Partial-Reroute run."""

    timeline: OperationalTimeline
    event_results: tuple[PartialRerouteEventResult, ...]
    final_state: RecoveryOperationalState

    def __post_init__(self) -> None:
        """Validate event order and state chaining."""
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
                PartialRerouteEventResult,
            ):
                raise TypeError("Every result must be a PartialRerouteEventResult.")

            expected_entry = self.timeline.entries[position - 1]

            if result.entry != expected_entry:
                raise ValueError("Partial-Reroute results must follow operational timeline order.")

        for previous, current in zip(
            self.event_results,
            self.event_results[1:],
            strict=False,
        ):
            if current.state_before != previous.state_after:
                raise ValueError("Each PR event must begin from the previous event's state.")

        if self.event_results:
            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the final event result state.")

        unprocessed = tuple(
            result for result in self.event_results if not result.event_was_processed
        )

        if len(unprocessed) > 1:
            raise ValueError("A PR run may contain at most one unprocessed event.")

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
            if result.entry.is_booking and result.event_was_processed
        )

    @property
    def processed_status_count(self) -> int:
        """Return successfully processed status updates."""
        return sum(
            1
            for result in self.event_results
            if result.entry.is_status_update and result.event_was_processed
        )

    @property
    def accepted_volume(self) -> float:
        """Return newly accepted volume across booking events."""
        return float(sum(result.accepted_volume for result in self.event_results))

    @property
    def total_revenue(self) -> float:
        """Return realised current-demand revenue."""
        return float(sum(result.realised_revenue for result in self.event_results))

    @property
    def total_truck_volume(self) -> float:
        """Return cumulative terminal truck allocation."""
        return float(self.final_state.total_truck_volume)

    @property
    def total_truck_penalty(self) -> float:
        """Return cumulative truck penalty."""
        return float(self.final_state.total_truck_penalty)


def _status_result(
    instance: ExperimentInstance,
    state: RecoveryOperationalState,
    entry: OperationalTimelineEntry,
    known_status_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ],
    truck_penalty_per_teu_by_demand: Mapping[str, float],
) -> PartialRerouteEventResult:
    """Process one forecast/status update under PR."""
    status_event = entry.status_update

    if status_event is None:
        raise ValueError("Status-event processing requires a status update.")

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

    recovery_fragments = build_recovery_fragment_snapshot(
        instance,
        state.booking_state,
        execution,
        ordinary_capacity,
        status_event,
    )

    # Nothing unfinished: the forecast is processed, but there is
    # no rerouting/truck optimisation to persist.
    if not recovery_fragments.fragments:
        return PartialRerouteEventResult(
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
        recovery_fragments,
    )

    recovery_networks = build_recovery_fragment_network_snapshot(
        instance,
        recovery_fragments,
        recovery_capacity,
    )

    penalties: dict[str, float] = {}

    for demand_id in recovery_fragments.demand_ids:
        if demand_id not in truck_penalty_per_teu_by_demand:
            raise ValueError(f"Missing explicit truck penalty for recovery demand {demand_id}.")

        penalties[demand_id] = float(truck_penalty_per_teu_by_demand[demand_id])

    artifacts = build_truck_recourse_model(
        instance,
        recovery_fragments,
        recovery_capacity,
        recovery_networks,
        truck_penalty_per_teu_by_demand=penalties,
    )

    try:
        solution = solve_truck_recourse_model(artifacts)

        if not solution.is_solved:
            return PartialRerouteEventResult(
                entry=entry,
                state_before=state,
                state_after=state,
                actual_capacity_profile=actual_capacity,
                event_was_processed=False,
                recovery_solution=solution,
            )

        transition = apply_truck_recourse_solution(
            artifacts,
            solution,
            state,
        )

        return PartialRerouteEventResult(
            entry=entry,
            state_before=state,
            state_after=transition.state_after,
            actual_capacity_profile=actual_capacity,
            event_was_processed=True,
            recovery_solution=solution,
            recovery_transition=transition,
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
) -> PartialRerouteEventResult:
    """Process one ordinary booking under current actual capacity."""
    booking_event = entry.booking_event

    if booking_event is None:
        raise ValueError("Booking-event processing requires a booking event.")

    operational_capacity = build_operational_transport_capacity_snapshot(
        instance,
        state,
        physical_time=entry.physical_time,
    )

    actual_capacity = build_actual_capacity_profile(
        instance,
        physical_time=entry.physical_time,
        status_updates=known_status_updates,
    )

    actual_bookable = build_actual_bookable_capacity_snapshot(
        instance,
        operational_capacity,
        actual_capacity,
    )

    artifacts = build_sequential_booking_model(
        instance,
        state.booking_state,
        booking_event,
        residual_capacity_overrides=(actual_bookable.as_residual_capacity_overrides()),
    )

    try:
        solution = solve_sequential_booking_model(artifacts)

        if not solution.is_solved:
            return PartialRerouteEventResult(
                entry=entry,
                state_before=state,
                state_after=state,
                actual_capacity_profile=actual_capacity,
                event_was_processed=False,
                booking_solution=solution,
                actual_bookable_capacity=actual_bookable,
            )

        booking_state_after = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

        state_after = state.with_booking_state(booking_state_after)

        return PartialRerouteEventResult(
            entry=entry,
            state_before=state,
            state_after=state_after,
            actual_capacity_profile=actual_capacity,
            event_was_processed=True,
            booking_solution=solution,
            actual_bookable_capacity=actual_bookable,
        )
    finally:
        artifacts.model.end()


def run_partial_reroute(
    instance: ExperimentInstance,
    *,
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
    truck_penalty_per_teu_by_demand: Mapping[
        str,
        float,
    ],
    timeline: OperationalTimeline | None = None,
) -> PartialRerouteRun:
    """Run dynamic Partial-Reroute over the operational timeline."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

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

    if not isinstance(
        truck_penalty_per_teu_by_demand,
        Mapping,
    ):
        raise TypeError("truck_penalty_per_teu_by_demand must be a mapping.")

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    results: list[PartialRerouteEventResult] = []
    known_status_updates: list[ServiceStatusUpdateEvent] = []

    for entry in selected_timeline.entries:
        if entry.is_status_update:
            status_event = entry.status_update

            if status_event is None:
                raise ValueError("Operational status entry has no status-update event.")

            # The newly published forecast is visible immediately.
            known_status_updates.append(status_event)

            result = _status_result(
                instance,
                state,
                entry,
                tuple(known_status_updates),
                truck_penalty_per_teu_by_demand,
            )
        else:
            result = _booking_result(
                instance,
                state,
                entry,
                tuple(known_status_updates),
            )

        results.append(result)

        if not result.event_was_processed:
            break

        state = result.state_after

    return PartialRerouteRun(
        timeline=selected_timeline,
        event_results=tuple(results),
        final_state=state,
    )
