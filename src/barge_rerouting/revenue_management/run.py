"""Time-aware sequential orchestration of DCA-RM decisions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.dca_rm import (
    DcaRmSolution,
    FutureProtectionResult,
    build_dca_rm_model,
    solve_dca_rm_model,
    validate_dca_rm_solution,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
    FutureDemandSet,
    select_a004_interacting_future_set,
    select_explicit_future_set,
)
from barge_rerouting.revenue_management.transition import (
    apply_dca_rm_solution,
)
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
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)

ForecastProvider = Callable[
    [
        BookingDecisionEvent,
        RollingBookingState,
    ],
    Sequence[FutureDemandForecast],
]


def _normalise_optional_float(
    name: str,
    value: float | None,
) -> float | None:
    """Validate and normalise an optional finite number."""
    if value is None:
        return None

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class DcaRmEventResult:
    """One persisted sequential DCA-RM event result."""

    event: BookingDecisionEvent
    is_solved: bool
    solve_status: str
    value_interpretation: FutureValueInterpretation
    selection_mode: FutureDemandSelectionMode
    forecast_ids: tuple[str, ...]
    acceptance_fraction: float | None
    optimisation_objective: float | None
    current_realised_revenue: float | None
    future_expected_revenue: float | None
    protections: tuple[FutureProtectionResult, ...]
    capacity_transitions: tuple[
        ArcCapacityTransition,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate one event-level result."""
        if not isinstance(
            self.event,
            BookingDecisionEvent,
        ):
            raise TypeError("event must be a BookingDecisionEvent.")

        if not isinstance(self.is_solved, bool):
            raise TypeError("is_solved must be Boolean.")

        if not isinstance(self.solve_status, str):
            raise TypeError("solve_status must be a string.")

        solve_status = self.solve_status.strip()

        if not solve_status:
            raise ValueError("solve_status must be non-empty.")

        if not isinstance(
            self.value_interpretation,
            FutureValueInterpretation,
        ):
            raise TypeError("value_interpretation must be a FutureValueInterpretation.")

        if not isinstance(
            self.selection_mode,
            FutureDemandSelectionMode,
        ):
            raise TypeError("selection_mode must be a FutureDemandSelectionMode.")

        if not isinstance(self.forecast_ids, tuple):
            raise TypeError("forecast_ids must be a tuple.")

        forecast_ids = tuple(sorted(self.forecast_ids))

        if len(set(forecast_ids)) != len(forecast_ids):
            raise ValueError("forecast_ids must be unique.")

        if not isinstance(self.protections, tuple):
            raise TypeError("protections must be a tuple.")

        for protection in self.protections:
            if not isinstance(
                protection,
                FutureProtectionResult,
            ):
                raise TypeError("Every protection must be a FutureProtectionResult.")

        if not isinstance(
            self.capacity_transitions,
            tuple,
        ):
            raise TypeError("capacity_transitions must be a tuple.")

        for transition in self.capacity_transitions:
            if not isinstance(
                transition,
                ArcCapacityTransition,
            ):
                raise TypeError("Every transition must be an ArcCapacityTransition.")

        if self.is_solved:
            required_values = (
                self.acceptance_fraction,
                self.optimisation_objective,
                self.current_realised_revenue,
                self.future_expected_revenue,
            )

            if any(value is None for value in required_values):
                raise ValueError(
                    "A solved event requires acceptance, "
                    "objective, realised revenue, and "
                    "future expected revenue."
                )

            acceptance_fraction = self.acceptance_fraction

            if acceptance_fraction is None:
                raise ValueError("A solved event requires an acceptance fraction.")

            acceptance = float(acceptance_fraction)

            if acceptance < -1e-6 or acceptance > 1.0 + 1e-6:
                raise ValueError("acceptance_fraction must lie between zero and one.")

            object.__setattr__(
                self,
                "acceptance_fraction",
                min(1.0, max(0.0, acceptance)),
            )

            object.__setattr__(
                self,
                "optimisation_objective",
                _normalise_optional_float(
                    "optimisation_objective",
                    self.optimisation_objective,
                ),
            )
            object.__setattr__(
                self,
                "current_realised_revenue",
                _normalise_optional_float(
                    "current_realised_revenue",
                    self.current_realised_revenue,
                ),
            )
            object.__setattr__(
                self,
                "future_expected_revenue",
                _normalise_optional_float(
                    "future_expected_revenue",
                    self.future_expected_revenue,
                ),
            )
        else:
            optional_values = (
                self.acceptance_fraction,
                self.optimisation_objective,
                self.current_realised_revenue,
                self.future_expected_revenue,
            )

            if any(value is not None for value in optional_values):
                raise ValueError("An unsolved event cannot have solution values.")

            if self.protections:
                raise ValueError("An unsolved event cannot have protection results.")

        object.__setattr__(
            self,
            "solve_status",
            solve_status,
        )
        object.__setattr__(
            self,
            "forecast_ids",
            forecast_ids,
        )
        object.__setattr__(
            self,
            "protections",
            tuple(
                sorted(
                    self.protections,
                    key=lambda item: item.forecast_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "capacity_transitions",
            tuple(
                sorted(
                    self.capacity_transitions,
                    key=lambda item: item.arc_id,
                )
            ),
        )

    @property
    def demand_id(self) -> str:
        """Return the current demand identifier."""
        return str(self.event.demand_id)

    @property
    def accepted_volume(self) -> float:
        """Return realised accepted current volume."""
        if self.acceptance_fraction is None:
            return 0.0

        return float(self.event.demand.volume * self.acceptance_fraction)

    @property
    def is_accepted(self) -> bool:
        """Return whether positive current volume was accepted."""
        return bool(
            self.is_solved
            and self.acceptance_fraction is not None
            and self.acceptance_fraction > 1e-6
        )

    def protection_for(
        self,
        forecast_id: str,
    ) -> FutureProtectionResult:
        """Return one event protection result."""
        for protection in self.protections:
            if protection.forecast_id == forecast_id:
                return protection

        raise KeyError(f"No protection result for {forecast_id}.")

    def capacity_transition_for(
        self,
        arc_id: str,
    ) -> ArcCapacityTransition:
        """Return one realised capacity transition."""
        for transition in self.capacity_transitions:
            if transition.arc_id == arc_id:
                return transition

        raise KeyError(f"No capacity transition for {arc_id}.")


@dataclass(frozen=True, slots=True)
class DcaRmEpochResult:
    """DCA-RM decisions and snapshots at one physical time."""

    physical_time: int
    execution_before: ExecutionSnapshot
    capacity_before: TransportCapacitySnapshot
    event_results: tuple[DcaRmEventResult, ...]
    execution_after: ExecutionSnapshot
    capacity_after: TransportCapacitySnapshot

    def __post_init__(self) -> None:
        """Validate epoch timing and event membership."""
        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        snapshots = (
            self.execution_before,
            self.capacity_before,
            self.execution_after,
            self.capacity_after,
        )

        snapshot_times = {snapshot.physical_time for snapshot in snapshots}

        if snapshot_times != {self.physical_time}:
            raise ValueError("Every snapshot must use the epoch time.")

        if not isinstance(
            self.event_results,
            tuple,
        ):
            raise TypeError("event_results must be a tuple.")

        for result in self.event_results:
            if not isinstance(
                result,
                DcaRmEventResult,
            ):
                raise TypeError("Every event result must be a DcaRmEventResult.")

            if result.event.decision_time != self.physical_time:
                raise ValueError("Every event must belong to the epoch time.")

    @property
    def has_failure(self) -> bool:
        """Return whether this epoch ended unsolved."""
        return any(not result.is_solved for result in self.event_results)


@dataclass(frozen=True, slots=True)
class TimeAwareDcaRmRun:
    """Complete or partial sequential DCA-RM run."""

    timeline: BookingTimeline
    epochs: tuple[DcaRmEpochResult, ...]
    final_state: RollingBookingState
    value_interpretation: FutureValueInterpretation
    selection_mode: FutureDemandSelectionMode

    def __post_init__(self) -> None:
        """Validate ordering and state consistency."""
        if not isinstance(
            self.timeline,
            BookingTimeline,
        ):
            raise TypeError("timeline must be a BookingTimeline.")

        if not isinstance(self.epochs, tuple):
            raise TypeError("epochs must be a tuple.")

        for epoch in self.epochs:
            if not isinstance(epoch, DcaRmEpochResult):
                raise TypeError("Every epoch must be a DcaRmEpochResult.")

        epoch_times = tuple(epoch.physical_time for epoch in self.epochs)

        if epoch_times != tuple(sorted(epoch_times)):
            raise ValueError("Epochs must be chronologically ordered.")

        solved_count = sum(1 for result in self.results if result.is_solved)

        if solved_count != self.final_state.processed_event_count:
            raise ValueError("Final state must contain every solved current decision.")

    @property
    def results(self) -> tuple[DcaRmEventResult, ...]:
        """Return all event results in timeline order."""
        return tuple(result for epoch in self.epochs for result in epoch.event_results)

    @property
    def completed(self) -> bool:
        """Return whether every event was solved."""
        return bool(
            len(self.results) == self.timeline.event_count
            and all(result.is_solved for result in self.results)
        )

    @property
    def total_realised_revenue(self) -> float:
        """Return revenue from realised current acceptances."""
        return float(sum(result.current_realised_revenue or 0.0 for result in self.results))

    @property
    def summed_event_objectives(self) -> float:
        """Return the diagnostic sum of event objectives.

        This is not realised revenue because expected future values
        may later overlap with realised demand revenue.
        """
        return float(sum(result.optimisation_objective or 0.0 for result in self.results))

    @property
    def total_expected_future_contribution(self) -> float:
        """Return the diagnostic sum of future-value terms."""
        return float(sum(result.future_expected_revenue or 0.0 for result in self.results))

    @property
    def accepted_volume(self) -> float:
        """Return realised accepted current volume."""
        return float(sum(result.accepted_volume for result in self.results))

    @property
    def failure_result(self) -> DcaRmEventResult | None:
        """Return the first unsolved result."""
        for result in self.results:
            if not result.is_solved:
                return result

        return None


def _build_snapshots(
    instance: ExperimentInstance,
    state: RollingBookingState,
    physical_time: int,
) -> tuple[
    ExecutionSnapshot,
    TransportCapacitySnapshot,
]:
    """Build consistent execution and capacity snapshots."""
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=physical_time,
    )
    capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    return execution, capacity


def _select_future_set(
    instance: ExperimentInstance,
    event: BookingDecisionEvent,
    forecasts: Sequence[FutureDemandForecast],
    *,
    selection_mode: FutureDemandSelectionMode,
    lookahead_periods: int | None,
) -> FutureDemandSet:
    """Construct K(current) using the selected rule."""
    if selection_mode is FutureDemandSelectionMode.EXPLICIT:
        return select_explicit_future_set(
            instance,
            event,
            forecasts,
        )

    if selection_mode is FutureDemandSelectionMode.A004_SHARED_ARC:
        lookahead_end_time = (
            None if lookahead_periods is None else event.decision_time + lookahead_periods
        )

        return select_a004_interacting_future_set(
            instance,
            event,
            forecasts,
            lookahead_end_time=lookahead_end_time,
        )

    raise ValueError(f"Unsupported selection mode: {selection_mode}")


def _event_result_from_solution(
    solution: DcaRmSolution,
    *,
    event: BookingDecisionEvent,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    forecast_ids: tuple[str, ...],
    transitions: tuple[ArcCapacityTransition, ...],
) -> DcaRmEventResult:
    """Build one solved event result."""
    return DcaRmEventResult(
        event=event,
        is_solved=True,
        solve_status=solution.solve_status,
        value_interpretation=value_interpretation,
        selection_mode=selection_mode,
        forecast_ids=forecast_ids,
        acceptance_fraction=solution.acceptance_fraction,
        optimisation_objective=solution.objective_value,
        current_realised_revenue=solution.current_revenue,
        future_expected_revenue=(solution.future_expected_revenue),
        protections=solution.protections,
        capacity_transitions=transitions,
    )


def run_time_aware_dca_rm(
    instance: ExperimentInstance,
    forecast_provider: ForecastProvider,
    *,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    timeline: BookingTimeline | None = None,
    lookahead_periods: int | None = None,
) -> TimeAwareDcaRmRun:
    """Run DCA-RM sequentially over the booking timeline."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not callable(forecast_provider):
        raise TypeError("forecast_provider must be callable.")

    if not isinstance(
        value_interpretation,
        FutureValueInterpretation,
    ):
        raise TypeError("value_interpretation must be a FutureValueInterpretation.")

    if not isinstance(
        selection_mode,
        FutureDemandSelectionMode,
    ):
        raise TypeError("selection_mode must be a FutureDemandSelectionMode.")

    if lookahead_periods is not None:
        if isinstance(lookahead_periods, bool) or not isinstance(lookahead_periods, int):
            raise TypeError("lookahead_periods must be an integer or None.")

        if lookahead_periods < 0:
            raise ValueError("lookahead_periods must be non-negative.")

    selected_timeline = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(
        selected_timeline,
        BookingTimeline,
    ):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_ids = tuple(sorted(event.demand_id for event in selected_timeline.events))
    instance_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if timeline_ids != instance_ids:
        raise ValueError("Timeline demands must match the instance.")

    state = RollingBookingState.empty(instance)
    epochs: list[DcaRmEpochResult] = []
    terminate_run = False

    for physical_time in selected_timeline.decision_times:
        execution_before, capacity_before = _build_snapshots(
            instance,
            state,
            physical_time,
        )
        epoch_results: list[DcaRmEventResult] = []

        for event in selected_timeline.events_at_time(physical_time):
            _, current_capacity = _build_snapshots(
                instance,
                state,
                physical_time,
            )

            forecasts = tuple(forecast_provider(event, state))

            future_set = _select_future_set(
                instance,
                event,
                forecasts,
                selection_mode=selection_mode,
                lookahead_periods=lookahead_periods,
            )

            artifacts = build_dca_rm_model(
                instance,
                state,
                event,
                future_set,
                value_interpretation=(value_interpretation),
                capacity_snapshot=current_capacity,
            )

            try:
                solution = solve_dca_rm_model(artifacts)

                capacity_arc_ids = tuple(sorted(artifacts.available_capacities))
                residual_before = {
                    arc_id: current_capacity.bookable_capacity_for(arc_id)
                    for arc_id in capacity_arc_ids
                }

                if not solution.is_solved:
                    epoch_results.append(
                        DcaRmEventResult(
                            event=event,
                            is_solved=False,
                            solve_status=(solution.solve_status),
                            value_interpretation=(value_interpretation),
                            selection_mode=selection_mode,
                            forecast_ids=(future_set.forecast_ids),
                            acceptance_fraction=None,
                            optimisation_objective=None,
                            current_realised_revenue=None,
                            future_expected_revenue=None,
                            protections=(),
                            capacity_transitions=tuple(
                                ArcCapacityTransition(
                                    arc_id=arc_id,
                                    residual_before=(residual_before[arc_id]),
                                    residual_after=(residual_before[arc_id]),
                                )
                                for arc_id in capacity_arc_ids
                            ),
                        )
                    )
                    terminate_run = True
                    break

                validation = validate_dca_rm_solution(
                    artifacts,
                    solution,
                )

                if not validation.is_valid:
                    raise ValueError("Solved DCA-RM event failed independent validation.")

                state = apply_dca_rm_solution(
                    artifacts,
                    solution,
                )

                _, capacity_after_event = _build_snapshots(
                    instance,
                    state,
                    physical_time,
                )

                transitions = tuple(
                    ArcCapacityTransition(
                        arc_id=arc_id,
                        residual_before=(residual_before[arc_id]),
                        residual_after=(capacity_after_event.bookable_capacity_for(arc_id)),
                    )
                    for arc_id in capacity_arc_ids
                )

                epoch_results.append(
                    _event_result_from_solution(
                        solution,
                        event=event,
                        value_interpretation=(value_interpretation),
                        selection_mode=selection_mode,
                        forecast_ids=(future_set.forecast_ids),
                        transitions=transitions,
                    )
                )
            finally:
                artifacts.model.end()

        execution_after, capacity_after = _build_snapshots(
            instance,
            state,
            physical_time,
        )

        epochs.append(
            DcaRmEpochResult(
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

    return TimeAwareDcaRmRun(
        timeline=selected_timeline,
        epochs=tuple(epochs),
        final_state=state,
        value_interpretation=value_interpretation,
        selection_mode=selection_mode,
    )
