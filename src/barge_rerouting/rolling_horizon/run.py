"""Complete event-by-event sequential DCA runs."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.sequential import (
    apply_sequential_booking_solution,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)
from barge_rerouting.rolling_horizon.state import RollingBookingState
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)


def _normalise_nonnegative_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite nonnegative floating-point value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value < -1e-6:
        raise ValueError(f"{name} must be nonnegative.")

    return max(0.0, numeric_value)


@dataclass(frozen=True, slots=True)
class ArcCapacityTransition:
    """Residual capacity before and after one booking decision."""

    arc_id: str
    residual_before: float
    residual_after: float

    def __post_init__(self) -> None:
        """Validate and normalise the capacity transition."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        arc_id = self.arc_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        residual_before = _normalise_nonnegative_float(
            "residual_before",
            self.residual_before,
        )
        residual_after = _normalise_nonnegative_float(
            "residual_after",
            self.residual_after,
        )

        if residual_after - residual_before > 1e-6:
            raise ValueError(
                "A myopic booking decision cannot increase reserved transport capacity."
            )

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(
            self,
            "residual_before",
            residual_before,
        )
        object.__setattr__(
            self,
            "residual_after",
            residual_after,
        )


@dataclass(frozen=True, slots=True)
class SequentialEventResult:
    """Persisted numerical outcome of one sequential booking event."""

    event: BookingDecisionEvent
    is_solved: bool
    solve_status: str
    acceptance_fraction: float | None
    objective_value: float | None
    capacity_transitions: tuple[ArcCapacityTransition, ...]

    def __post_init__(self) -> None:
        """Validate the event-level result."""
        if not isinstance(self.event, BookingDecisionEvent):
            raise TypeError("event must be a BookingDecisionEvent.")

        if not isinstance(self.is_solved, bool):
            raise TypeError("is_solved must be Boolean.")

        if not isinstance(self.solve_status, str):
            raise TypeError("solve_status must be a string.")

        solve_status = self.solve_status.strip()

        if not solve_status:
            raise ValueError("solve_status must be non-empty.")

        if not isinstance(self.capacity_transitions, tuple):
            raise TypeError("capacity_transitions must be a tuple.")

        for transition in self.capacity_transitions:
            if not isinstance(transition, ArcCapacityTransition):
                raise TypeError("Every capacity transition must be an ArcCapacityTransition.")

        transition_arc_ids = [transition.arc_id for transition in self.capacity_transitions]

        if len(set(transition_arc_ids)) != len(transition_arc_ids):
            raise ValueError("Capacity-transition arc identifiers must be unique.")

        if self.is_solved:
            if self.acceptance_fraction is None:
                raise ValueError("A solved event requires an acceptance fraction.")

            if self.objective_value is None:
                raise ValueError("A solved event requires an objective value.")

            acceptance_fraction = float(self.acceptance_fraction)
            objective_value = float(self.objective_value)

            if not isfinite(acceptance_fraction):
                raise ValueError("acceptance_fraction must be finite.")

            if acceptance_fraction < -1e-6 or acceptance_fraction > 1 + 1e-6:
                raise ValueError("acceptance_fraction must lie between zero and one.")

            if not isfinite(objective_value):
                raise ValueError("objective_value must be finite.")

            object.__setattr__(
                self,
                "acceptance_fraction",
                min(1.0, max(0.0, acceptance_fraction)),
            )
            object.__setattr__(
                self,
                "objective_value",
                objective_value,
            )
        else:
            if self.acceptance_fraction is not None:
                raise ValueError("An unsolved event cannot have an acceptance fraction.")

            if self.objective_value is not None:
                raise ValueError("An unsolved event cannot have an objective value.")

        object.__setattr__(self, "solve_status", solve_status)
        object.__setattr__(
            self,
            "capacity_transitions",
            tuple(
                sorted(
                    self.capacity_transitions,
                    key=lambda transition: transition.arc_id,
                )
            ),
        )

    @property
    def demand_id(self) -> str:
        """Return the processed demand identifier."""
        return str(self.event.demand_id)

    @property
    def accepted_volume(self) -> float:
        """Return volume accepted at this event."""
        if self.acceptance_fraction is None:
            return 0.0

        return float(self.event.demand.volume) * float(self.acceptance_fraction)

    @property
    def is_accepted(self) -> bool:
        """Return whether positive demand volume was accepted."""
        return (
            self.is_solved
            and self.acceptance_fraction is not None
            and self.acceptance_fraction > 1e-6
        )

    @property
    def is_rejected(self) -> bool:
        """Return whether the event was solved with zero acceptance."""
        return (
            self.is_solved
            and self.acceptance_fraction is not None
            and self.acceptance_fraction <= 1e-6
        )


@dataclass(frozen=True, slots=True)
class SequentialDcaRun:
    """Complete or partial sequential DCA run."""

    timeline: BookingTimeline
    results: tuple[SequentialEventResult, ...]
    final_state: RollingBookingState

    def __post_init__(self) -> None:
        """Validate run ordering and state consistency."""
        if not isinstance(self.timeline, BookingTimeline):
            raise TypeError("timeline must be a BookingTimeline.")

        if not isinstance(self.results, tuple):
            raise TypeError("results must be a tuple.")

        if not isinstance(self.final_state, RollingBookingState):
            raise TypeError("final_state must be a RollingBookingState.")

        for result in self.results:
            if not isinstance(result, SequentialEventResult):
                raise TypeError("Every run result must be a SequentialEventResult.")

        if len(self.results) > self.timeline.event_count:
            raise ValueError("Run results cannot exceed the booking timeline.")

        for position, result in enumerate(self.results, start=1):
            expected_event = self.timeline.event_at_sequence(position)

            if result.event != expected_event:
                raise ValueError("Sequential run results must follow timeline order.")

        solved_count = sum(1 for result in self.results if result.is_solved)

        if solved_count != self.final_state.processed_event_count:
            raise ValueError("Final state must contain every solved booking result.")

        unsolved_results = [result for result in self.results if not result.is_solved]

        if len(unsolved_results) > 1:
            raise ValueError("A sequential run must stop after its first unsolved event.")

        if unsolved_results and self.results[-1].is_solved:
            raise ValueError("An unsolved result must terminate the sequential run.")

    @property
    def completed(self) -> bool:
        """Return whether every booking event was solved and recorded."""
        return len(self.results) == self.timeline.event_count and all(
            result.is_solved for result in self.results
        )

    @property
    def total_revenue(self) -> float:
        """Return accumulated revenue from solved booking decisions."""
        return float(sum(result.objective_value or 0.0 for result in self.results))

    @property
    def accepted_volume(self) -> float:
        """Return total positively accepted cargo volume."""
        return float(sum(result.accepted_volume for result in self.results))

    @property
    def failure_result(self) -> SequentialEventResult | None:
        """Return the first unsolved booking event, when present."""
        for result in self.results:
            if not result.is_solved:
                return result

        return None


def run_sequential_dca(
    instance: ExperimentInstance,
    *,
    timeline: BookingTimeline | None = None,
) -> SequentialDcaRun:
    """Run myopic DCA decisions sequentially until completion or failure."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    selected_timeline = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(selected_timeline, BookingTimeline):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_demand_ids = tuple(event.demand_id for event in selected_timeline.events)
    instance_demand_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if tuple(sorted(timeline_demand_ids)) != instance_demand_ids:
        raise ValueError("Timeline demands must match the assembled instance.")

    state = RollingBookingState.empty(instance)
    results: list[SequentialEventResult] = []

    for event in selected_timeline.events:
        network_index = instance.network_index_for(event.demand_id)

        transport_arc_ids = tuple(
            sorted(
                arc_id
                for arc_id in network_index.feasible_arc_ids
                if instance.arc_by_id(arc_id).is_transport
            )
        )

        residual_before = {
            arc_id: state.residual_transport_capacity(
                instance,
                arc_id,
            )
            for arc_id in transport_arc_ids
        }

        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)

        if not solution.is_solved:
            results.append(
                SequentialEventResult(
                    event=event,
                    is_solved=False,
                    solve_status=solution.solve_status,
                    acceptance_fraction=None,
                    objective_value=None,
                    capacity_transitions=tuple(
                        ArcCapacityTransition(
                            arc_id=arc_id,
                            residual_before=residual_before[arc_id],
                            residual_after=residual_before[arc_id],
                        )
                        for arc_id in transport_arc_ids
                    ),
                )
            )
            break

        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

        results.append(
            SequentialEventResult(
                event=event,
                is_solved=True,
                solve_status=solution.solve_status,
                acceptance_fraction=solution.acceptance_fraction,
                objective_value=solution.objective_value,
                capacity_transitions=tuple(
                    ArcCapacityTransition(
                        arc_id=arc_id,
                        residual_before=residual_before[arc_id],
                        residual_after=(
                            state.residual_transport_capacity(
                                instance,
                                arc_id,
                            )
                        ),
                    )
                    for arc_id in transport_arc_ids
                ),
            )
        )

    return SequentialDcaRun(
        timeline=selected_timeline,
        results=tuple(results),
        final_state=state,
    )
