"""Phase 11 policy execution with explicit A036 continuation semantics."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
)
from barge_rerouting.experiments.phase11_execution import (
    Phase11EventDisposition,
    advance_regular_feasibility_rejection,
    is_proven_infeasible_status,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.dca_rm import (
    build_dca_rm_model,
    validate_dca_rm_solution,
)
from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
    solve_dca_rm_with_backend,
)
from barge_rerouting.rerouting.orchestration import (
    run_full_reroute_event,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.rrm_orchestration import (
    run_dca_rrm_event,
)
from barge_rerouting.revenue_management.run import (
    _select_future_set,
)
from barge_rerouting.revenue_management.transition import (
    apply_dca_rm_solution,
)
from barge_rerouting.rolling_horizon.capacity import (
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.sequential import (
    apply_sequential_booking_solution,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
    BookingTimeline,
    build_booking_timeline,
)

PHASE11_ACCEPTANCE_TOLERANCE = 1e-6

Phase11ForecastProvider = Callable[
    [
        BookingDecisionEvent,
        RollingBookingState,
    ],
    Sequence[FutureDemandForecast],
]


@dataclass(frozen=True, slots=True)
class Phase11PolicyEventResult:
    """Experiment-layer disposition of one incoming booking."""

    policy_key: str
    event: BookingDecisionEvent
    disposition: Phase11EventDisposition
    acceptance_fraction: float | None
    realised_revenue: float
    solver_status: str
    state_before: RollingBookingState
    state_after: RollingBookingState

    def __post_init__(self) -> None:
        """Validate one Phase 11 event record."""
        policy_key = self.policy_key.strip()
        solver_status = self.solver_status.strip()

        if not policy_key:
            raise ValueError("policy_key must be non-empty.")

        if not solver_status:
            raise ValueError("solver_status must be non-empty.")

        revenue = float(self.realised_revenue)

        if not isfinite(revenue):
            raise ValueError("realised_revenue must be finite.")

        if revenue < -PHASE11_ACCEPTANCE_TOLERANCE:
            raise ValueError("realised_revenue must be non-negative.")

        acceptance = self.acceptance_fraction

        if acceptance is not None:
            acceptance = float(acceptance)

            if not isfinite(acceptance):
                raise ValueError("acceptance_fraction must be finite.")

            if (
                acceptance < -PHASE11_ACCEPTANCE_TOLERANCE
                or acceptance > 1.0 + PHASE11_ACCEPTANCE_TOLERANCE
            ):
                raise ValueError("acceptance_fraction must lie between zero and one.")

            acceptance = min(
                1.0,
                max(0.0, acceptance),
            )

        if self.disposition is Phase11EventDisposition.SOLVER_FAILURE:
            if acceptance is not None:
                raise ValueError("A solver failure cannot have an acceptance fraction.")

            if self.state_after != self.state_before:
                raise ValueError("A solver failure cannot advance persistent state.")
        else:
            if acceptance is None:
                raise ValueError(
                    "A processed event requires an experiment-level acceptance fraction."
                )

            if (
                self.state_after.processed_event_count
                != self.state_before.processed_event_count + 1
            ):
                raise ValueError("A processed Phase 11 event must advance the state once.")

        if self.disposition is Phase11EventDisposition.FEASIBILITY_REJECTED:
            if acceptance is None or acceptance > PHASE11_ACCEPTANCE_TOLERANCE:
                raise ValueError(
                    "An A036 feasibility rejection must have zero experiment-level acceptance."
                )

            if abs(revenue) > PHASE11_ACCEPTANCE_TOLERANCE:
                raise ValueError("An A036 feasibility rejection cannot earn revenue.")

        object.__setattr__(
            self,
            "policy_key",
            policy_key,
        )
        object.__setattr__(
            self,
            "solver_status",
            solver_status,
        )
        object.__setattr__(
            self,
            "realised_revenue",
            max(0.0, revenue),
        )
        object.__setattr__(
            self,
            "acceptance_fraction",
            acceptance,
        )

    @property
    def accepted_volume(self) -> float:
        """Return realised accepted current volume."""
        if self.acceptance_fraction is None:
            return 0.0

        return float(self.event.demand.volume * self.acceptance_fraction)

    @property
    def is_ordinary_rejection(self) -> bool:
        """Return whether optimisation solved with zero acceptance."""
        return bool(
            self.disposition is Phase11EventDisposition.OPTIMISATION_SOLVED
            and self.acceptance_fraction is not None
            and self.acceptance_fraction <= PHASE11_ACCEPTANCE_TOLERANCE
        )


@dataclass(frozen=True, slots=True)
class Phase11PolicyRun:
    """Complete or failed Phase 11 policy trajectory."""

    policy_key: str
    solver_backend: SolverBackend
    timeline: BookingTimeline
    event_results: tuple[Phase11PolicyEventResult, ...]
    final_state: RollingBookingState

    def __post_init__(self) -> None:
        """Validate event ordering and state chaining."""
        if not isinstance(
            self.solver_backend,
            SolverBackend,
        ):
            raise TypeError("solver_backend must be a SolverBackend.")

        for position, result in enumerate(
            self.event_results,
            start=1,
        ):
            expected = self.timeline.event_at_sequence(position)

            if result.event != expected:
                raise ValueError("Phase 11 results must follow booking order.")

            if result.policy_key != self.policy_key:
                raise ValueError("Every event must use the run policy key.")

        for previous, current in zip(
            self.event_results,
            self.event_results[1:],
            strict=False,
        ):
            if current.state_before != previous.state_after:
                raise ValueError("Phase 11 state chaining is inconsistent.")

        failures = tuple(
            result
            for result in self.event_results
            if result.disposition is Phase11EventDisposition.SOLVER_FAILURE
        )

        if len(failures) > 1:
            raise ValueError("A Phase 11 run may contain at most one solver failure.")

        if failures and self.event_results[-1] != failures[0]:
            raise ValueError("A solver failure must terminate the run.")

        if self.event_results:
            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the last event output.")

    @property
    def completed(self) -> bool:
        """Return whether every booking received a valid disposition."""
        return bool(
            len(self.event_results) == self.timeline.event_count and self.solver_failure_count == 0
        )

    @property
    def processed_event_count(self) -> int:
        """Return events that advanced booking state."""
        return sum(
            result.disposition is not Phase11EventDisposition.SOLVER_FAILURE
            for result in self.event_results
        )

    @property
    def total_revenue(self) -> float:
        """Return realised current-booking revenue."""
        return float(sum(result.realised_revenue for result in self.event_results))

    @property
    def accepted_volume(self) -> float:
        """Return total realised accepted volume."""
        return float(sum(result.accepted_volume for result in self.event_results))

    @property
    def ordinary_rejection_count(self) -> int:
        """Return solved zero-acceptance decisions."""
        return sum(result.is_ordinary_rejection for result in self.event_results)

    @property
    def feasibility_rejection_count(self) -> int:
        """Return A036 rejection count."""
        return sum(
            result.disposition is Phase11EventDisposition.FEASIBILITY_REJECTED
            for result in self.event_results
        )

    @property
    def feasibility_rejected_demand_ids(
        self,
    ) -> tuple[str, ...]:
        """Return A036-rejected demand identifiers."""
        return tuple(
            result.event.demand_id
            for result in self.event_results
            if result.disposition is Phase11EventDisposition.FEASIBILITY_REJECTED
        )

    @property
    def solver_failure_count(self) -> int:
        """Return computational/model failure count."""
        return sum(
            result.disposition is Phase11EventDisposition.SOLVER_FAILURE
            for result in self.event_results
        )

    @property
    def failure_event(
        self,
    ) -> Phase11PolicyEventResult | None:
        """Return the terminating solver failure."""
        for result in self.event_results:
            if result.disposition is Phase11EventDisposition.SOLVER_FAILURE:
                return result

        return None

    def result_for_demand(
        self,
        demand_id: str,
    ) -> Phase11PolicyEventResult:
        """Return one event result by demand identifier."""
        for result in self.event_results:
            if result.event.demand_id == demand_id:
                return result

        raise KeyError(f"No Phase 11 result for {demand_id}.")


def _selected_timeline(
    instance: ExperimentInstance,
    timeline: BookingTimeline | None,
) -> BookingTimeline:
    selected = build_booking_timeline(instance) if timeline is None else timeline

    if not isinstance(
        selected,
        BookingTimeline,
    ):
        raise TypeError("timeline must be a BookingTimeline.")

    timeline_ids = tuple(sorted(event.demand_id for event in selected.events))
    instance_ids = tuple(sorted(demand.demand_id for demand in instance.demands))

    if timeline_ids != instance_ids:
        raise ValueError("Timeline demands must match the instance.")

    return selected


def _unsolved_event(
    *,
    policy_key: str,
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    solve_status: str,
) -> tuple[
    Phase11PolicyEventResult,
    RollingBookingState,
    bool,
]:
    """Apply A036 when permitted, otherwise return solver failure."""
    if event.demand.category.value == "R" and is_proven_infeasible_status(solve_status):
        state_after = advance_regular_feasibility_rejection(
            instance,
            state,
            event,
            solve_status=solve_status,
        )

        return (
            Phase11PolicyEventResult(
                policy_key=policy_key,
                event=event,
                disposition=(Phase11EventDisposition.FEASIBILITY_REJECTED),
                acceptance_fraction=0.0,
                realised_revenue=0.0,
                solver_status=solve_status,
                state_before=state,
                state_after=state_after,
            ),
            state_after,
            False,
        )

    return (
        Phase11PolicyEventResult(
            policy_key=policy_key,
            event=event,
            disposition=(Phase11EventDisposition.SOLVER_FAILURE),
            acceptance_fraction=None,
            realised_revenue=0.0,
            solver_status=solve_status,
            state_before=state,
            state_after=state,
        ),
        state,
        True,
    )


def run_phase11_dca(
    instance: ExperimentInstance,
    *,
    timeline: BookingTimeline | None = None,
) -> Phase11PolicyRun:
    """Run time-aware DCA with Phase 11 A036 semantics."""
    selected = _selected_timeline(
        instance,
        timeline,
    )
    state = RollingBookingState.empty(instance)
    results: list[Phase11PolicyEventResult] = []

    for event in selected.events:
        state_before = state

        execution = build_execution_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )
        capacity = build_transport_capacity_snapshot(
            instance,
            execution,
        )

        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
            capacity_snapshot=capacity,
        )

        stop = False

        try:
            solution = solve_sequential_booking_model(artifacts)

            if solution.is_solved:
                state = apply_sequential_booking_solution(
                    artifacts,
                    solution,
                )

                result = Phase11PolicyEventResult(
                    policy_key="dca",
                    event=event,
                    disposition=(Phase11EventDisposition.OPTIMISATION_SOLVED),
                    acceptance_fraction=(solution.acceptance_fraction),
                    realised_revenue=float(solution.objective_value or 0.0),
                    solver_status=(solution.solve_status),
                    state_before=state_before,
                    state_after=state,
                )
            else:
                result, state, stop = _unsolved_event(
                    policy_key="dca",
                    instance=instance,
                    state=state,
                    event=event,
                    solve_status=(solution.solve_status),
                )
        finally:
            artifacts.model.end()

        results.append(result)

        if stop:
            break

    return Phase11PolicyRun(
        policy_key="dca",
        solver_backend=SolverBackend.CPLEX,
        timeline=selected,
        event_results=tuple(results),
        final_state=state,
    )


def run_phase11_dca_rm(
    instance: ExperimentInstance,
    forecast_provider: Phase11ForecastProvider,
    *,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    timeline: BookingTimeline | None = None,
    lookahead_periods: int | None = None,
    solver_backend: SolverBackend = SolverBackend.CPLEX,
) -> Phase11PolicyRun:
    """Run DCA-RM with Phase 11 A036 semantics."""
    selected = _selected_timeline(
        instance,
        timeline,
    )
    state = RollingBookingState.empty(instance)
    results: list[Phase11PolicyEventResult] = []

    for event in selected.events:
        state_before = state

        execution = build_execution_snapshot(
            instance,
            state,
            physical_time=event.decision_time,
        )
        capacity = build_transport_capacity_snapshot(
            instance,
            execution,
        )

        forecasts = tuple(
            forecast_provider(
                event,
                state,
            )
        )

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
            capacity_snapshot=capacity,
        )

        stop = False

        try:
            solution = solve_dca_rm_with_backend(
                artifacts,
                backend=solver_backend,
            )

            if solution.is_solved:
                validation = validate_dca_rm_solution(
                    artifacts,
                    solution,
                )

                if not validation.is_valid:
                    raise ValueError("Solved Phase 11 DCA-RM event failed independent validation.")

                state = apply_dca_rm_solution(
                    artifacts,
                    solution,
                )

                result = Phase11PolicyEventResult(
                    policy_key="dca_rm",
                    event=event,
                    disposition=(Phase11EventDisposition.OPTIMISATION_SOLVED),
                    acceptance_fraction=(solution.acceptance_fraction),
                    realised_revenue=float(solution.current_revenue or 0.0),
                    solver_status=(solution.solve_status),
                    state_before=state_before,
                    state_after=state,
                )
            else:
                result, state, stop = _unsolved_event(
                    policy_key="dca_rm",
                    instance=instance,
                    state=state,
                    event=event,
                    solve_status=(solution.solve_status),
                )
        finally:
            artifacts.model.end()

        results.append(result)

        if stop:
            break

    return Phase11PolicyRun(
        policy_key="dca_rm",
        solver_backend=solver_backend,
        timeline=selected,
        event_results=tuple(results),
        final_state=state,
    )


def run_phase11_dca_r(
    instance: ExperimentInstance,
    *,
    timeline: BookingTimeline | None = None,
) -> Phase11PolicyRun:
    """Run Full-Reroute with Phase 11 A036 semantics."""
    selected = _selected_timeline(
        instance,
        timeline,
    )
    state = RollingBookingState.empty(instance)
    results: list[Phase11PolicyEventResult] = []

    for event in selected.events:
        state_before = state

        core_result = run_full_reroute_event(
            instance,
            state,
            event,
        )

        stop = False

        if core_result.event_was_processed:
            state = core_result.state_after

            result = Phase11PolicyEventResult(
                policy_key="dca_r",
                event=event,
                disposition=(Phase11EventDisposition.OPTIMISATION_SOLVED),
                acceptance_fraction=(core_result.reroute_acceptance_fraction),
                realised_revenue=float(core_result.reroute_solution.objective_value or 0.0),
                solver_status=(core_result.reroute_solution.solve_status),
                state_before=state_before,
                state_after=state,
            )
        else:
            result, state, stop = _unsolved_event(
                policy_key="dca_r",
                instance=instance,
                state=state,
                event=event,
                solve_status=(core_result.reroute_solution.solve_status),
            )

        results.append(result)

        if stop:
            break

    return Phase11PolicyRun(
        policy_key="dca_r",
        solver_backend=SolverBackend.CPLEX,
        timeline=selected,
        event_results=tuple(results),
        final_state=state,
    )


def run_phase11_dca_rrm(
    instance: ExperimentInstance,
    forecast_provider: Phase11ForecastProvider,
    *,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    timeline: BookingTimeline | None = None,
    lookahead_periods: int | None = None,
    solver_backend: SolverBackend = SolverBackend.CPLEX,
) -> Phase11PolicyRun:
    """Run DCA-RRM with Phase 11 A036 semantics."""
    selected = _selected_timeline(
        instance,
        timeline,
    )
    state = RollingBookingState.empty(instance)
    results: list[Phase11PolicyEventResult] = []

    for event in selected.events:
        state_before = state

        forecasts = tuple(
            forecast_provider(
                event,
                state,
            )
        )

        core_result = run_dca_rrm_event(
            instance,
            state,
            event,
            forecasts,
            value_interpretation=(value_interpretation),
            selection_mode=selection_mode,
            lookahead_periods=lookahead_periods,
            solver_backend=solver_backend,
        )

        stop = False

        if core_result.event_was_processed:
            state = core_result.state_after

            result = Phase11PolicyEventResult(
                policy_key="dca_rrm",
                event=event,
                disposition=(Phase11EventDisposition.OPTIMISATION_SOLVED),
                acceptance_fraction=(core_result.acceptance_fraction),
                realised_revenue=float(core_result.current_realised_revenue),
                solver_status=(core_result.solution.solve_status),
                state_before=state_before,
                state_after=state,
            )
        else:
            result, state, stop = _unsolved_event(
                policy_key="dca_rrm",
                instance=instance,
                state=state,
                event=event,
                solve_status=(core_result.solution.solve_status),
            )

        results.append(result)

        if stop:
            break

    return Phase11PolicyRun(
        policy_key="dca_rrm",
        solver_backend=solver_backend,
        timeline=selected,
        event_results=tuple(results),
        final_state=state,
    )
