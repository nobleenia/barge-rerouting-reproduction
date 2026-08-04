"""Time-aware orchestration of sequential DCA booking events."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.run import (
    ArcCapacityTransition,
    SequentialEventResult,
)
from barge_rerouting.rolling_horizon.sequential import (
    apply_sequential_booking_solution,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)
from barge_rerouting.rolling_horizon.state import RollingBookingState
from barge_rerouting.rolling_horizon.timeline import (
    BookingTimeline,
    build_booking_timeline,
)


@dataclass(frozen=True, slots=True)
class TimeAwareEpochResult:
    """Execution and booking results at one physical decision time."""

    physical_time: int
    execution_before: ExecutionSnapshot
    capacity_before: TransportCapacitySnapshot
    event_results: tuple[SequentialEventResult, ...]
    execution_after: ExecutionSnapshot
    capacity_after: TransportCapacitySnapshot

    def __post_init__(self) -> None:
        """Validate epoch timing consistency."""
        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if not isinstance(self.execution_before, ExecutionSnapshot):
            raise TypeError("execution_before must be an ExecutionSnapshot.")

        if not isinstance(
            self.capacity_before,
            TransportCapacitySnapshot,
        ):
            raise TypeError("capacity_before must be a TransportCapacitySnapshot.")

        if not isinstance(self.execution_after, ExecutionSnapshot):
            raise TypeError("execution_after must be an ExecutionSnapshot.")

        if not isinstance(
            self.capacity_after,
            TransportCapacitySnapshot,
        ):
            raise TypeError("capacity_after must be a TransportCapacitySnapshot.")

        snapshot_times = {
            self.execution_before.physical_time,
            self.capacity_before.physical_time,
            self.execution_after.physical_time,
            self.capacity_after.physical_time,
        }

        if snapshot_times != {self.physical_time}:
            raise ValueError("Every epoch snapshot must use the epoch physical time.")

        if not isinstance(self.event_results, tuple):
            raise TypeError("event_results must be a tuple.")

        for event_result in self.event_results:
            if not isinstance(event_result, SequentialEventResult):
                raise TypeError("Every event result must be a SequentialEventResult.")

            if event_result.event.decision_time != self.physical_time:
                raise ValueError("Every event result must belong to the epoch time.")

    @property
    def has_failure(self) -> bool:
        """Return whether this epoch ended with an unsolved event."""
        return any(not event_result.is_solved for event_result in self.event_results)


@dataclass(frozen=True, slots=True)
class TimeAwareSequentialDcaRun:
    """Complete or partial sequential run with physical-time snapshots."""

    timeline: BookingTimeline
    epochs: tuple[TimeAwareEpochResult, ...]
    final_state: RollingBookingState

    def __post_init__(self) -> None:
        """Validate epoch ordering and state consistency."""
        if not isinstance(self.timeline, BookingTimeline):
            raise TypeError("timeline must be a BookingTimeline.")

        if not isinstance(self.epochs, tuple):
            raise TypeError("epochs must be a tuple.")

        if not isinstance(self.final_state, RollingBookingState):
            raise TypeError("final_state must be a RollingBookingState.")

        for epoch in self.epochs:
            if not isinstance(epoch, TimeAwareEpochResult):
                raise TypeError("Every epoch must be a TimeAwareEpochResult.")

        epoch_times = tuple(epoch.physical_time for epoch in self.epochs)

        if epoch_times != tuple(sorted(epoch_times)):
            raise ValueError("Time-aware epochs must be chronologically ordered.")

        solved_count = sum(1 for result in self.results if result.is_solved)

        if solved_count != self.final_state.processed_event_count:
            raise ValueError("Final booking state must contain every solved event.")

    @property
    def results(self) -> tuple[SequentialEventResult, ...]:
        """Return all event results in chronological sequence."""
        return tuple(result for epoch in self.epochs for result in epoch.event_results)

    @property
    def completed(self) -> bool:
        """Return whether all booking events were processed."""
        return len(self.results) == self.timeline.event_count and all(
            result.is_solved for result in self.results
        )

    @property
    def total_revenue(self) -> float:
        """Return accumulated event revenue."""
        return float(sum(result.objective_value or 0.0 for result in self.results))

    @property
    def accepted_volume(self) -> float:
        """Return total accepted demand volume."""
        return float(sum(result.accepted_volume for result in self.results))

    @property
    def failure_result(self) -> SequentialEventResult | None:
        """Return the first unsolved event."""
        for result in self.results:
            if not result.is_solved:
                return result

        return None


def _build_snapshots(
    instance: ExperimentInstance,
    state: RollingBookingState,
    physical_time: int,
) -> tuple[ExecutionSnapshot, TransportCapacitySnapshot]:
    """Build mutually consistent execution and capacity snapshots."""
    execution_snapshot = build_execution_snapshot(
        instance,
        state,
        physical_time=physical_time,
    )
    capacity_snapshot = build_transport_capacity_snapshot(
        instance,
        execution_snapshot,
    )

    return execution_snapshot, capacity_snapshot


def run_time_aware_sequential_dca(
    instance: ExperimentInstance,
    *,
    timeline: BookingTimeline | None = None,
) -> TimeAwareSequentialDcaRun:
    """Run sequential DCA while advancing physical execution time."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    selected_timeline = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(selected_timeline, BookingTimeline):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_demand_ids = tuple(sorted(event.demand_id for event in selected_timeline.events))
    instance_demand_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if timeline_demand_ids != instance_demand_ids:
        raise ValueError("Timeline demands must match the assembled instance.")

    state = RollingBookingState.empty(instance)
    epochs: list[TimeAwareEpochResult] = []
    terminate_run = False

    for physical_time in selected_timeline.decision_times:
        execution_before, capacity_before = _build_snapshots(
            instance,
            state,
            physical_time,
        )
        epoch_results: list[SequentialEventResult] = []

        for event in selected_timeline.events_at_time(physical_time):
            current_execution, current_capacity = _build_snapshots(
                instance,
                state,
                physical_time,
            )

            network_index = instance.network_index_for(event.demand_id)

            transport_arc_ids = tuple(
                sorted(
                    arc_id
                    for arc_id in network_index.feasible_arc_ids
                    if instance.arc_by_id(arc_id).is_transport
                )
            )

            residual_before = {
                arc_id: current_capacity.bookable_capacity_for(arc_id)
                for arc_id in transport_arc_ids
            }

            artifacts = build_sequential_booking_model(
                instance,
                state,
                event,
                capacity_snapshot=current_capacity,
            )
            solution = solve_sequential_booking_model(artifacts)

            if not solution.is_solved:
                epoch_results.append(
                    SequentialEventResult(
                        event=event,
                        is_solved=False,
                        solve_status=solution.solve_status,
                        acceptance_fraction=None,
                        objective_value=None,
                        capacity_transitions=tuple(
                            ArcCapacityTransition(
                                arc_id=arc_id,
                                residual_before=(residual_before[arc_id]),
                                residual_after=(residual_before[arc_id]),
                            )
                            for arc_id in transport_arc_ids
                        ),
                    )
                )
                terminate_run = True
                break

            state = apply_sequential_booking_solution(
                artifacts,
                solution,
            )

            _, capacity_after_event = _build_snapshots(
                instance,
                state,
                physical_time,
            )

            epoch_results.append(
                SequentialEventResult(
                    event=event,
                    is_solved=True,
                    solve_status=solution.solve_status,
                    acceptance_fraction=(solution.acceptance_fraction),
                    objective_value=solution.objective_value,
                    capacity_transitions=tuple(
                        ArcCapacityTransition(
                            arc_id=arc_id,
                            residual_before=(residual_before[arc_id]),
                            residual_after=(capacity_after_event.bookable_capacity_for(arc_id)),
                        )
                        for arc_id in transport_arc_ids
                    ),
                )
            )

        execution_after, capacity_after = _build_snapshots(
            instance,
            state,
            physical_time,
        )

        epochs.append(
            TimeAwareEpochResult(
                physical_time=physical_time,
                execution_before=execution_before,
                capacity_before=capacity_before,
                event_results=tuple(epoch_results),
                execution_after=execution_after,
                capacity_after=capacity_after,
            )
        )

        if terminate_run:
            break

    return TimeAwareSequentialDcaRun(
        timeline=selected_timeline,
        epochs=tuple(epochs),
        final_state=state,
    )
