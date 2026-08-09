"""Phase 11 execution semantics for Table 5 PR and FR policies.

This adapter preserves the validated Phase-10 PR/FR mechanisms while
applying the Phase-11 A036 continuation rule to explicitly infeasible
Regular booking requests.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from barge_rerouting.disruption import (
    dynamic_full_reroute_run as dynamic_fr,
)
from barge_rerouting.disruption import (
    partial_reroute as partial_reroute,
)
from barge_rerouting.disruption.dynamic_full_reroute_run import (
    DynamicFullRerouteEventResult,
)
from barge_rerouting.disruption.partial_reroute import (
    PartialRerouteEventResult,
)
from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.disruption.timeline import (
    OperationalTimeline,
    OperationalTimelineEntry,
    build_operational_timeline,
)
from barge_rerouting.domain import CustomerCategory
from barge_rerouting.experiments.phase11_execution import (
    advance_regular_feasibility_rejection,
    is_proven_infeasible_status,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)

type CoreTable5EventResult = PartialRerouteEventResult | DynamicFullRerouteEventResult

TABLE5_EXECUTION_TOLERANCE = 1e-9


class Table5EventDisposition(StrEnum):
    """Phase-11 interpretation of one operational event."""

    CORE_PROCESSED = "core_processed"
    REGULAR_FEASIBILITY_REJECTION = "regular_feasibility_rejection"
    SOLVER_FAILURE = "solver_failure"


@dataclass(frozen=True, slots=True)
class Table5PolicyEventResult:
    """Phase-11 wrapper around one PR/FR operational event."""

    policy_key: str
    entry: OperationalTimelineEntry
    disposition: Table5EventDisposition
    state_before: RecoveryOperationalState
    state_after: RecoveryOperationalState
    core_result: CoreTable5EventResult | None
    solve_status: str | None = None

    def __post_init__(self) -> None:
        """Validate wrapper consistency."""
        if self.policy_key not in (
            "pr",
            "fr",
        ):
            raise ValueError("Table 5 policy_key must be 'pr' or 'fr'.")

        if not isinstance(
            self.entry,
            OperationalTimelineEntry,
        ):
            raise TypeError("entry must be an OperationalTimelineEntry.")

        if not isinstance(
            self.disposition,
            Table5EventDisposition,
        ):
            raise TypeError("disposition must be a Table5EventDisposition.")

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

        if self.state_after.instance_fingerprint != self.state_before.instance_fingerprint:
            raise ValueError("Operational states belong to different instances.")

        if self.core_result is not None:
            if self.core_result.entry != self.entry:
                raise ValueError("Core result must belong to the wrapped event.")

        if self.disposition is Table5EventDisposition.CORE_PROCESSED:
            if self.core_result is None:
                raise ValueError("A core-processed event requires a core result.")

            if not self.core_result.event_was_processed:
                raise ValueError("CORE_PROCESSED requires a processed core result.")

            if self.state_after != self.core_result.state_after:
                raise ValueError("Core-processed state must equal the core state.")

        elif self.disposition is Table5EventDisposition.REGULAR_FEASIBILITY_REJECTION:
            if not self.entry.is_booking:
                raise ValueError("A036 applies only to booking events.")

            if self.core_result is None:
                raise ValueError("A036 must retain the unsolved core result.")

            if self.core_result.event_was_processed:
                raise ValueError("A036 requires an unprocessed core booking.")

            if self.solve_status is None:
                raise ValueError("A036 must preserve the infeasible solver status.")

            event = self.entry.booking_event

            if event is None:
                raise ValueError("A036 booking entry has no booking event.")

            if event.demand.category is not CustomerCategory.REGULAR:
                raise ValueError("A036 applies only to Regular requests.")

            if not is_proven_infeasible_status(self.solve_status):
                raise ValueError("A036 requires certified infeasibility.")

            if (
                self.state_after.booking_state.processed_event_count
                != self.state_before.booking_state.processed_event_count + 1
            ):
                raise ValueError("A036 must advance booking history exactly once.")

        elif self.disposition is Table5EventDisposition.SOLVER_FAILURE:
            if self.core_result is None:
                raise ValueError("A solver failure must retain its core result.")

            if self.core_result.event_was_processed:
                raise ValueError("SOLVER_FAILURE requires an unprocessed core result.")

            if self.state_after != self.state_before:
                raise ValueError("A solver failure cannot change operational state.")

    @property
    def accepted_volume(self) -> float:
        """Return newly accepted volume."""
        if (
            self.disposition is not Table5EventDisposition.CORE_PROCESSED
            or self.core_result is None
        ):
            return 0.0

        return float(self.core_result.accepted_volume)

    @property
    def realised_revenue(self) -> float:
        """Return realised booking revenue."""
        if (
            self.disposition is not Table5EventDisposition.CORE_PROCESSED
            or self.core_result is None
        ):
            return 0.0

        return float(self.core_result.realised_revenue)


@dataclass(frozen=True, slots=True)
class Table5OperationalPolicyRun:
    """Phase-11 PR or FR trajectory."""

    policy_key: str
    solver_backend: SolverBackend
    timeline: OperationalTimeline
    event_results: tuple[
        Table5PolicyEventResult,
        ...,
    ]
    final_state: RecoveryOperationalState

    def __post_init__(self) -> None:
        """Validate event order and state chaining."""
        if self.policy_key not in (
            "pr",
            "fr",
        ):
            raise ValueError("policy_key must be 'pr' or 'fr'.")

        if not isinstance(
            self.solver_backend,
            SolverBackend,
        ):
            raise TypeError("solver_backend must be a SolverBackend.")

        if not isinstance(
            self.timeline,
            OperationalTimeline,
        ):
            raise TypeError("timeline must be an OperationalTimeline.")

        if len(self.event_results) > self.timeline.event_count:
            raise ValueError("Run results cannot exceed timeline length.")

        for position, result in enumerate(
            self.event_results,
        ):
            if result.entry != self.timeline.entries[position]:
                raise ValueError("Table 5 results must follow timeline order.")

            if result.policy_key != self.policy_key:
                raise ValueError("All events must belong to the run policy.")

        for previous, current in zip(
            self.event_results,
            self.event_results[1:],
            strict=False,
        ):
            if current.state_before != previous.state_after:
                raise ValueError("Operational state chain is broken.")

        if self.event_results:
            if self.final_state != self.event_results[-1].state_after:
                raise ValueError("final_state must equal the final event state.")

    @property
    def completed(self) -> bool:
        """Return whether the full operational timeline completed."""
        return (
            len(self.event_results) == self.timeline.event_count and self.solver_failure_count == 0
        )

    @property
    def feasibility_rejection_count(self) -> int:
        """Return A036 continuation count."""
        return sum(
            result.disposition is Table5EventDisposition.REGULAR_FEASIBILITY_REJECTION
            for result in self.event_results
        )

    @property
    def feasibility_rejection_ids(
        self,
    ) -> tuple[str, ...]:
        """Return demand IDs rejected through A036."""
        demand_ids: list[str] = []

        for result in self.event_results:
            if result.disposition is not Table5EventDisposition.REGULAR_FEASIBILITY_REJECTION:
                continue

            event = result.entry.booking_event

            if event is None:
                raise RuntimeError("A036 result lost its booking event.")

            demand_ids.append(event.demand_id)

        return tuple(demand_ids)

    @property
    def solver_failure_count(self) -> int:
        """Return non-A036 unprocessed solver events."""
        return sum(
            result.disposition is Table5EventDisposition.SOLVER_FAILURE
            for result in self.event_results
        )

    @property
    def processed_booking_count(self) -> int:
        """Return bookings consumed from the contractual timeline."""
        return sum(
            result.entry.is_booking
            and result.disposition is not Table5EventDisposition.SOLVER_FAILURE
            for result in self.event_results
        )

    @property
    def processed_status_count(self) -> int:
        """Return successfully processed forecast/status events."""
        return sum(
            result.entry.is_status_update
            and result.disposition is Table5EventDisposition.CORE_PROCESSED
            for result in self.event_results
        )

    @property
    def accepted_volume(self) -> float:
        """Return newly accepted booking volume."""
        return float(sum(result.accepted_volume for result in self.event_results))

    @property
    def total_revenue(self) -> float:
        """Return realised booking revenue before truck penalties."""
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
        """Return booking revenue less truck penalty."""
        return float(self.total_revenue - self.total_truck_penalty)

    @property
    def ordinary_rejection_count(self) -> int:
        """Return solved bookings accepting effectively zero volume."""
        return sum(
            result.entry.is_booking
            and result.disposition is Table5EventDisposition.CORE_PROCESSED
            and result.accepted_volume <= TABLE5_EXECUTION_TOLERANCE
            for result in self.event_results
        )


def _solution_status(
    result: CoreTable5EventResult,
) -> str | None:
    """Return the solver status retained by one core event result."""
    value: object | None = None

    if result.entry.is_booking:
        solution = result.booking_solution

        if solution is None:
            return None

        value = solution.solve_status

    elif isinstance(
        result,
        PartialRerouteEventResult,
    ):
        recovery_solution = result.recovery_solution

        if recovery_solution is not None:
            value = recovery_solution.solve_status

    elif isinstance(
        result,
        DynamicFullRerouteEventResult,
    ):
        status_solution = result.status_solution

        if status_solution is not None:
            value = status_solution.solve_status

    if value is None:
        return None

    if not isinstance(
        value,
        str,
    ):
        raise TypeError("Core solver status must be a string.")

    return value


def _can_apply_a036(
    result: CoreTable5EventResult,
) -> bool:
    """Return whether one failed core booking qualifies for A036."""
    if not result.entry.is_booking:
        return False

    event = result.entry.booking_event

    if event is None:
        return False

    if event.demand.category is not CustomerCategory.REGULAR:
        return False

    status = _solution_status(result)

    if status is None:
        return False

    return bool(is_proven_infeasible_status(status))


def _advance_a036_operational_state(
    instance: ExperimentInstance,
    state: RecoveryOperationalState,
    entry: OperationalTimelineEntry,
    *,
    solve_status: str,
) -> RecoveryOperationalState:
    """Apply A036 while preserving the recovery overlay."""
    event = entry.booking_event

    if event is None:
        raise ValueError("A036 requires a booking entry.")

    booking_state = advance_regular_feasibility_rejection(
        instance,
        state.booking_state,
        event,
        solve_status=solve_status,
    )

    return state.with_booking_state(booking_state)


def _wrapped_result(
    *,
    policy_key: str,
    instance: ExperimentInstance,
    state: RecoveryOperationalState,
    core_result: CoreTable5EventResult,
) -> tuple[
    Table5PolicyEventResult,
    RecoveryOperationalState,
    bool,
]:
    """Interpret one Phase-10 core result under Phase-11 semantics."""
    if core_result.event_was_processed:
        wrapped = Table5PolicyEventResult(
            policy_key=policy_key,
            entry=core_result.entry,
            disposition=(Table5EventDisposition.CORE_PROCESSED),
            state_before=state,
            state_after=core_result.state_after,
            core_result=core_result,
            solve_status=(_solution_status(core_result)),
        )

        return (
            wrapped,
            core_result.state_after,
            False,
        )

    status = _solution_status(core_result)

    if status is not None and _can_apply_a036(core_result):
        state_after = _advance_a036_operational_state(
            instance,
            state,
            core_result.entry,
            solve_status=status,
        )

        wrapped = Table5PolicyEventResult(
            policy_key=policy_key,
            entry=core_result.entry,
            disposition=(Table5EventDisposition.REGULAR_FEASIBILITY_REJECTION),
            state_before=state,
            state_after=state_after,
            core_result=core_result,
            solve_status=status,
        )

        return (
            wrapped,
            state_after,
            False,
        )

    wrapped = Table5PolicyEventResult(
        policy_key=policy_key,
        entry=core_result.entry,
        disposition=(Table5EventDisposition.SOLVER_FAILURE),
        state_before=state,
        state_after=state,
        core_result=core_result,
        solve_status=status,
    )

    return (
        wrapped,
        state,
        True,
    )


def run_phase11_table5_pr(
    instance: ExperimentInstance,
    *,
    status_updates: Sequence[ServiceStatusUpdateEvent],
    truck_penalty_per_teu_by_demand: Mapping[
        str,
        float,
    ],
    timeline: OperationalTimeline | None = None,
    solver_backend: SolverBackend = (SolverBackend.CPLEX_CE_AWARE),
) -> Table5OperationalPolicyRun:
    """Run Table-5 Partial-Reroute with A036 continuation."""
    if not isinstance(
        instance,
        ExperimentInstance,
    ):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        solver_backend,
        SolverBackend,
    ):
        raise TypeError("solver_backend must be a SolverBackend.")

    selected_timeline = (
        build_operational_timeline(
            instance,
            status_updates=status_updates,
        )
        if timeline is None
        else timeline
    )

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    known_updates: list[ServiceStatusUpdateEvent] = []

    results: list[Table5PolicyEventResult] = []

    for entry in selected_timeline.entries:
        if entry.is_status_update:
            status_event = entry.status_update

            if status_event is None:
                raise ValueError("Status entry has no status event.")

            known_updates.append(status_event)

            core_result = partial_reroute._status_result(
                instance,
                state,
                entry,
                tuple(known_updates),
                truck_penalty_per_teu_by_demand,
                solver_backend,
            )
        else:
            core_result = partial_reroute._booking_result(
                instance,
                state,
                entry,
                tuple(known_updates),
            )

        (
            wrapped,
            state,
            stop,
        ) = _wrapped_result(
            policy_key="pr",
            instance=instance,
            state=state,
            core_result=core_result,
        )

        results.append(wrapped)

        if stop:
            break

    return Table5OperationalPolicyRun(
        policy_key="pr",
        solver_backend=solver_backend,
        timeline=selected_timeline,
        event_results=tuple(results),
        final_state=state,
    )


def run_phase11_table5_fr(
    instance: ExperimentInstance,
    *,
    truck_penalty_per_teu_by_demand: Mapping[
        str,
        float,
    ],
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
    timeline: OperationalTimeline | None = None,
    solver_backend: SolverBackend = (SolverBackend.CPLEX_CE_AWARE),
) -> Table5OperationalPolicyRun:
    """Run Table-5 Full-Reroute with A036 continuation."""
    if not isinstance(
        instance,
        ExperimentInstance,
    ):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        solver_backend,
        SolverBackend,
    ):
        raise TypeError("solver_backend must be a SolverBackend.")

    selected_timeline = (
        build_operational_timeline(
            instance,
            status_updates=status_updates,
        )
        if timeline is None
        else timeline
    )

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    known_updates: list[ServiceStatusUpdateEvent] = []

    results: list[Table5PolicyEventResult] = []

    for entry in selected_timeline.entries:
        if entry.is_status_update:
            status_event = entry.status_update

            if status_event is None:
                raise ValueError("Status entry has no status event.")

            known_updates.append(status_event)

            core_result = dynamic_fr._status_result(
                instance,
                state,
                entry,
                tuple(known_updates),
                truck_penalty_per_teu_by_demand,
                solver_backend,
            )
        else:
            core_result = dynamic_fr._booking_result(
                instance,
                state,
                entry,
                tuple(known_updates),
                truck_penalty_per_teu_by_demand,
                solver_backend,
            )

        (
            wrapped,
            state,
            stop,
        ) = _wrapped_result(
            policy_key="fr",
            instance=instance,
            state=state,
            core_result=core_result,
        )

        results.append(wrapped)

        if stop:
            break

    return Table5OperationalPolicyRun(
        policy_key="fr",
        solver_backend=solver_backend,
        timeline=selected_timeline,
        event_results=tuple(results),
        final_state=state,
    )
