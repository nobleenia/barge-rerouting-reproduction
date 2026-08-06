"""Canonical four-mechanism evaluation including DCA-RRM."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.run import (
    FullRerouteRun,
    run_full_reroute,
)
from barge_rerouting.revenue_management.evaluation import (
    ForecastSensitivityRegime,
    build_attribute_conditioned_forecast_provider,
    default_sensitivity_regimes,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.rrm_run import (
    TimeAwareDcaRrmRun,
    run_time_aware_dca_rrm,
)
from barge_rerouting.revenue_management.run import (
    TimeAwareDcaRmRun,
    run_time_aware_dca_rm,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    BookingTimeline,
    TimeAwareSequentialDcaRun,
    build_booking_timeline,
    run_time_aware_sequential_dca,
)

PHASE9_EVALUATION_TOLERANCE = 1e-6


def _validate_maximum_volume(
    value: object,
) -> int:
    """Validate a positive integer forecast-volume maximum."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("maximum_volume must be an integer.")

    if value <= 0:
        raise ValueError("maximum_volume must be strictly positive.")

    return value


def _validate_lookahead(
    value: int | None,
) -> int | None:
    """Validate an optional non-negative look-ahead."""
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("lookahead_periods must be an integer or None.")

    if value < 0:
        raise ValueError("lookahead_periods must be non-negative.")

    return value


def _optional_float(
    value: object | None,
) -> float | None:
    """Return a finite optional float."""
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("Expected a numerical value or None.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError("Numerical reporting values must be finite.")

    return numeric


@dataclass(frozen=True, slots=True)
class Phase9EventRecord:
    """One event result for one evaluated mechanism."""

    policy_key: str
    policy_label: str
    mechanism: str
    sequence_number: int
    event_id: str
    decision_time: int
    demand_id: str
    category: str
    requested_volume: float
    event_status: str
    solve_status: str
    acceptance_fraction: float | None
    accepted_volume: float | None
    current_realised_revenue: float | None
    optimisation_objective: float | None
    future_expected_revenue: float | None
    forecast_count: int
    protected_forecast_count: int
    selected_protection_volume: float
    forecast_ids: tuple[str, ...]
    protected_forecast_ids: tuple[str, ...]
    rerouted_prior_demand_ids: tuple[str, ...]
    released_arc_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase9PolicySummary:
    """Aggregate result for one evaluated policy."""

    policy_key: str
    policy_label: str
    mechanism: str
    value_interpretation: str | None
    occurrence_probability: float | None
    maximum_forecast_volume: int | None
    lookahead_periods: int | None
    completed: bool
    attempted_events: int
    processed_events: int
    accepted_volume: float
    realised_revenue: float
    summed_optimisation_objectives: float
    summed_expected_future_contribution: float
    forecast_candidate_count: int
    positive_protection_count: int
    selected_protection_volume: float
    events_reoptimising_prior_commitments: int
    accepted_demand_ids: tuple[str, ...]
    failure_event_id: str | None
    processed_event_delta_vs_dca: int
    accepted_volume_delta_vs_dca: float
    realised_revenue_delta_vs_dca: float
    common_prefix_accepted_volume_delta: float
    common_prefix_revenue_delta: float
    continuation_volume_after_dca_failure: float
    continuation_revenue_after_dca_failure: float
    paired_acceptance_improvement_count: int


@dataclass(frozen=True, slots=True)
class Phase9CanonicalEvaluation:
    """Complete canonical evaluation of the four mechanisms."""

    instance_fingerprint: str
    total_booking_events: int
    maximum_forecast_volume: int
    lookahead_periods: int | None
    regimes: tuple[ForecastSensitivityRegime, ...]
    summaries: tuple[Phase9PolicySummary, ...]
    events: tuple[Phase9EventRecord, ...]

    def __post_init__(self) -> None:
        """Validate evaluation shape and policy uniqueness."""
        if len(self.instance_fingerprint) != 64:
            raise ValueError("instance_fingerprint must be a SHA-256 value.")

        if self.total_booking_events <= 0:
            raise ValueError("total_booking_events must be positive.")

        _validate_maximum_volume(self.maximum_forecast_volume)
        _validate_lookahead(self.lookahead_periods)

        expected_policy_count = 2 + 2 * len(self.regimes)

        if len(self.summaries) != expected_policy_count:
            raise ValueError("Phase 9 requires DCA, DCA-R, and one DCA-RM/DCA-RRM pair per regime.")

        policy_keys = tuple(summary.policy_key for summary in self.summaries)

        if len(set(policy_keys)) != len(policy_keys):
            raise ValueError("Policy summary keys must be unique.")

        expected_event_count = expected_policy_count * self.total_booking_events

        if len(self.events) != expected_event_count:
            raise ValueError("Event rows must cover every policy and booking event.")

    def summary_for(
        self,
        policy_key: str,
    ) -> Phase9PolicySummary:
        """Return one policy summary."""
        for summary in self.summaries:
            if summary.policy_key == policy_key:
                return summary

        raise KeyError(f"No Phase 9 policy summary for {policy_key}.")

    def events_for(
        self,
        policy_key: str,
    ) -> tuple[Phase9EventRecord, ...]:
        """Return complete event rows for one policy."""
        records = tuple(record for record in self.events if record.policy_key == policy_key)

        if not records:
            raise KeyError(f"No Phase 9 event records for {policy_key}.")

        return records


def _not_run_record(
    event: BookingDecisionEvent,
    *,
    policy_key: str,
    policy_label: str,
    mechanism: str,
) -> Phase9EventRecord:
    """Build one unattempted event row."""
    return Phase9EventRecord(
        policy_key=policy_key,
        policy_label=policy_label,
        mechanism=mechanism,
        sequence_number=event.sequence_number,
        event_id=event.event_id,
        decision_time=event.decision_time,
        demand_id=event.demand_id,
        category=str(event.demand.category.value),
        requested_volume=float(event.demand.volume),
        event_status="not-run",
        solve_status="not-run",
        acceptance_fraction=None,
        accepted_volume=None,
        current_realised_revenue=None,
        optimisation_objective=None,
        future_expected_revenue=None,
        forecast_count=0,
        protected_forecast_count=0,
        selected_protection_volume=0.0,
        forecast_ids=(),
        protected_forecast_ids=(),
        rerouted_prior_demand_ids=(),
        released_arc_ids=(),
    )


def _dca_event_records(
    timeline: BookingTimeline,
    run: TimeAwareSequentialDcaRun,
) -> tuple[Phase9EventRecord, ...]:
    """Build complete Sequential DCA event rows."""
    by_event_id = {result.event.event_id: result for result in run.results}
    records: list[Phase9EventRecord] = []

    for event in timeline.events:
        result = by_event_id.get(event.event_id)

        if result is None:
            records.append(
                _not_run_record(
                    event,
                    policy_key="dca",
                    policy_label="Sequential DCA",
                    mechanism="DCA",
                )
            )
            continue

        if not result.is_solved:
            records.append(
                Phase9EventRecord(
                    policy_key="dca",
                    policy_label="Sequential DCA",
                    mechanism="DCA",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=str(event.demand.category.value),
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=str(result.solve_status),
                    acceptance_fraction=None,
                    accepted_volume=None,
                    current_realised_revenue=None,
                    optimisation_objective=None,
                    future_expected_revenue=None,
                    forecast_count=0,
                    protected_forecast_count=0,
                    selected_protection_volume=0.0,
                    forecast_ids=(),
                    protected_forecast_ids=(),
                    rerouted_prior_demand_ids=(),
                    released_arc_ids=(),
                )
            )
            continue

        revenue = _optional_float(result.objective_value)

        records.append(
            Phase9EventRecord(
                policy_key="dca",
                policy_label="Sequential DCA",
                mechanism="DCA",
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=str(event.demand.category.value),
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=str(result.solve_status),
                acceptance_fraction=_optional_float(result.acceptance_fraction),
                accepted_volume=float(result.accepted_volume),
                current_realised_revenue=revenue,
                optimisation_objective=revenue,
                future_expected_revenue=0.0,
                forecast_count=0,
                protected_forecast_count=0,
                selected_protection_volume=0.0,
                forecast_ids=(),
                protected_forecast_ids=(),
                rerouted_prior_demand_ids=(),
                released_arc_ids=(),
            )
        )

    return tuple(records)


def _reroute_event_records(
    timeline: BookingTimeline,
    run: FullRerouteRun,
) -> tuple[Phase9EventRecord, ...]:
    """Build complete DCA-R event rows."""
    by_event_id = {result.event.event_id: result for result in run.results}
    records: list[Phase9EventRecord] = []

    for event in timeline.events:
        result = by_event_id.get(event.event_id)

        if result is None:
            records.append(
                _not_run_record(
                    event,
                    policy_key="dca_r",
                    policy_label="DCA-R / Full-Reroute",
                    mechanism="DCA-R",
                )
            )
            continue

        if not result.event_was_processed:
            records.append(
                Phase9EventRecord(
                    policy_key="dca_r",
                    policy_label="DCA-R / Full-Reroute",
                    mechanism="DCA-R",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=str(event.demand.category.value),
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=str(result.reroute_solution.solve_status),
                    acceptance_fraction=None,
                    accepted_volume=None,
                    current_realised_revenue=None,
                    optimisation_objective=None,
                    future_expected_revenue=None,
                    forecast_count=0,
                    protected_forecast_count=0,
                    selected_protection_volume=0.0,
                    forecast_ids=(),
                    protected_forecast_ids=(),
                    rerouted_prior_demand_ids=tuple(
                        str(demand_id) for demand_id in (result.rerouted_demand_ids)
                    ),
                    released_arc_ids=tuple(str(arc_id) for arc_id in result.released_arc_ids),
                )
            )
            continue

        acceptance = _optional_float(result.reroute_acceptance_fraction)
        revenue = _optional_float(result.reroute_solution.objective_value)

        records.append(
            Phase9EventRecord(
                policy_key="dca_r",
                policy_label="DCA-R / Full-Reroute",
                mechanism="DCA-R",
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=str(event.demand.category.value),
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=str(result.reroute_solution.solve_status),
                acceptance_fraction=acceptance,
                accepted_volume=(float(event.demand.volume) * float(acceptance or 0.0)),
                current_realised_revenue=revenue,
                optimisation_objective=revenue,
                future_expected_revenue=0.0,
                forecast_count=0,
                protected_forecast_count=0,
                selected_protection_volume=0.0,
                forecast_ids=(),
                protected_forecast_ids=(),
                rerouted_prior_demand_ids=tuple(
                    str(demand_id) for demand_id in (result.rerouted_demand_ids)
                ),
                released_arc_ids=tuple(str(arc_id) for arc_id in result.released_arc_ids),
            )
        )

    return tuple(records)


def _rm_event_records(
    timeline: BookingTimeline,
    regime: ForecastSensitivityRegime,
    run: TimeAwareDcaRmRun,
) -> tuple[Phase9EventRecord, ...]:
    """Build complete DCA-RM event rows."""
    by_event_id = {result.event.event_id: result for result in run.results}
    records: list[Phase9EventRecord] = []

    for event in timeline.events:
        result = by_event_id.get(event.event_id)

        if result is None:
            records.append(
                _not_run_record(
                    event,
                    policy_key=regime.key,
                    policy_label=regime.label,
                    mechanism="DCA-RM",
                )
            )
            continue

        if not result.is_solved:
            records.append(
                Phase9EventRecord(
                    policy_key=regime.key,
                    policy_label=regime.label,
                    mechanism="DCA-RM",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=str(event.demand.category.value),
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=str(result.solve_status),
                    acceptance_fraction=None,
                    accepted_volume=None,
                    current_realised_revenue=None,
                    optimisation_objective=None,
                    future_expected_revenue=None,
                    forecast_count=len(result.forecast_ids),
                    protected_forecast_count=0,
                    selected_protection_volume=0.0,
                    forecast_ids=tuple(str(forecast_id) for forecast_id in result.forecast_ids),
                    protected_forecast_ids=(),
                    rerouted_prior_demand_ids=(),
                    released_arc_ids=(),
                )
            )
            continue

        positive = tuple(
            protection
            for protection in result.protections
            if (protection.protected_volume > PHASE9_EVALUATION_TOLERANCE)
        )

        records.append(
            Phase9EventRecord(
                policy_key=regime.key,
                policy_label=regime.label,
                mechanism="DCA-RM",
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=str(event.demand.category.value),
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=str(result.solve_status),
                acceptance_fraction=_optional_float(result.acceptance_fraction),
                accepted_volume=float(result.accepted_volume),
                current_realised_revenue=_optional_float(result.current_realised_revenue),
                optimisation_objective=_optional_float(result.optimisation_objective),
                future_expected_revenue=_optional_float(result.future_expected_revenue),
                forecast_count=len(result.forecast_ids),
                protected_forecast_count=len(positive),
                selected_protection_volume=float(
                    sum(protection.protected_volume for protection in positive)
                ),
                forecast_ids=tuple(str(forecast_id) for forecast_id in result.forecast_ids),
                protected_forecast_ids=tuple(
                    str(protection.forecast_id) for protection in positive
                ),
                rerouted_prior_demand_ids=(),
                released_arc_ids=(),
            )
        )

    return tuple(records)


def _rrm_key(
    regime: ForecastSensitivityRegime,
) -> str:
    """Return the matching DCA-RRM policy key."""
    if regime.key.startswith("rm_"):
        return f"rrm_{regime.key[3:]}"

    return f"rrm_{regime.key}"


def _rrm_label(
    regime: ForecastSensitivityRegime,
) -> str:
    """Return the matching DCA-RRM policy label."""
    return f"DCA-RRM {regime.value_interpretation.value} p={regime.occurrence_probability:.2f}"


def _rrm_event_records(
    timeline: BookingTimeline,
    regime: ForecastSensitivityRegime,
    run: TimeAwareDcaRrmRun,
) -> tuple[Phase9EventRecord, ...]:
    """Build complete DCA-RRM event rows."""
    policy_key = _rrm_key(regime)
    policy_label = _rrm_label(regime)
    by_event_id = {result.event.event_id: result for result in run.results}
    records: list[Phase9EventRecord] = []

    for event in timeline.events:
        result = by_event_id.get(event.event_id)

        if result is None:
            records.append(
                _not_run_record(
                    event,
                    policy_key=policy_key,
                    policy_label=policy_label,
                    mechanism="DCA-RRM",
                )
            )
            continue

        if not result.event_was_processed:
            records.append(
                Phase9EventRecord(
                    policy_key=policy_key,
                    policy_label=policy_label,
                    mechanism="DCA-RRM",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=str(event.demand.category.value),
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=str(result.solution.solve_status),
                    acceptance_fraction=None,
                    accepted_volume=None,
                    current_realised_revenue=None,
                    optimisation_objective=None,
                    future_expected_revenue=None,
                    forecast_count=len(result.forecast_ids),
                    protected_forecast_count=0,
                    selected_protection_volume=0.0,
                    forecast_ids=tuple(str(forecast_id) for forecast_id in result.forecast_ids),
                    protected_forecast_ids=(),
                    rerouted_prior_demand_ids=tuple(
                        str(demand_id) for demand_id in (result.rerouted_demand_ids)
                    ),
                    released_arc_ids=tuple(str(arc_id) for arc_id in result.released_arc_ids),
                )
            )
            continue

        records.append(
            Phase9EventRecord(
                policy_key=policy_key,
                policy_label=policy_label,
                mechanism="DCA-RRM",
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=str(event.demand.category.value),
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=str(result.solution.solve_status),
                acceptance_fraction=_optional_float(result.acceptance_fraction),
                accepted_volume=float(result.accepted_volume),
                current_realised_revenue=float(result.current_realised_revenue),
                optimisation_objective=float(result.optimisation_objective),
                future_expected_revenue=float(result.future_expected_revenue),
                forecast_count=len(result.forecast_ids),
                protected_forecast_count=len(result.protected_forecast_ids),
                selected_protection_volume=float(result.selected_protection_volume),
                forecast_ids=tuple(str(forecast_id) for forecast_id in result.forecast_ids),
                protected_forecast_ids=tuple(
                    str(forecast_id) for forecast_id in (result.protected_forecast_ids)
                ),
                rerouted_prior_demand_ids=tuple(
                    str(demand_id) for demand_id in (result.rerouted_demand_ids)
                ),
                released_arc_ids=tuple(str(arc_id) for arc_id in result.released_arc_ids),
            )
        )

    return tuple(records)


def _summary(
    *,
    policy_key: str,
    policy_label: str,
    mechanism: str,
    value_interpretation: str | None,
    occurrence_probability: float | None,
    maximum_forecast_volume: int | None,
    lookahead_periods: int | None,
    completed: bool,
    attempted_events: int,
    processed_events: int,
    accepted_volume: float,
    realised_revenue: float,
    summed_objectives: float,
    summed_future_contribution: float,
    accepted_demand_ids: tuple[str, ...],
    failure_event_id: str | None,
    records: tuple[Phase9EventRecord, ...],
    baseline_processed_events: int,
    baseline_accepted_volume: float,
    baseline_realised_revenue: float,
    baseline_records: tuple[Phase9EventRecord, ...],
) -> Phase9PolicySummary:
    """Build one policy summary against Sequential DCA."""
    common_prefix_length = min(
        baseline_processed_events,
        processed_events,
    )

    baseline_prefix = baseline_records[:common_prefix_length]
    policy_prefix = records[:common_prefix_length]

    baseline_prefix_volume = float(sum(record.accepted_volume or 0.0 for record in baseline_prefix))
    policy_prefix_volume = float(sum(record.accepted_volume or 0.0 for record in policy_prefix))

    baseline_prefix_revenue = float(
        sum(record.current_realised_revenue or 0.0 for record in baseline_prefix)
    )
    policy_prefix_revenue = float(
        sum(record.current_realised_revenue or 0.0 for record in policy_prefix)
    )

    paired_improvements = sum(
        1
        for baseline_record, policy_record in zip(
            baseline_prefix,
            policy_prefix,
            strict=True,
        )
        if (
            baseline_record.acceptance_fraction is not None
            and policy_record.acceptance_fraction is not None
            and (
                policy_record.acceptance_fraction - baseline_record.acceptance_fraction
                > PHASE9_EVALUATION_TOLERANCE
            )
        )
    )

    positive_protection_count = sum(
        record.protected_forecast_count for record in records if record.event_status == "solved"
    )
    selected_protection_volume = float(
        sum(
            record.selected_protection_volume
            for record in records
            if record.event_status == "solved"
        )
    )

    return Phase9PolicySummary(
        policy_key=policy_key,
        policy_label=policy_label,
        mechanism=mechanism,
        value_interpretation=value_interpretation,
        occurrence_probability=occurrence_probability,
        maximum_forecast_volume=(maximum_forecast_volume),
        lookahead_periods=lookahead_periods,
        completed=completed,
        attempted_events=attempted_events,
        processed_events=processed_events,
        accepted_volume=float(accepted_volume),
        realised_revenue=float(realised_revenue),
        summed_optimisation_objectives=float(summed_objectives),
        summed_expected_future_contribution=float(summed_future_contribution),
        forecast_candidate_count=sum(
            record.forecast_count for record in records if record.event_status != "not-run"
        ),
        positive_protection_count=(positive_protection_count),
        selected_protection_volume=(selected_protection_volume),
        events_reoptimising_prior_commitments=sum(
            1
            for record in records
            if (record.event_status == "solved" and record.rerouted_prior_demand_ids)
        ),
        accepted_demand_ids=accepted_demand_ids,
        failure_event_id=failure_event_id,
        processed_event_delta_vs_dca=(processed_events - baseline_processed_events),
        accepted_volume_delta_vs_dca=(accepted_volume - baseline_accepted_volume),
        realised_revenue_delta_vs_dca=(realised_revenue - baseline_realised_revenue),
        common_prefix_accepted_volume_delta=(policy_prefix_volume - baseline_prefix_volume),
        common_prefix_revenue_delta=(policy_prefix_revenue - baseline_prefix_revenue),
        continuation_volume_after_dca_failure=(accepted_volume - policy_prefix_volume),
        continuation_revenue_after_dca_failure=(realised_revenue - policy_prefix_revenue),
        paired_acceptance_improvement_count=(paired_improvements),
    )


def evaluate_phase9_canonical(
    instance: ExperimentInstance,
    *,
    regimes: Sequence[ForecastSensitivityRegime] | None = None,
    maximum_volume: int | None = None,
    lookahead_periods: int | None = None,
) -> Phase9CanonicalEvaluation:
    """Evaluate DCA, DCA-R, DCA-RM, and DCA-RRM.

    The same attribute-conditioned synthetic forecast provider is
    supplied to DCA-RM and DCA-RRM for every sensitivity regime.

    This is a mechanism evaluation, not an exact numerical
    reproduction of the paper's unreported experimental inputs.
    """
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    selected_regimes = default_sensitivity_regimes() if regimes is None else tuple(regimes)

    if not selected_regimes:
        raise ValueError("At least one forecast regime is required.")

    for regime in selected_regimes:
        if not isinstance(
            regime,
            ForecastSensitivityRegime,
        ):
            raise TypeError("Every regime must be a ForecastSensitivityRegime.")

    regime_keys = tuple(regime.key for regime in selected_regimes)

    if len(set(regime_keys)) != len(regime_keys):
        raise ValueError("Forecast-regime keys must be unique.")

    selected_maximum_volume = (
        _validate_maximum_volume(maximum_volume)
        if maximum_volume is not None
        else _validate_maximum_volume(instance.config.demand_generation.maximum_volume)
    )
    selected_lookahead = _validate_lookahead(lookahead_periods)

    timeline = build_booking_timeline(instance)

    dca_run = run_time_aware_sequential_dca(
        instance,
        timeline=timeline,
    )
    reroute_run = run_full_reroute(
        instance,
        timeline=timeline,
    )

    dca_records = _dca_event_records(
        timeline,
        dca_run,
    )
    reroute_records = _reroute_event_records(
        timeline,
        reroute_run,
    )

    baseline_processed = dca_run.final_state.processed_event_count
    baseline_volume = float(dca_run.accepted_volume)
    baseline_revenue = float(dca_run.total_revenue)

    dca_failure = dca_run.failure_result
    reroute_failure = reroute_run.failure_result

    summaries: list[Phase9PolicySummary] = [
        _summary(
            policy_key="dca",
            policy_label="Sequential DCA",
            mechanism="DCA",
            value_interpretation=None,
            occurrence_probability=None,
            maximum_forecast_volume=None,
            lookahead_periods=None,
            completed=dca_run.completed,
            attempted_events=len(dca_run.results),
            processed_events=baseline_processed,
            accepted_volume=baseline_volume,
            realised_revenue=baseline_revenue,
            summed_objectives=baseline_revenue,
            summed_future_contribution=0.0,
            accepted_demand_ids=tuple(dca_run.final_state.accepted_demand_ids),
            failure_event_id=(None if dca_failure is None else dca_failure.event.event_id),
            records=dca_records,
            baseline_processed_events=baseline_processed,
            baseline_accepted_volume=baseline_volume,
            baseline_realised_revenue=baseline_revenue,
            baseline_records=dca_records,
        ),
        _summary(
            policy_key="dca_r",
            policy_label="DCA-R / Full-Reroute",
            mechanism="DCA-R",
            value_interpretation=None,
            occurrence_probability=None,
            maximum_forecast_volume=None,
            lookahead_periods=None,
            completed=reroute_run.completed,
            attempted_events=len(reroute_run.results),
            processed_events=(reroute_run.processed_event_count),
            accepted_volume=float(reroute_run.accepted_volume),
            realised_revenue=float(reroute_run.total_revenue),
            summed_objectives=float(reroute_run.total_revenue),
            summed_future_contribution=0.0,
            accepted_demand_ids=tuple(reroute_run.final_state.accepted_demand_ids),
            failure_event_id=(None if reroute_failure is None else reroute_failure.event.event_id),
            records=reroute_records,
            baseline_processed_events=baseline_processed,
            baseline_accepted_volume=baseline_volume,
            baseline_realised_revenue=baseline_revenue,
            baseline_records=dca_records,
        ),
    ]
    events: list[Phase9EventRecord] = [
        *dca_records,
        *reroute_records,
    ]

    for regime in selected_regimes:
        provider = build_attribute_conditioned_forecast_provider(
            timeline,
            maximum_volume=(selected_maximum_volume),
            occurrence_probability=(regime.occurrence_probability),
        )

        rm_run = run_time_aware_dca_rm(
            instance,
            provider,
            value_interpretation=(regime.value_interpretation),
            selection_mode=(FutureDemandSelectionMode.A004_SHARED_ARC),
            timeline=timeline,
            lookahead_periods=selected_lookahead,
        )
        rrm_run = run_time_aware_dca_rrm(
            instance,
            provider,
            value_interpretation=(regime.value_interpretation),
            selection_mode=(FutureDemandSelectionMode.A004_SHARED_ARC),
            timeline=timeline,
            lookahead_periods=selected_lookahead,
        )

        rm_records = _rm_event_records(
            timeline,
            regime,
            rm_run,
        )
        rrm_records = _rrm_event_records(
            timeline,
            regime,
            rrm_run,
        )

        rm_failure = rm_run.failure_result
        rrm_failure = rrm_run.failure_result

        summaries.append(
            _summary(
                policy_key=regime.key,
                policy_label=regime.label,
                mechanism="DCA-RM",
                value_interpretation=(regime.value_interpretation.value),
                occurrence_probability=(regime.occurrence_probability),
                maximum_forecast_volume=(selected_maximum_volume),
                lookahead_periods=selected_lookahead,
                completed=rm_run.completed,
                attempted_events=len(rm_run.results),
                processed_events=(rm_run.final_state.processed_event_count),
                accepted_volume=float(rm_run.accepted_volume),
                realised_revenue=float(rm_run.total_realised_revenue),
                summed_objectives=float(rm_run.summed_event_objectives),
                summed_future_contribution=float(rm_run.total_expected_future_contribution),
                accepted_demand_ids=tuple(rm_run.final_state.accepted_demand_ids),
                failure_event_id=(None if rm_failure is None else rm_failure.event.event_id),
                records=rm_records,
                baseline_processed_events=(baseline_processed),
                baseline_accepted_volume=(baseline_volume),
                baseline_realised_revenue=(baseline_revenue),
                baseline_records=dca_records,
            )
        )
        summaries.append(
            _summary(
                policy_key=_rrm_key(regime),
                policy_label=_rrm_label(regime),
                mechanism="DCA-RRM",
                value_interpretation=(regime.value_interpretation.value),
                occurrence_probability=(regime.occurrence_probability),
                maximum_forecast_volume=(selected_maximum_volume),
                lookahead_periods=selected_lookahead,
                completed=rrm_run.completed,
                attempted_events=len(rrm_run.results),
                processed_events=(rrm_run.processed_event_count),
                accepted_volume=float(rrm_run.accepted_volume),
                realised_revenue=float(rrm_run.total_realised_revenue),
                summed_objectives=float(rrm_run.summed_event_objectives),
                summed_future_contribution=float(rrm_run.total_expected_future_contribution),
                accepted_demand_ids=tuple(rrm_run.final_state.accepted_demand_ids),
                failure_event_id=(None if rrm_failure is None else rrm_failure.event.event_id),
                records=rrm_records,
                baseline_processed_events=(baseline_processed),
                baseline_accepted_volume=(baseline_volume),
                baseline_realised_revenue=(baseline_revenue),
                baseline_records=dca_records,
            )
        )

        events.extend(rm_records)
        events.extend(rrm_records)

    return Phase9CanonicalEvaluation(
        instance_fingerprint=(instance.demand_fingerprint),
        total_booking_events=timeline.event_count,
        maximum_forecast_volume=(selected_maximum_volume),
        lookahead_periods=selected_lookahead,
        regimes=selected_regimes,
        summaries=tuple(summaries),
        events=tuple(events),
    )


@dataclass(frozen=True, slots=True)
class Phase9EvaluationPaths:
    """Files written for one Phase 9 canonical evaluation."""

    policy_summary_csv: Path
    event_results_csv: Path
    evaluation_json: Path
    report_markdown: Path


def _csv_optional_float(
    value: float | None,
) -> str:
    """Format an optional floating-point CSV value."""
    if value is None:
        return ""

    return f"{value:.10g}"


def _csv_optional_int(
    value: int | None,
) -> str:
    """Format an optional integer CSV value."""
    if value is None:
        return ""

    return str(value)


def _markdown_optional_float(
    value: float | None,
) -> str:
    """Format an optional floating-point Markdown value."""
    if value is None:
        return "—"

    return f"{value:.4f}"


def _markdown_optional_int(
    value: int | None,
) -> str:
    """Format an optional integer Markdown value."""
    if value is None:
        return "—"

    return str(value)


def _phase9_markdown_report(
    evaluation: Phase9CanonicalEvaluation,
) -> str:
    """Render the canonical four-mechanism report."""
    lines = [
        "# Phase 9 Canonical DCA-RRM Evaluation",
        "",
        "## Scientific status",
        "",
        (
            "This is a deterministic mechanism and sensitivity "
            "evaluation of DCA, DCA-R, DCA-RM, and DCA-RRM on "
            "the canonical synthetic instance."
        ),
        "",
        (
            "It is not an exact numerical reproduction of the "
            "paper's experimental tables because the complete "
            "forecast distributions, demand-generation inputs, "
            "random seeds, and operational construction of the "
            "future-demand set are not reported."
        ),
        "",
        (
            "The evaluation reuses the Phase 8 attribute-conditioned "
            "synthetic forecast regime. Realised future demand volume "
            "is not used to construct the forecast distribution."
        ),
        "",
        (
            "DCA-RM and DCA-RRM receive the same future-demand "
            "forecasts, probability regime, maximum forecast volume, "
            "value interpretation, timeline, and look-ahead."
        ),
        "",
        (
            "Phase 9 evaluates stable service capacities with truck "
            "recourse disabled. No truck-flow variable is available, "
            "so the paper's truck-penalty term is zero by construction. "
            "Service-status changes and explicit truck recourse belong "
            "to Phase 10."
        ),
        "",
        (
            "Realised revenue is the primary financial result. "
            "Optimisation-objective sums and expected-future "
            "contributions are diagnostic quantities and must not "
            "be interpreted as earned revenue."
        ),
        "",
        "## Evaluation configuration",
        "",
        f"- Instance fingerprint: `{evaluation.instance_fingerprint}`",
        f"- Booking events: {evaluation.total_booking_events}",
        (f"- Maximum synthetic forecast volume: {evaluation.maximum_forecast_volume}"),
        (f"- Look-ahead periods: {_markdown_optional_int(evaluation.lookahead_periods)}"),
        ("- Future-set selection: A004 shared-current-arc operational rule"),
        ("- Forecast distribution: zero-inflated uniform over positive volumes"),
        "",
        "## Policy summary",
        "",
        "| Policy | Mechanism | Interpretation | Probability | "
        "Completed | Processed | Accepted volume | Realised revenue | "
        "Objective sum | Expected-future sum | Forecast candidates | "
        "Positive protections | Protected volume | Prior-reoptimising "
        "events | Failure event |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for summary in evaluation.summaries:
        lines.append(
            "| "
            f"{summary.policy_label} | "
            f"{summary.mechanism} | "
            f"{summary.value_interpretation or '—'} | "
            f"{_markdown_optional_float(summary.occurrence_probability)} | "
            f"{summary.completed} | "
            f"{summary.processed_events} | "
            f"{summary.accepted_volume:.4f} | "
            f"{summary.realised_revenue:.4f} | "
            f"{summary.summed_optimisation_objectives:.4f} | "
            f"{summary.summed_expected_future_contribution:.4f} | "
            f"{summary.forecast_candidate_count} | "
            f"{summary.positive_protection_count} | "
            f"{summary.selected_protection_volume:.4f} | "
            f"{summary.events_reoptimising_prior_commitments} | "
            f"{summary.failure_event_id or 'none'} |"
        )

    lines.extend(
        [
            "",
            "## Comparison with Sequential DCA",
            "",
            "| Policy | Processed-event delta | Volume delta | "
            "Realised-revenue delta | Common-prefix volume delta | "
            "Common-prefix revenue delta | Continuation volume | "
            "Continuation revenue | Paired acceptance gains |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for summary in evaluation.summaries:
        lines.append(
            "| "
            f"{summary.policy_label} | "
            f"{summary.processed_event_delta_vs_dca:+d} | "
            f"{summary.accepted_volume_delta_vs_dca:+.4f} | "
            f"{summary.realised_revenue_delta_vs_dca:+.4f} | "
            f"{summary.common_prefix_accepted_volume_delta:+.4f} | "
            f"{summary.common_prefix_revenue_delta:+.4f} | "
            f"{summary.continuation_volume_after_dca_failure:+.4f} | "
            f"{summary.continuation_revenue_after_dca_failure:+.4f} | "
            f"{summary.paired_acceptance_improvement_count} |"
        )

    lines.extend(
        [
            "",
            "## Event-level results",
            "",
            "| Policy | Seq. | Event | Demand | Category | Status | "
            "Acceptance | Accepted volume | Realised revenue | "
            "Objective | Future contribution | Forecasts | Protected | "
            "Protected volume | Prior demands reoptimised | "
            "Released arcs |",
            "|---|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )

    for record in evaluation.events:
        lines.append(
            "| "
            f"{record.policy_label} | "
            f"{record.sequence_number} | "
            f"{record.event_id} | "
            f"{record.demand_id} | "
            f"{record.category} | "
            f"{record.event_status} | "
            f"{_markdown_optional_float(record.acceptance_fraction)} | "
            f"{_markdown_optional_float(record.accepted_volume)} | "
            f"{_markdown_optional_float(record.current_realised_revenue)} | "
            f"{_markdown_optional_float(record.optimisation_objective)} | "
            f"{_markdown_optional_float(record.future_expected_revenue)} | "
            f"{record.forecast_count} | "
            f"{record.protected_forecast_count} | "
            f"{record.selected_protection_volume:.4f} | "
            f"{', '.join(record.rerouted_prior_demand_ids) or '—'} | "
            f"{', '.join(record.released_arc_ids) or '—'} |"
        )

    lines.extend(
        [
            "",
            "## Canonical findings",
            "",
            (
                "Sequential DCA terminates at booking event 9. "
                "DCA-R recovers that event and continues to event 12."
            ),
            "",
            (
                "Under every evaluated probability and value regime, "
                "DCA-RRM has the same processed-event count, accepted "
                "volume, realised revenue, accepted-demand set, and "
                "failure event as its corresponding DCA-RM policy."
            ),
            "",
            (
                "DCA-RRM nevertheless reports a larger expected-future "
                "objective contribution in the canonical runs because "
                "tentative future flow is optimised jointly with "
                "mandatory unfinished accepted fragments."
            ),
            "",
            (
                "This equality of realised DCA-RM and DCA-RRM outcomes "
                "is an observed property of this canonical instance. "
                "It is not a general mathematical equivalence."
            ),
            "",
            (
                "The number of prior-reoptimising events records events "
                "where accepted unfinished commitments entered joint "
                "optimisation. It does not prove that every listed "
                "physical route changed."
            ),
            "",
            "## Interpretation boundary",
            "",
            (
                "Past accepted unfinished fragments follow Assumption "
                "A003. Their effective source is the execution-aware "
                "terminal-time position, not the original demand source."
            ),
            "",
            (
                "Future-set membership follows Assumption A004 and is "
                "based on interaction with the current request's feasible "
                "transport arcs. A forecast interacting only with a past "
                "fragment network is not selected by this baseline rule."
            ),
            "",
            (
                "The printed future-value expression is the reproduction "
                "baseline, while the capped expectation is an explicitly "
                "labelled sensitivity."
            ),
            "",
            (
                "Future selectors, protected volumes, and tentative "
                "future flows are discarded after each event. Only "
                "reconstructed prior commitments and the current realised "
                "decision enter persistent state."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_phase9_evaluation(
    evaluation: Phase9CanonicalEvaluation,
    *,
    output_directory: Path | str,
    report_path: Path | str,
) -> Phase9EvaluationPaths:
    """Write Phase 9 summary CSV, event CSV, JSON, and report."""
    if not isinstance(
        evaluation,
        Phase9CanonicalEvaluation,
    ):
        raise TypeError("evaluation must be a Phase9CanonicalEvaluation.")

    output_directory = Path(output_directory)
    report_path = Path(report_path)

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    policy_summary_csv = output_directory / "canonical_policy_summary.csv"
    event_results_csv = output_directory / "canonical_event_results.csv"
    evaluation_json = output_directory / "canonical_evaluation.json"

    summary_fieldnames = tuple(Phase9PolicySummary.__dataclass_fields__)
    event_fieldnames = tuple(Phase9EventRecord.__dataclass_fields__)

    with policy_summary_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=summary_fieldnames,
        )
        writer.writeheader()

        for summary in evaluation.summaries:
            row = asdict(summary)
            row["value_interpretation"] = summary.value_interpretation or ""
            row["occurrence_probability"] = _csv_optional_float(summary.occurrence_probability)
            row["maximum_forecast_volume"] = _csv_optional_int(summary.maximum_forecast_volume)
            row["lookahead_periods"] = _csv_optional_int(summary.lookahead_periods)
            row["accepted_demand_ids"] = ";".join(summary.accepted_demand_ids)
            row["failure_event_id"] = summary.failure_event_id or ""

            numeric_fields = (
                "accepted_volume",
                "realised_revenue",
                "summed_optimisation_objectives",
                "summed_expected_future_contribution",
                "selected_protection_volume",
                "accepted_volume_delta_vs_dca",
                "realised_revenue_delta_vs_dca",
                "common_prefix_accepted_volume_delta",
                "common_prefix_revenue_delta",
                "continuation_volume_after_dca_failure",
                "continuation_revenue_after_dca_failure",
            )

            for field_name in numeric_fields:
                row[field_name] = _csv_optional_float(float(row[field_name]))

            writer.writerow(row)

    with event_results_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=event_fieldnames,
        )
        writer.writeheader()

        for record in evaluation.events:
            row = asdict(record)

            for field_name in (
                "acceptance_fraction",
                "accepted_volume",
                "current_realised_revenue",
                "optimisation_objective",
                "future_expected_revenue",
            ):
                row[field_name] = _csv_optional_float(getattr(record, field_name))

            row["requested_volume"] = _csv_optional_float(record.requested_volume)
            row["selected_protection_volume"] = _csv_optional_float(
                record.selected_protection_volume
            )
            row["forecast_ids"] = ";".join(record.forecast_ids)
            row["protected_forecast_ids"] = ";".join(record.protected_forecast_ids)
            row["rerouted_prior_demand_ids"] = ";".join(record.rerouted_prior_demand_ids)
            row["released_arc_ids"] = ";".join(record.released_arc_ids)

            writer.writerow(row)

    with evaluation_json.open(
        "w",
        encoding="utf-8",
    ) as stream:
        json.dump(
            asdict(evaluation),
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")

    report_path.write_text(
        _phase9_markdown_report(evaluation),
        encoding="utf-8",
    )

    return Phase9EvaluationPaths(
        policy_summary_csv=policy_summary_csv,
        event_results_csv=event_results_csv,
        evaluation_json=evaluation_json,
        report_markdown=report_path,
    )
