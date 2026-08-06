"""Canonical synthetic evaluation of DCA-RM forecast sensitivities."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.run import (
    DcaRmEventResult,
    ForecastProvider,
    TimeAwareDcaRmRun,
    run_time_aware_dca_rm,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    BookingTimeline,
    RollingBookingState,
    TimeAwareSequentialDcaRun,
    build_booking_timeline,
    run_time_aware_sequential_dca,
)

EVALUATION_TOLERANCE = 1e-6


def _validate_occurrence_probability(
    value: object,
) -> float:
    """Validate a future-demand occurrence probability."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("occurrence_probability must be a real number.")

    probability = float(value)

    if not isfinite(probability):
        raise ValueError("occurrence_probability must be finite.")

    if probability < 0.0 or probability > 1.0:
        raise ValueError("occurrence_probability must lie between zero and one.")

    return probability


def _validate_maximum_volume(
    value: object,
) -> int:
    """Validate a positive integer forecast-volume maximum."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("maximum_volume must be an integer.")

    if value <= 0:
        raise ValueError("maximum_volume must be strictly positive.")

    return value


def _uniform_positive_outcomes(
    maximum_volume: int,
    occurrence_probability: float,
) -> tuple[VolumeProbability, ...]:
    """Build a zero-inflated uniform positive-volume distribution.

    The synthetic diagnostic distribution is:

        P(X = 0) = 1 - p

        P(X = x) = p / VMAX
        for x in {1, ..., VMAX}

    It does not use the realised future request volume.
    """
    maximum_volume = _validate_maximum_volume(maximum_volume)
    probability = _validate_occurrence_probability(occurrence_probability)

    outcomes: list[VolumeProbability] = [
        VolumeProbability(
            0,
            1.0 - probability,
        )
    ]

    positive_probability = probability / maximum_volume
    allocated_probability = 0.0

    for volume in range(1, maximum_volume + 1):
        if volume < maximum_volume:
            volume_probability = positive_probability
            allocated_probability += volume_probability
        else:
            volume_probability = probability - allocated_probability

        outcomes.append(
            VolumeProbability(
                volume,
                volume_probability,
            )
        )

    return tuple(outcomes)


@dataclass(frozen=True, slots=True)
class ForecastSensitivityRegime:
    """One DCA-RM forecast and value-function regime."""

    key: str
    label: str
    occurrence_probability: float
    value_interpretation: FutureValueInterpretation

    def __post_init__(self) -> None:
        """Validate and normalise one regime."""
        if not isinstance(self.key, str):
            raise TypeError("key must be a string.")

        if not isinstance(self.label, str):
            raise TypeError("label must be a string.")

        key = self.key.strip()
        label = self.label.strip()

        if not key:
            raise ValueError("key must be non-empty.")

        if not label:
            raise ValueError("label must be non-empty.")

        probability = _validate_occurrence_probability(self.occurrence_probability)

        if not isinstance(
            self.value_interpretation,
            FutureValueInterpretation,
        ):
            raise TypeError("value_interpretation must be a FutureValueInterpretation.")

        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(
            self,
            "occurrence_probability",
            probability,
        )


@dataclass(frozen=True, slots=True)
class Phase8PolicySummary:
    """Aggregate result for one DCA or DCA-RM policy."""

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
class Phase8EventRecord:
    """One policy-event result in long reporting format."""

    policy_key: str
    policy_label: str
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


@dataclass(frozen=True, slots=True)
class Phase8CanonicalEvaluation:
    """Complete DCA and DCA-RM canonical sensitivity evaluation."""

    instance_fingerprint: str
    total_booking_events: int
    maximum_forecast_volume: int
    lookahead_periods: int | None
    regimes: tuple[ForecastSensitivityRegime, ...]
    summaries: tuple[Phase8PolicySummary, ...]
    events: tuple[Phase8EventRecord, ...]

    def __post_init__(self) -> None:
        """Validate evaluation shape and unique policy keys."""
        if len(self.instance_fingerprint) != 64:
            raise ValueError("instance_fingerprint must be a SHA-256 value.")

        if self.total_booking_events <= 0:
            raise ValueError("total_booking_events must be positive.")

        _validate_maximum_volume(self.maximum_forecast_volume)

        policy_keys = tuple(summary.policy_key for summary in self.summaries)

        if len(set(policy_keys)) != len(policy_keys):
            raise ValueError("Policy summary keys must be unique.")

        expected_event_rows = len(self.summaries) * self.total_booking_events

        if len(self.events) != expected_event_rows:
            raise ValueError("Event rows must cover every policy and booking event.")

    def summary_for(
        self,
        policy_key: str,
    ) -> Phase8PolicySummary:
        """Return one policy summary."""
        for summary in self.summaries:
            if summary.policy_key == policy_key:
                return summary

        raise KeyError(f"No Phase 8 policy summary for {policy_key}.")


def default_sensitivity_regimes(
    occurrence_probabilities: Sequence[float] = (
        0.20,
        0.50,
        0.80,
    ),
) -> tuple[ForecastSensitivityRegime, ...]:
    """Return printed and capped regimes for each probability."""
    probabilities = tuple(
        _validate_occurrence_probability(value) for value in occurrence_probabilities
    )

    if not probabilities:
        raise ValueError("At least one occurrence probability is required.")

    if len(set(probabilities)) != len(probabilities):
        raise ValueError("Occurrence probabilities must be unique.")

    regimes: list[ForecastSensitivityRegime] = []

    for interpretation in (
        FutureValueInterpretation.PRINTED,
        FutureValueInterpretation.CAPPED,
    ):
        for probability in probabilities:
            probability_code = int(round(probability * 100))
            regimes.append(
                ForecastSensitivityRegime(
                    key=(f"rm_{interpretation.value}_p{probability_code:02d}"),
                    label=(f"DCA-RM {interpretation.value} p={probability:.2f}"),
                    occurrence_probability=probability,
                    value_interpretation=interpretation,
                )
            )

    return tuple(regimes)


def build_attribute_conditioned_forecast_provider(
    timeline: BookingTimeline,
    *,
    maximum_volume: int,
    occurrence_probability: float,
) -> ForecastProvider:
    """Build a diagnostic provider from unrevealed demand attributes.

    For every later timeline event, the forecast reuses:

    - origin;
    - destination;
    - availability time;
    - deadline;
    - category;
    - fare.

    It deliberately does not use the future event's realised volume.
    Volume uncertainty is replaced by the configured zero-inflated
    uniform distribution.

    This is an attribute-conditioned diagnostic regime, not a claim
    that the paper's operational forecasting process is known.
    """
    if not isinstance(timeline, BookingTimeline):
        raise TypeError("timeline must be a BookingTimeline.")

    maximum_volume = _validate_maximum_volume(maximum_volume)
    probability = _validate_occurrence_probability(occurrence_probability)
    outcomes = _uniform_positive_outcomes(
        maximum_volume,
        probability,
    )

    def provide(
        event: BookingDecisionEvent,
        state: RollingBookingState,
    ) -> tuple[FutureDemandForecast, ...]:
        if not isinstance(
            event,
            BookingDecisionEvent,
        ):
            raise TypeError("event must be a BookingDecisionEvent.")

        if not isinstance(
            state,
            RollingBookingState,
        ):
            raise TypeError("state must be a RollingBookingState.")

        forecasts: list[FutureDemandForecast] = []

        for future_event in timeline.events:
            if future_event.sequence_number <= event.sequence_number:
                continue

            future_demand = future_event.demand

            forecasts.append(
                FutureDemandForecast(
                    forecast_id=future_demand.demand_id,
                    origin=future_demand.origin,
                    destination=future_demand.destination,
                    availability_time=(future_demand.availability_time),
                    due_time=future_demand.due_time,
                    category=future_demand.category,
                    fare_per_teu=(future_demand.fare_per_teu),
                    outcomes=outcomes,
                )
            )

        return tuple(forecasts)

    return provide


def _baseline_event_records(
    timeline: BookingTimeline,
    run: TimeAwareSequentialDcaRun,
) -> tuple[Phase8EventRecord, ...]:
    """Build complete baseline DCA event records."""
    result_by_event_id = {result.event.event_id: result for result in run.results}

    records: list[Phase8EventRecord] = []

    for event in timeline.events:
        result = result_by_event_id.get(event.event_id)

        if result is None:
            records.append(
                Phase8EventRecord(
                    policy_key="dca",
                    policy_label="Sequential DCA",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=event.demand.category.value,
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
                )
            )
            continue

        if not result.is_solved:
            records.append(
                Phase8EventRecord(
                    policy_key="dca",
                    policy_label="Sequential DCA",
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=event.demand.category.value,
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=result.solve_status,
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
                )
            )
            continue

        records.append(
            Phase8EventRecord(
                policy_key="dca",
                policy_label="Sequential DCA",
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=event.demand.category.value,
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=result.solve_status,
                acceptance_fraction=(result.acceptance_fraction),
                accepted_volume=result.accepted_volume,
                current_realised_revenue=(result.objective_value),
                optimisation_objective=(result.objective_value),
                future_expected_revenue=0.0,
                forecast_count=0,
                protected_forecast_count=0,
                selected_protection_volume=0.0,
                forecast_ids=(),
                protected_forecast_ids=(),
            )
        )

    return tuple(records)


def _rm_event_records(
    timeline: BookingTimeline,
    regime: ForecastSensitivityRegime,
    run: TimeAwareDcaRmRun,
) -> tuple[Phase8EventRecord, ...]:
    """Build complete event records for one DCA-RM regime."""
    result_by_event_id = {result.event.event_id: result for result in run.results}

    records: list[Phase8EventRecord] = []

    for event in timeline.events:
        result = result_by_event_id.get(event.event_id)

        if result is None:
            records.append(
                Phase8EventRecord(
                    policy_key=regime.key,
                    policy_label=regime.label,
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=event.demand.category.value,
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
                )
            )
            continue

        if not result.is_solved:
            records.append(
                Phase8EventRecord(
                    policy_key=regime.key,
                    policy_label=regime.label,
                    sequence_number=event.sequence_number,
                    event_id=event.event_id,
                    decision_time=event.decision_time,
                    demand_id=event.demand_id,
                    category=event.demand.category.value,
                    requested_volume=float(event.demand.volume),
                    event_status="failed",
                    solve_status=result.solve_status,
                    acceptance_fraction=None,
                    accepted_volume=None,
                    current_realised_revenue=None,
                    optimisation_objective=None,
                    future_expected_revenue=None,
                    forecast_count=len(result.forecast_ids),
                    protected_forecast_count=0,
                    selected_protection_volume=0.0,
                    forecast_ids=result.forecast_ids,
                    protected_forecast_ids=(),
                )
            )
            continue

        positive_protections = tuple(
            protection
            for protection in result.protections
            if (protection.protected_volume > EVALUATION_TOLERANCE)
        )

        records.append(
            Phase8EventRecord(
                policy_key=regime.key,
                policy_label=regime.label,
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=event.demand.category.value,
                requested_volume=float(event.demand.volume),
                event_status="solved",
                solve_status=result.solve_status,
                acceptance_fraction=(result.acceptance_fraction),
                accepted_volume=result.accepted_volume,
                current_realised_revenue=(result.current_realised_revenue),
                optimisation_objective=(result.optimisation_objective),
                future_expected_revenue=(result.future_expected_revenue),
                forecast_count=len(result.forecast_ids),
                protected_forecast_count=len(positive_protections),
                selected_protection_volume=float(
                    sum(protection.protected_volume for protection in positive_protections)
                ),
                forecast_ids=result.forecast_ids,
                protected_forecast_ids=tuple(
                    protection.forecast_id for protection in positive_protections
                ),
            )
        )

    return tuple(records)


def _acceptance_value(
    result: DcaRmEventResult,
) -> float:
    """Return a solved DCA-RM acceptance value."""
    if not result.is_solved or result.acceptance_fraction is None:
        return 0.0

    return float(result.acceptance_fraction)


def _rm_summary(
    regime: ForecastSensitivityRegime,
    run: TimeAwareDcaRmRun,
    baseline: TimeAwareSequentialDcaRun,
    *,
    maximum_volume: int,
    lookahead_periods: int | None,
) -> Phase8PolicySummary:
    """Build one DCA-RM summary against the DCA baseline."""
    baseline_processed = baseline.final_state.processed_event_count
    rm_processed = run.final_state.processed_event_count
    common_prefix_length = min(
        baseline_processed,
        rm_processed,
    )

    baseline_prefix_results = baseline.results[:common_prefix_length]
    rm_prefix_results = run.results[:common_prefix_length]

    baseline_prefix_revenue = float(
        sum(result.objective_value or 0.0 for result in baseline_prefix_results)
    )
    rm_prefix_revenue = float(
        sum(result.current_realised_revenue or 0.0 for result in rm_prefix_results)
    )

    baseline_prefix_volume = float(
        sum(result.accepted_volume for result in baseline_prefix_results)
    )
    rm_prefix_volume = float(sum(result.accepted_volume for result in rm_prefix_results))

    positive_protections = tuple(
        protection
        for result in run.results
        if result.is_solved
        for protection in result.protections
        if (protection.protected_volume > EVALUATION_TOLERANCE)
    )

    paired_improvements = sum(
        1
        for baseline_result, rm_result in zip(
            baseline_prefix_results,
            rm_prefix_results,
            strict=True,
        )
        if (
            rm_result.is_solved
            and rm_result.acceptance_fraction is not None
            and baseline_result.acceptance_fraction is not None
            and (
                float(rm_result.acceptance_fraction) - float(baseline_result.acceptance_fraction)
                > EVALUATION_TOLERANCE
            )
        )
    )

    failure = run.failure_result

    return Phase8PolicySummary(
        policy_key=regime.key,
        policy_label=regime.label,
        mechanism="DCA-RM",
        value_interpretation=(regime.value_interpretation.value),
        occurrence_probability=(regime.occurrence_probability),
        maximum_forecast_volume=maximum_volume,
        lookahead_periods=lookahead_periods,
        completed=run.completed,
        attempted_events=len(run.results),
        processed_events=rm_processed,
        accepted_volume=float(run.accepted_volume),
        realised_revenue=float(run.total_realised_revenue),
        summed_optimisation_objectives=float(run.summed_event_objectives),
        summed_expected_future_contribution=float(run.total_expected_future_contribution),
        forecast_candidate_count=sum(len(result.forecast_ids) for result in run.results),
        positive_protection_count=len(positive_protections),
        selected_protection_volume=float(
            sum(protection.protected_volume for protection in positive_protections)
        ),
        accepted_demand_ids=(run.final_state.accepted_demand_ids),
        failure_event_id=(None if failure is None else failure.event.event_id),
        processed_event_delta_vs_dca=(rm_processed - baseline_processed),
        accepted_volume_delta_vs_dca=(run.accepted_volume - baseline.accepted_volume),
        realised_revenue_delta_vs_dca=(run.total_realised_revenue - baseline.total_revenue),
        common_prefix_accepted_volume_delta=(rm_prefix_volume - baseline_prefix_volume),
        common_prefix_revenue_delta=(rm_prefix_revenue - baseline_prefix_revenue),
        continuation_volume_after_dca_failure=(run.accepted_volume - rm_prefix_volume),
        continuation_revenue_after_dca_failure=(run.total_realised_revenue - rm_prefix_revenue),
        paired_acceptance_improvement_count=(paired_improvements),
    )


def _baseline_summary(
    run: TimeAwareSequentialDcaRun,
) -> Phase8PolicySummary:
    """Build the baseline DCA summary."""
    failure = run.failure_result

    return Phase8PolicySummary(
        policy_key="dca",
        policy_label="Sequential DCA",
        mechanism="DCA",
        value_interpretation=None,
        occurrence_probability=None,
        maximum_forecast_volume=None,
        lookahead_periods=None,
        completed=run.completed,
        attempted_events=len(run.results),
        processed_events=(run.final_state.processed_event_count),
        accepted_volume=float(run.accepted_volume),
        realised_revenue=float(run.total_revenue),
        summed_optimisation_objectives=float(run.total_revenue),
        summed_expected_future_contribution=0.0,
        forecast_candidate_count=0,
        positive_protection_count=0,
        selected_protection_volume=0.0,
        accepted_demand_ids=(run.final_state.accepted_demand_ids),
        failure_event_id=(None if failure is None else failure.event.event_id),
        processed_event_delta_vs_dca=0,
        accepted_volume_delta_vs_dca=0.0,
        realised_revenue_delta_vs_dca=0.0,
        common_prefix_accepted_volume_delta=0.0,
        common_prefix_revenue_delta=0.0,
        continuation_volume_after_dca_failure=0.0,
        continuation_revenue_after_dca_failure=0.0,
        paired_acceptance_improvement_count=0,
    )


def evaluate_phase8_canonical(
    instance: ExperimentInstance,
    *,
    regimes: Sequence[ForecastSensitivityRegime] | None = None,
    maximum_volume: int | None = None,
    lookahead_periods: int | None = None,
) -> Phase8CanonicalEvaluation:
    """Evaluate DCA and synthetic DCA-RM regimes.

    The forecast regime is attribute-conditioned and deliberately
    excludes realised future request volume. The evaluation is a
    mechanism and sensitivity study, not an exact numerical
    reproduction of the paper's experimental tables.
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
        instance.config.demand_generation.maximum_volume
        if maximum_volume is None
        else _validate_maximum_volume(maximum_volume)
    )

    if lookahead_periods is not None:
        if isinstance(lookahead_periods, bool) or not isinstance(lookahead_periods, int):
            raise TypeError("lookahead_periods must be an integer or None.")

        if lookahead_periods < 0:
            raise ValueError("lookahead_periods must be non-negative.")

    timeline = build_booking_timeline(instance)
    baseline = run_time_aware_sequential_dca(
        instance,
        timeline=timeline,
    )

    summaries: list[Phase8PolicySummary] = [_baseline_summary(baseline)]
    events: list[Phase8EventRecord] = list(
        _baseline_event_records(
            timeline,
            baseline,
        )
    )

    for regime in selected_regimes:
        provider = build_attribute_conditioned_forecast_provider(
            timeline,
            maximum_volume=(selected_maximum_volume),
            occurrence_probability=(regime.occurrence_probability),
        )

        run = run_time_aware_dca_rm(
            instance,
            provider,
            value_interpretation=(regime.value_interpretation),
            selection_mode=(FutureDemandSelectionMode.A004_SHARED_ARC),
            timeline=timeline,
            lookahead_periods=lookahead_periods,
        )

        summaries.append(
            _rm_summary(
                regime,
                run,
                baseline,
                maximum_volume=(selected_maximum_volume),
                lookahead_periods=lookahead_periods,
            )
        )
        events.extend(
            _rm_event_records(
                timeline,
                regime,
                run,
            )
        )

    return Phase8CanonicalEvaluation(
        instance_fingerprint=(instance.demand_fingerprint),
        total_booking_events=timeline.event_count,
        maximum_forecast_volume=(selected_maximum_volume),
        lookahead_periods=lookahead_periods,
        regimes=selected_regimes,
        summaries=tuple(summaries),
        events=tuple(events),
    )


@dataclass(frozen=True, slots=True)
class Phase8EvaluationPaths:
    """Files written for one Phase 8 canonical evaluation."""

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


def _phase8_markdown_report(
    evaluation: Phase8CanonicalEvaluation,
) -> str:
    """Render the canonical synthetic DCA-RM report."""
    lines = [
        "# Phase 8 Canonical Synthetic DCA-RM Evaluation",
        "",
        "## Scientific status",
        "",
        (
            "This is a deterministic mechanism and sensitivity "
            "evaluation using an attribute-conditioned synthetic "
            "forecast regime."
        ),
        "",
        (
            "The forecast provider uses the origin, destination, "
            "availability time, deadline, customer category, and fare "
            "of later timeline requests, but deliberately replaces "
            "their realised volumes with a configured probability "
            "distribution."
        ),
        "",
        (
            "Because the paper does not report the complete forecast "
            "generation parameters, probability distributions, seeds, "
            "or exact construction of the future-demand set, these "
            "results are not an exact numerical reproduction of the "
            "paper's experimental tables."
        ),
        "",
        (
            "Future-set membership follows the disclosed operational "
            "interpretation in Assumption A004. The printed expected-"
            "revenue expression is the baseline under Assumption A005; "
            "the capped expectation is reported as a sensitivity."
        ),
        "",
        (
            "Zero protected volume is represented by setting all "
            "positive-level selectors to zero, as documented in "
            "Assumption A016."
        ),
        "",
        (
            "Realised revenue is the primary financial result. Summed "
            "optimisation objectives and expected future contributions "
            "are diagnostic quantities and must not be interpreted as "
            "earned revenue."
        ),
        "",
        "## Evaluation configuration",
        "",
        f"- Instance fingerprint: `{evaluation.instance_fingerprint}`",
        f"- Booking events: {evaluation.total_booking_events}",
        (f"- Maximum synthetic forecast volume: {evaluation.maximum_forecast_volume}"),
        (f"- Look-ahead periods: {_markdown_optional_int(evaluation.lookahead_periods)}"),
        ("- Forecast volume distribution: zero-inflated uniform over positive volumes"),
        "",
        "## Policy summary",
        "",
        "| Policy | Mechanism | Interpretation | Probability | "
        "Completed | Processed | Accepted volume | Realised revenue | "
        "Objective sum | Expected-future sum | Forecast candidates | "
        "Positive protections | Protected volume | Failure event |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
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
            f"{summary.failure_event_id or 'none'} |"
        )

    lines.extend(
        [
            "",
            "## Comparison with sequential DCA",
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
            "| Policy | Seq. | Event | Time | Demand | Category | "
            "Requested | Status | Acceptance | Accepted volume | "
            "Realised revenue | Objective | Future contribution | "
            "Forecasts | Protected forecasts | Protected volume |",
            "|---|---:|---|---:|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for record in evaluation.events:
        lines.append(
            "| "
            f"{record.policy_label} | "
            f"{record.sequence_number} | "
            f"{record.event_id} | "
            f"{record.decision_time} | "
            f"{record.demand_id} | "
            f"{record.category} | "
            f"{record.requested_volume:.4f} | "
            f"{record.event_status} | "
            f"{_markdown_optional_float(record.acceptance_fraction)} | "
            f"{_markdown_optional_float(record.accepted_volume)} | "
            f"{_markdown_optional_float(record.current_realised_revenue)} | "
            f"{_markdown_optional_float(record.optimisation_objective)} | "
            f"{_markdown_optional_float(record.future_expected_revenue)} | "
            f"{record.forecast_count} | "
            f"{record.protected_forecast_count} | "
            f"{record.selected_protection_volume:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "The probability regimes test whether the implemented "
                "DCA-RM mechanism responds coherently to changing "
                "future-demand opportunity cost. They do not establish "
                "that any one synthetic probability regime matches the "
                "paper's original experimental data."
            ),
            "",
            (
                "Tentative future flows, protected-volume selectors, "
                "and forecast protection levels are discarded after "
                "each decision. Only the realised current acceptance "
                "and current route enter persistent booking state."
            ),
            "",
            (
                "The capped-value formulation credits outcomes above "
                "the selected protection level and is an explicitly "
                "labelled sensitivity, not the printed baseline."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def write_phase8_evaluation(
    evaluation: Phase8CanonicalEvaluation,
    *,
    output_directory: Path | str,
    report_path: Path | str,
) -> Phase8EvaluationPaths:
    """Write Phase 8 summary CSV, event CSV, JSON, and report."""
    if not isinstance(
        evaluation,
        Phase8CanonicalEvaluation,
    ):
        raise TypeError("evaluation must be a Phase8CanonicalEvaluation.")

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

    summary_fieldnames = (
        "policy_key",
        "policy_label",
        "mechanism",
        "value_interpretation",
        "occurrence_probability",
        "maximum_forecast_volume",
        "lookahead_periods",
        "completed",
        "attempted_events",
        "processed_events",
        "accepted_volume",
        "realised_revenue",
        "summed_optimisation_objectives",
        "summed_expected_future_contribution",
        "forecast_candidate_count",
        "positive_protection_count",
        "selected_protection_volume",
        "accepted_demand_ids",
        "failure_event_id",
        "processed_event_delta_vs_dca",
        "accepted_volume_delta_vs_dca",
        "realised_revenue_delta_vs_dca",
        "common_prefix_accepted_volume_delta",
        "common_prefix_revenue_delta",
        "continuation_volume_after_dca_failure",
        "continuation_revenue_after_dca_failure",
        "paired_acceptance_improvement_count",
    )

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
            writer.writerow(
                {
                    "policy_key": summary.policy_key,
                    "policy_label": summary.policy_label,
                    "mechanism": summary.mechanism,
                    "value_interpretation": (summary.value_interpretation or ""),
                    "occurrence_probability": (_csv_optional_float(summary.occurrence_probability)),
                    "maximum_forecast_volume": (_csv_optional_int(summary.maximum_forecast_volume)),
                    "lookahead_periods": (_csv_optional_int(summary.lookahead_periods)),
                    "completed": summary.completed,
                    "attempted_events": (summary.attempted_events),
                    "processed_events": (summary.processed_events),
                    "accepted_volume": (_csv_optional_float(summary.accepted_volume)),
                    "realised_revenue": (_csv_optional_float(summary.realised_revenue)),
                    "summed_optimisation_objectives": (
                        _csv_optional_float(summary.summed_optimisation_objectives)
                    ),
                    "summed_expected_future_contribution": (
                        _csv_optional_float(summary.summed_expected_future_contribution)
                    ),
                    "forecast_candidate_count": (summary.forecast_candidate_count),
                    "positive_protection_count": (summary.positive_protection_count),
                    "selected_protection_volume": (
                        _csv_optional_float(summary.selected_protection_volume)
                    ),
                    "accepted_demand_ids": ";".join(summary.accepted_demand_ids),
                    "failure_event_id": (summary.failure_event_id or ""),
                    "processed_event_delta_vs_dca": (summary.processed_event_delta_vs_dca),
                    "accepted_volume_delta_vs_dca": (
                        _csv_optional_float(summary.accepted_volume_delta_vs_dca)
                    ),
                    "realised_revenue_delta_vs_dca": (
                        _csv_optional_float(summary.realised_revenue_delta_vs_dca)
                    ),
                    "common_prefix_accepted_volume_delta": (
                        _csv_optional_float(summary.common_prefix_accepted_volume_delta)
                    ),
                    "common_prefix_revenue_delta": (
                        _csv_optional_float(summary.common_prefix_revenue_delta)
                    ),
                    "continuation_volume_after_dca_failure": (
                        _csv_optional_float(summary.continuation_volume_after_dca_failure)
                    ),
                    "continuation_revenue_after_dca_failure": (
                        _csv_optional_float(summary.continuation_revenue_after_dca_failure)
                    ),
                    "paired_acceptance_improvement_count": (
                        summary.paired_acceptance_improvement_count
                    ),
                }
            )

    event_fieldnames = (
        "policy_key",
        "policy_label",
        "sequence_number",
        "event_id",
        "decision_time",
        "demand_id",
        "category",
        "requested_volume",
        "event_status",
        "solve_status",
        "acceptance_fraction",
        "accepted_volume",
        "current_realised_revenue",
        "optimisation_objective",
        "future_expected_revenue",
        "forecast_count",
        "protected_forecast_count",
        "selected_protection_volume",
        "forecast_ids",
        "protected_forecast_ids",
    )

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
            writer.writerow(
                {
                    "policy_key": record.policy_key,
                    "policy_label": record.policy_label,
                    "sequence_number": (record.sequence_number),
                    "event_id": record.event_id,
                    "decision_time": record.decision_time,
                    "demand_id": record.demand_id,
                    "category": record.category,
                    "requested_volume": (_csv_optional_float(record.requested_volume)),
                    "event_status": record.event_status,
                    "solve_status": record.solve_status,
                    "acceptance_fraction": (_csv_optional_float(record.acceptance_fraction)),
                    "accepted_volume": (_csv_optional_float(record.accepted_volume)),
                    "current_realised_revenue": (
                        _csv_optional_float(record.current_realised_revenue)
                    ),
                    "optimisation_objective": (_csv_optional_float(record.optimisation_objective)),
                    "future_expected_revenue": (
                        _csv_optional_float(record.future_expected_revenue)
                    ),
                    "forecast_count": (record.forecast_count),
                    "protected_forecast_count": (record.protected_forecast_count),
                    "selected_protection_volume": (
                        _csv_optional_float(record.selected_protection_volume)
                    ),
                    "forecast_ids": ";".join(record.forecast_ids),
                    "protected_forecast_ids": ";".join(record.protected_forecast_ids),
                }
            )

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
        _phase8_markdown_report(evaluation),
        encoding="utf-8",
    )

    return Phase8EvaluationPaths(
        policy_summary_csv=policy_summary_csv,
        event_results_csv=event_results_csv,
        evaluation_json=evaluation_json,
        report_markdown=report_path,
    )
