"""Complete time-aware sequential DCA-RRM runs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.rrm_orchestration import (
    DcaRrmEventResult,
    run_dca_rrm_event,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)

DcaRrmForecastProvider = Callable[
    [
        BookingDecisionEvent,
        RollingBookingState,
    ],
    Sequence[FutureDemandForecast],
]


@dataclass(frozen=True, slots=True)
class TimeAwareDcaRrmRun:
    """Complete or partial sequential DCA-RRM run."""

    timeline: BookingTimeline
    event_results: tuple[DcaRrmEventResult, ...]
    final_state: RollingBookingState
    value_interpretation: FutureValueInterpretation
    selection_mode: FutureDemandSelectionMode
    lookahead_periods: int | None

    def __post_init__(self) -> None:
        """Validate event order, state chaining, and termination."""
        if not isinstance(
            self.timeline,
            BookingTimeline,
        ):
            raise TypeError("timeline must be a BookingTimeline.")

        if not isinstance(
            self.event_results,
            tuple,
        ):
            raise TypeError("event_results must be a tuple.")

        if not isinstance(
            self.final_state,
            RollingBookingState,
        ):
            raise TypeError("final_state must be a RollingBookingState.")

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

        if self.lookahead_periods is not None:
            if isinstance(self.lookahead_periods, bool) or not isinstance(
                self.lookahead_periods,
                int,
            ):
                raise TypeError("lookahead_periods must be an integer or None.")

            if self.lookahead_periods < 0:
                raise ValueError("lookahead_periods must be non-negative.")

        if len(self.event_results) > self.timeline.event_count:
            raise ValueError("Run results cannot exceed the timeline.")

        for result in self.event_results:
            if not isinstance(
                result,
                DcaRrmEventResult,
            ):
                raise TypeError("Every run result must be a DcaRrmEventResult.")

        for position, result in enumerate(
            self.event_results,
            start=1,
        ):
            expected_event = self.timeline.event_at_sequence(position)

            if result.event != expected_event:
                raise ValueError("DCA-RRM results must follow timeline order.")

        if self.event_results:
            first_result = self.event_results[0]

            if first_result.state_before.processed_event_count != 0:
                raise ValueError("A complete DCA-RRM run must begin from an empty booking state.")

            for previous, current in zip(
                self.event_results,
                self.event_results[1:],
                strict=False,
            ):
                if current.state_before != previous.state_after:
                    raise ValueError(
                        "Each DCA-RRM event must begin from the preceding event's output state."
                    )

            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the final event output state.")
        elif self.final_state.processed_event_count != 0:
            raise ValueError("A run without results must retain an empty state.")

        failed_results = tuple(
            result for result in self.event_results if not result.event_was_processed
        )

        if len(failed_results) > 1:
            raise ValueError("A DCA-RRM run may contain at most one failed event.")

        if failed_results and self.event_results[-1].event_was_processed:
            raise ValueError("A failed event must terminate the run.")

        if self.processed_event_count != self.final_state.processed_event_count:
            raise ValueError("Final state must contain every processed event.")

    @property
    def results(self) -> tuple[DcaRrmEventResult, ...]:
        """Return event results in booking order."""
        return self.event_results

    @property
    def completed(self) -> bool:
        """Return whether every event was processed."""
        return bool(
            len(self.event_results) == self.timeline.event_count
            and all(result.event_was_processed for result in self.event_results)
        )

    @property
    def processed_event_count(self) -> int:
        """Return successfully processed event count."""
        return sum(1 for result in self.event_results if result.event_was_processed)

    @property
    def total_realised_revenue(self) -> float:
        """Return revenue from realised current decisions."""
        return float(
            sum(
                result.current_realised_revenue
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def summed_event_objectives(self) -> float:
        """Return the diagnostic sum of event objectives.

        This is not realised revenue because future-value
        contributions can overlap with later realised revenue.
        """
        return float(
            sum(
                result.optimisation_objective
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def total_expected_future_contribution(self) -> float:
        """Return summed expected future contributions."""
        return float(
            sum(
                result.future_expected_revenue
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def accepted_volume(self) -> float:
        """Return realised accepted current volume."""
        return float(
            sum(
                result.accepted_volume
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def events_with_prior_reoptimization(self) -> int:
        """Return events rebuilding prior commitments."""
        return sum(1 for result in self.event_results if result.rerouted_demand_ids)

    @property
    def cumulative_selected_protection_volume(self) -> float:
        """Return event-level selected protection summed over solves."""
        return float(
            sum(
                result.selected_protection_volume
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def cumulative_discarded_future_volume(self) -> float:
        """Return tentative protection discarded after decisions."""
        return float(
            sum(
                result.discarded_tentative_future_volume
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def failure_result(self) -> DcaRrmEventResult | None:
        """Return the first event that could not be processed."""
        for result in self.event_results:
            if not result.event_was_processed:
                return result

        return None


def run_time_aware_dca_rrm(
    instance: ExperimentInstance,
    forecast_provider: DcaRrmForecastProvider,
    *,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    timeline: BookingTimeline | None = None,
    lookahead_periods: int | None = None,
    solver_backend: SolverBackend = SolverBackend.CPLEX,
) -> TimeAwareDcaRrmRun:
    """Run combined DCA-RRM over the booking timeline."""
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

    if not isinstance(
        solver_backend,
        SolverBackend,
    ):
        raise TypeError("solver_backend must be a SolverBackend.")

    if lookahead_periods is not None:
        if isinstance(lookahead_periods, bool) or not isinstance(
            lookahead_periods,
            int,
        ):
            raise TypeError("lookahead_periods must be an integer or None.")

        if lookahead_periods < 0:
            raise ValueError("lookahead_periods must be non-negative.")

    selected_timeline = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(
        selected_timeline,
        BookingTimeline,
    ):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_demand_ids = tuple(sorted(event.demand_id for event in selected_timeline.events))
    instance_demand_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if timeline_demand_ids != instance_demand_ids:
        raise ValueError("Timeline demands must match the instance.")

    state = RollingBookingState.empty(instance)
    event_results: list[DcaRrmEventResult] = []

    for event in selected_timeline.events:
        forecasts = tuple(
            forecast_provider(
                event,
                state,
            )
        )

        result = run_dca_rrm_event(
            instance,
            state,
            event,
            forecasts,
            value_interpretation=value_interpretation,
            selection_mode=selection_mode,
            lookahead_periods=lookahead_periods,
            solver_backend=solver_backend,
        )
        event_results.append(result)

        if not result.event_was_processed:
            break

        state = result.state_after

    return TimeAwareDcaRrmRun(
        timeline=selected_timeline,
        event_results=tuple(event_results),
        final_state=state,
        value_interpretation=value_interpretation,
        selection_mode=selection_mode,
        lookahead_periods=lookahead_periods,
    )
