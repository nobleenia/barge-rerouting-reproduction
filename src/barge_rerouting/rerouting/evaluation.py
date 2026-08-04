"""Canonical evaluation and export of Full-Reroute results."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.run import (
    FullRerouteRun,
    run_full_reroute,
)
from barge_rerouting.rolling_horizon import (
    BookingTimeline,
    TimeAwareSequentialDcaRun,
    build_booking_timeline,
    run_time_aware_sequential_dca,
)


@dataclass(frozen=True, slots=True)
class CanonicalEventComparison:
    """One booking event compared across both mechanisms."""

    sequence_number: int
    event_id: str
    decision_time: int
    demand_id: str
    category: str
    requested_volume: float
    ordinary_acceptance: float | None
    full_reroute_acceptance: float | None
    ordinary_revenue: float | None
    full_reroute_revenue: float | None
    rerouted_prior_demands: tuple[str, ...]
    released_services: tuple[str, ...]
    ordinary_solve_status: str
    full_reroute_solve_status: str


@dataclass(frozen=True, slots=True)
class CanonicalComparisonSummary:
    """Aggregate canonical comparison statistics."""

    instance_fingerprint: str
    total_booking_events: int
    ordinary_completed: bool
    full_reroute_completed: bool
    ordinary_processed_events: int
    full_reroute_processed_events: int
    ordinary_accepted_volume: float
    full_reroute_accepted_volume: float
    accepted_volume_delta: float
    ordinary_revenue: float
    full_reroute_revenue: float
    revenue_delta: float
    paired_acceptance_improvement_count: int
    ordinary_failure_recovered: bool
    additional_processed_events: int
    failure_sequence_shift: int | None
    common_prefix_ordinary_revenue: float
    common_prefix_full_reroute_revenue: float
    common_prefix_revenue_delta: float
    common_prefix_ordinary_accepted_volume: float
    common_prefix_full_reroute_accepted_volume: float
    common_prefix_accepted_volume_delta: float
    continuation_revenue_after_ordinary_failure: float
    continuation_volume_after_ordinary_failure: float
    events_reoptimising_prior_commitments: int
    ordinary_accepted_demand_ids: tuple[str, ...]
    full_reroute_accepted_demand_ids: tuple[str, ...]
    ordinary_failure_event_id: str | None
    full_reroute_failure_event_id: str | None


@dataclass(frozen=True, slots=True)
class Phase7CanonicalEvaluation:
    """Complete canonical event and summary evaluation."""

    summary: CanonicalComparisonSummary
    events: tuple[CanonicalEventComparison, ...]

    def __post_init__(self) -> None:
        """Validate timeline ordering and fingerprint presence."""
        if not isinstance(
            self.summary,
            CanonicalComparisonSummary,
        ):
            raise TypeError("summary must be a CanonicalComparisonSummary.")

        if not isinstance(self.events, tuple):
            raise TypeError("events must be a tuple.")

        for event in self.events:
            if not isinstance(
                event,
                CanonicalEventComparison,
            ):
                raise TypeError("Every event must be a CanonicalEventComparison.")

        sequences = tuple(event.sequence_number for event in self.events)

        if sequences != tuple(range(1, len(self.events) + 1)):
            raise ValueError("Canonical event comparisons must follow contiguous timeline order.")

        if len(self.events) != self.summary.total_booking_events:
            raise ValueError("Event rows must cover the complete timeline.")


@dataclass(frozen=True, slots=True)
class Phase7EvaluationPaths:
    """Files written for one canonical evaluation."""

    event_csv: Path
    evaluation_json: Path
    report_markdown: Path


def _optional_float(
    value: float | None,
) -> float | None:
    """Return an explicitly typed optional float."""
    if value is None:
        return None

    return float(value)


def _released_services(
    instance: ExperimentInstance,
    released_arc_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Translate released transport arcs to service IDs."""
    service_ids: set[str] = set()

    for arc_id in released_arc_ids:
        service_id = instance.arc_by_id(arc_id).service_id

        if service_id is not None:
            service_ids.add(str(service_id))

    return tuple(sorted(service_ids))


def _event_rows(
    instance: ExperimentInstance,
    timeline: BookingTimeline,
    ordinary_run: TimeAwareSequentialDcaRun,
    full_run: FullRerouteRun,
) -> tuple[CanonicalEventComparison, ...]:
    """Build complete event-level comparison rows."""
    ordinary_by_event_id = {result.event.event_id: result for result in ordinary_run.results}
    full_by_event_id = {result.event.event_id: result for result in full_run.results}

    rows: list[CanonicalEventComparison] = []

    for event in timeline.events:
        ordinary_result = ordinary_by_event_id.get(event.event_id)
        full_result = full_by_event_id.get(event.event_id)

        if ordinary_result is None:
            ordinary_acceptance = None
            ordinary_revenue = None
            ordinary_solve_status = "not-run"
        else:
            ordinary_acceptance = _optional_float(ordinary_result.acceptance_fraction)
            ordinary_revenue = _optional_float(ordinary_result.objective_value)
            ordinary_solve_status = str(ordinary_result.solve_status)

        if full_result is None:
            full_acceptance = None
            full_revenue = None
            rerouted_prior_demands: tuple[str, ...] = ()
            released_services: tuple[str, ...] = ()
            full_solve_status = "not-run"
        else:
            full_acceptance = _optional_float(full_result.reroute_acceptance_fraction)
            full_revenue = _optional_float(full_result.reroute_solution.objective_value)
            rerouted_prior_demands = tuple(full_result.rerouted_demand_ids)
            released_services = _released_services(
                instance,
                full_result.released_arc_ids,
            )
            full_solve_status = str(full_result.reroute_solution.solve_status)

        rows.append(
            CanonicalEventComparison(
                sequence_number=event.sequence_number,
                event_id=event.event_id,
                decision_time=event.decision_time,
                demand_id=event.demand_id,
                category=str(event.demand.category.value),
                requested_volume=float(event.demand.volume),
                ordinary_acceptance=ordinary_acceptance,
                full_reroute_acceptance=full_acceptance,
                ordinary_revenue=ordinary_revenue,
                full_reroute_revenue=full_revenue,
                rerouted_prior_demands=(rerouted_prior_demands),
                released_services=released_services,
                ordinary_solve_status=(ordinary_solve_status),
                full_reroute_solve_status=(full_solve_status),
            )
        )

    return tuple(rows)


def evaluate_full_reroute_against_sequential(
    instance: ExperimentInstance,
) -> Phase7CanonicalEvaluation:
    """Evaluate both mechanisms on the same timeline and instance."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    timeline = build_booking_timeline(instance)

    ordinary_run = run_time_aware_sequential_dca(
        instance,
        timeline=timeline,
    )
    full_run = run_full_reroute(
        instance,
        timeline=timeline,
    )

    ordinary_failure = ordinary_run.failure_result
    full_failure = full_run.failure_result

    ordinary_revenue = float(ordinary_run.total_revenue)
    full_revenue = float(full_run.total_revenue)

    ordinary_volume = float(ordinary_run.accepted_volume)
    full_volume = float(full_run.accepted_volume)

    events = _event_rows(
        instance,
        timeline,
        ordinary_run,
        full_run,
    )

    ordinary_processed_events = ordinary_run.final_state.processed_event_count
    full_processed_events = full_run.processed_event_count

    common_prefix_length = min(
        ordinary_processed_events,
        full_processed_events,
    )
    common_prefix_events = events[:common_prefix_length]

    common_prefix_ordinary_revenue = float(
        sum(event.ordinary_revenue or 0.0 for event in common_prefix_events)
    )
    common_prefix_full_reroute_revenue = float(
        sum(event.full_reroute_revenue or 0.0 for event in common_prefix_events)
    )

    common_prefix_ordinary_volume = float(
        sum(
            event.requested_volume * (event.ordinary_acceptance or 0.0)
            for event in common_prefix_events
        )
    )
    common_prefix_full_reroute_volume = float(
        sum(
            event.requested_volume * (event.full_reroute_acceptance or 0.0)
            for event in common_prefix_events
        )
    )

    ordinary_failure_recovered = False

    if ordinary_failure is not None:
        ordinary_failure_row = next(
            (event for event in events if event.event_id == ordinary_failure.event.event_id),
            None,
        )
        ordinary_failure_recovered = (
            ordinary_failure_row is not None
            and ordinary_failure_row.full_reroute_acceptance is not None
        )

    failure_sequence_shift = (
        full_failure.event.sequence_number - ordinary_failure.event.sequence_number
        if (ordinary_failure is not None and full_failure is not None)
        else None
    )

    summary = CanonicalComparisonSummary(
        instance_fingerprint=(instance.demand_fingerprint),
        total_booking_events=timeline.event_count,
        ordinary_completed=ordinary_run.completed,
        full_reroute_completed=full_run.completed,
        ordinary_processed_events=(ordinary_run.final_state.processed_event_count),
        full_reroute_processed_events=(full_run.processed_event_count),
        ordinary_accepted_volume=ordinary_volume,
        full_reroute_accepted_volume=full_volume,
        accepted_volume_delta=(full_volume - ordinary_volume),
        ordinary_revenue=ordinary_revenue,
        full_reroute_revenue=full_revenue,
        revenue_delta=full_revenue - ordinary_revenue,
        paired_acceptance_improvement_count=(full_run.acceptance_improvement_count),
        ordinary_failure_recovered=(ordinary_failure_recovered),
        additional_processed_events=(full_processed_events - ordinary_processed_events),
        failure_sequence_shift=failure_sequence_shift,
        common_prefix_ordinary_revenue=(common_prefix_ordinary_revenue),
        common_prefix_full_reroute_revenue=(common_prefix_full_reroute_revenue),
        common_prefix_revenue_delta=(
            common_prefix_full_reroute_revenue - common_prefix_ordinary_revenue
        ),
        common_prefix_ordinary_accepted_volume=(common_prefix_ordinary_volume),
        common_prefix_full_reroute_accepted_volume=(common_prefix_full_reroute_volume),
        common_prefix_accepted_volume_delta=(
            common_prefix_full_reroute_volume - common_prefix_ordinary_volume
        ),
        continuation_revenue_after_ordinary_failure=(
            full_revenue - common_prefix_full_reroute_revenue
        ),
        continuation_volume_after_ordinary_failure=(
            full_volume - common_prefix_full_reroute_volume
        ),
        events_reoptimising_prior_commitments=(full_run.events_with_prior_reoptimization),
        ordinary_accepted_demand_ids=(ordinary_run.final_state.accepted_demand_ids),
        full_reroute_accepted_demand_ids=(full_run.final_state.accepted_demand_ids),
        ordinary_failure_event_id=(
            None if ordinary_failure is None else ordinary_failure.event.event_id
        ),
        full_reroute_failure_event_id=(
            None if full_failure is None else full_failure.event.event_id
        ),
    )

    return Phase7CanonicalEvaluation(
        summary=summary,
        events=events,
    )


def _csv_value(
    value: float | None,
) -> str:
    """Format an optional numerical CSV value."""
    if value is None:
        return ""

    return f"{value:.10g}"


def _markdown_value(
    value: float | None,
) -> str:
    """Format an optional numerical Markdown value."""
    if value is None:
        return "—"

    return f"{value:.4f}"


def _markdown_report(
    evaluation: Phase7CanonicalEvaluation,
) -> str:
    """Render a reproducible Markdown results report."""
    summary = evaluation.summary

    lines = [
        "# Phase 7 Canonical Full-Reroute Evaluation",
        "",
        "This report compares the operational Full-Reroute "
        "implementation under Assumption A003 with the "
        "time-aware sequential DCA baseline.",
        "",
        "It does not yet include the paper's future-demand revenue-management component.",
        "",
        "## Aggregate results",
        "",
        f"- Instance fingerprint: `{summary.instance_fingerprint}`",
        f"- Total booking events: {summary.total_booking_events}",
        f"- Ordinary run completed: {summary.ordinary_completed}",
        f"- Full-Reroute run completed: {summary.full_reroute_completed}",
        (f"- Ordinary processed events: {summary.ordinary_processed_events}"),
        (f"- Full-Reroute processed events: {summary.full_reroute_processed_events}"),
        (f"- Ordinary accepted volume: {summary.ordinary_accepted_volume:.4f}"),
        (f"- Full-Reroute accepted volume: {summary.full_reroute_accepted_volume:.4f}"),
        (f"- Accepted-volume delta: {summary.accepted_volume_delta:.4f}"),
        (f"- Ordinary revenue: {summary.ordinary_revenue:.4f}"),
        (f"- Full-Reroute revenue: {summary.full_reroute_revenue:.4f}"),
        (f"- Revenue delta: {summary.revenue_delta:.4f}"),
        (f"- Paired acceptance-improvement events: {summary.paired_acceptance_improvement_count}"),
        (f"- Ordinary failure recovered by Full-Reroute: {summary.ordinary_failure_recovered}"),
        (f"- Additional processed events: {summary.additional_processed_events}"),
        (f"- Failure-sequence shift: {summary.failure_sequence_shift}"),
        (f"- Common-prefix ordinary revenue: {summary.common_prefix_ordinary_revenue:.4f}"),
        (f"- Common-prefix Full-Reroute revenue: {summary.common_prefix_full_reroute_revenue:.4f}"),
        (f"- Common-prefix revenue delta: {summary.common_prefix_revenue_delta:.4f}"),
        (
            "- Common-prefix accepted-volume delta: "
            f"{summary.common_prefix_accepted_volume_delta:.4f}"
        ),
        (
            "- Continuation revenue after ordinary failure: "
            f"{summary.continuation_revenue_after_ordinary_failure:.4f}"
        ),
        (
            "- Continuation volume after ordinary failure: "
            f"{summary.continuation_volume_after_ordinary_failure:.4f}"
        ),
        (
            "- Events reoptimising prior commitments: "
            f"{summary.events_reoptimising_prior_commitments}"
        ),
        (f"- Ordinary failure event: {summary.ordinary_failure_event_id or 'none'}"),
        (f"- Full-Reroute failure event: {summary.full_reroute_failure_event_id or 'none'}"),
        "",
        "## Comparison interpretation",
        "",
        (
            "The aggregate revenue and volume deltas are "
            "continuation gains after the ordinary baseline "
            "terminates. They are not paired improvements "
            "across all twenty booking events."
        ),
        "",
        (
            "On the common solved prefix, both mechanisms "
            "produce the same acceptance, accepted volume, "
            "and revenue. Full-Reroute then recovers the "
            "ordinary failure event and continues until its "
            "own later mandatory-demand infeasibility."
        ),
        "",
        (
            "The listed prior commitments were included in "
            "joint reoptimisation. Their inclusion does not "
            "by itself prove that every physical route changed."
        ),
        "",
        "## Event-level comparison",
        "",
        "| Seq. | Event | Time | Demand | Category | Volume | "
        "Ordinary acceptance | Full-Reroute acceptance | "
        "Ordinary revenue | Full-Reroute revenue | "
        "Prior commitments reoptimised | Released services |",
        "|---:|---|---:|---|---|---:|---:|---:|---:|---:|---|---|",
    ]

    for event in evaluation.events:
        lines.append(
            "| "
            f"{event.sequence_number} | "
            f"{event.event_id} | "
            f"{event.decision_time} | "
            f"{event.demand_id} | "
            f"{event.category} | "
            f"{event.requested_volume:.4f} | "
            f"{_markdown_value(event.ordinary_acceptance)} | "
            f"{_markdown_value(event.full_reroute_acceptance)} | "
            f"{_markdown_value(event.ordinary_revenue)} | "
            f"{_markdown_value(event.full_reroute_revenue)} | "
            f"{', '.join(event.rerouted_prior_demands) or '—'} | "
            f"{', '.join(event.released_services) or '—'} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "The fragment source is the cargo's execution-aware "
            "terminal-time position. Completed and in-transit "
            "movements remain immutable, while only future "
            "bookable reservations are released and reoptimised.",
            "",
            "This is the disclosed operational interpretation in "
            "Assumption A003 and should not be presented as a "
            "verbatim implementation of printed Equation (5).",
            "",
        ]
    )

    return "\n".join(lines)


def write_phase7_evaluation(
    evaluation: Phase7CanonicalEvaluation,
    *,
    output_directory: Path | str,
    report_path: Path | str,
) -> Phase7EvaluationPaths:
    """Write canonical event CSV, JSON, and Markdown outputs."""
    if not isinstance(
        evaluation,
        Phase7CanonicalEvaluation,
    ):
        raise TypeError("evaluation must be a Phase7CanonicalEvaluation.")

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

    event_csv = output_directory / "canonical_event_comparison.csv"
    evaluation_json = output_directory / "canonical_evaluation.json"

    fieldnames = (
        "sequence_number",
        "event_id",
        "decision_time",
        "demand_id",
        "category",
        "requested_volume",
        "ordinary_acceptance",
        "full_reroute_acceptance",
        "ordinary_revenue",
        "full_reroute_revenue",
        "rerouted_prior_demands",
        "released_services",
        "ordinary_solve_status",
        "full_reroute_solve_status",
    )

    with event_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for event in evaluation.events:
            writer.writerow(
                {
                    "sequence_number": (event.sequence_number),
                    "event_id": event.event_id,
                    "decision_time": event.decision_time,
                    "demand_id": event.demand_id,
                    "category": event.category,
                    "requested_volume": (_csv_value(event.requested_volume)),
                    "ordinary_acceptance": (_csv_value(event.ordinary_acceptance)),
                    "full_reroute_acceptance": (_csv_value(event.full_reroute_acceptance)),
                    "ordinary_revenue": (_csv_value(event.ordinary_revenue)),
                    "full_reroute_revenue": (_csv_value(event.full_reroute_revenue)),
                    "rerouted_prior_demands": ";".join(event.rerouted_prior_demands),
                    "released_services": ";".join(event.released_services),
                    "ordinary_solve_status": (event.ordinary_solve_status),
                    "full_reroute_solve_status": (event.full_reroute_solve_status),
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
        _markdown_report(evaluation),
        encoding="utf-8",
    )

    return Phase7EvaluationPaths(
        event_csv=event_csv,
        evaluation_json=evaluation_json,
        report_markdown=report_path,
    )
