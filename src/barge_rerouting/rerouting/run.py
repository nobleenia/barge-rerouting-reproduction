"""Complete event-by-event Full-Reroute runs."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.orchestration import (
    FullRerouteEventResult,
    run_full_reroute_event,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingTimeline,
    build_booking_timeline,
)

FULL_REROUTE_RUN_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class FullRerouteRun:
    """Complete or partial Full-Reroute booking run."""

    timeline: BookingTimeline
    event_results: tuple[FullRerouteEventResult, ...]
    final_state: RollingBookingState

    def __post_init__(self) -> None:
        """Validate event order, state chaining, and termination."""
        if not isinstance(self.timeline, BookingTimeline):
            raise TypeError("timeline must be a BookingTimeline.")

        if not isinstance(self.event_results, tuple):
            raise TypeError("event_results must be a tuple.")

        if not isinstance(
            self.final_state,
            RollingBookingState,
        ):
            raise TypeError("final_state must be a RollingBookingState.")

        if len(self.event_results) > self.timeline.event_count:
            raise ValueError("Run results cannot exceed the booking timeline.")

        for result in self.event_results:
            if not isinstance(
                result,
                FullRerouteEventResult,
            ):
                raise TypeError("Every run result must be a FullRerouteEventResult.")

        for position, result in enumerate(
            self.event_results,
            start=1,
        ):
            expected_event = self.timeline.event_at_sequence(position)

            if result.event != expected_event:
                raise ValueError("Full-Reroute results must follow timeline order.")

        if self.event_results:
            first_result = self.event_results[0]

            if first_result.state_before.processed_event_count != 0:
                raise ValueError(
                    "A complete Full-Reroute run must begin from an empty booking state."
                )

            for previous, current in zip(
                self.event_results,
                self.event_results[1:],
                strict=False,
            ):
                if current.state_before != previous.state_after:
                    raise ValueError(
                        "Each event must begin from the state produced by the previous event."
                    )

            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the final event's output state.")
        elif self.final_state.processed_event_count != 0:
            raise ValueError("A run without results must retain an empty state.")

        unprocessed_results = tuple(
            result for result in self.event_results if not result.event_was_processed
        )

        if len(unprocessed_results) > 1:
            raise ValueError("A Full-Reroute run may contain at most one unprocessed event.")

        if unprocessed_results and self.event_results[-1].event_was_processed:
            raise ValueError("An unprocessed event must terminate the run.")

        processed_count = sum(1 for result in self.event_results if result.event_was_processed)

        if processed_count != self.final_state.processed_event_count:
            raise ValueError("Final state must contain every processed event.")

    @property
    def results(
        self,
    ) -> tuple[FullRerouteEventResult, ...]:
        """Return event results in booking order."""
        return self.event_results

    @property
    def completed(self) -> bool:
        """Return whether every booking event was processed."""
        return len(self.event_results) == self.timeline.event_count and all(
            result.event_was_processed for result in self.event_results
        )

    @property
    def processed_event_count(self) -> int:
        """Return the number of successfully processed events."""
        return sum(1 for result in self.event_results if result.event_was_processed)

    @property
    def total_revenue(self) -> float:
        """Return revenue from current requests accepted by Full-Reroute."""
        return float(
            sum(
                result.reroute_solution.objective_value or 0.0
                for result in self.event_results
                if result.event_was_processed
            )
        )

    @property
    def ordinary_total_revenue(self) -> float:
        """Return the corresponding ordinary-DCA event revenue."""
        return float(
            sum(
                result.ordinary_solution.objective_value or 0.0
                for result in self.event_results
                if result.ordinary_solution.is_solved
            )
        )

    @property
    def accepted_volume(self) -> float:
        """Return total newly accepted cargo volume."""
        return float(
            sum(
                (result.transition.current_commitment.accepted_volume)
                if (
                    result.transition is not None
                    and result.transition.current_commitment is not None
                )
                else 0.0
                for result in self.event_results
            )
        )

    @property
    def events_with_prior_reoptimization(self) -> int:
        """Return events that rebuilt prior accepted commitments."""
        return sum(1 for result in self.event_results if result.rerouted_demand_ids)

    @property
    def acceptance_improvement_count(self) -> int:
        """Return events whose Full-Reroute acceptance exceeds ordinary DCA."""
        improvement_count = 0

        for result in self.event_results:
            ordinary = result.ordinary_acceptance_fraction
            rerouted = result.reroute_acceptance_fraction

            if ordinary is None or rerouted is None:
                continue

            if rerouted - ordinary > FULL_REROUTE_RUN_TOLERANCE:
                improvement_count += 1

        return improvement_count

    @property
    def failure_result(
        self,
    ) -> FullRerouteEventResult | None:
        """Return the first event that could not be processed."""
        for result in self.event_results:
            if not result.event_was_processed:
                return result

        return None


def run_full_reroute(
    instance: ExperimentInstance,
    *,
    timeline: BookingTimeline | None = None,
) -> FullRerouteRun:
    """Run Full-Reroute at every incoming booking request."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    selected_timeline = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(
        selected_timeline,
        BookingTimeline,
    ):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_demand_ids = tuple(sorted(event.demand_id for event in selected_timeline.events))
    instance_demand_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if timeline_demand_ids != instance_demand_ids:
        raise ValueError("Timeline demands must match the assembled instance.")

    state = RollingBookingState.empty(instance)
    event_results: list[FullRerouteEventResult] = []

    for event in selected_timeline.events:
        result = run_full_reroute_event(
            instance,
            state,
            event,
        )
        event_results.append(result)

        if not result.event_was_processed:
            break

        state = result.state_after

    return FullRerouteRun(
        timeline=selected_timeline,
        event_results=tuple(event_results),
        final_state=state,
    )
