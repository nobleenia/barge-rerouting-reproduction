"""Tests for canonical Full-Reroute comparison exports."""

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    evaluate_full_reroute_against_sequential,
    write_phase7_evaluation,
)


def quiet_config():
    """Load the toy configuration without solver output."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def build_equal_mechanism_instance():
    """Build a single-route three-demand comparison."""
    return assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                4,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                8,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                20,
            ),
            Demand(
                "K003",
                6,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )


@pytest.fixture(scope="module")
def equal_evaluation():
    """Return one reusable deterministic evaluation."""
    return evaluate_full_reroute_against_sequential(build_equal_mechanism_instance())


def test_summary_deltas_match_run_totals(
    equal_evaluation,
) -> None:
    """Single-route mechanisms must produce equal totals."""
    summary = equal_evaluation.summary

    assert summary.ordinary_revenue == pytest.approx(160.0)
    assert summary.full_reroute_revenue == pytest.approx(160.0)
    assert summary.revenue_delta == pytest.approx(0.0)

    assert summary.ordinary_accepted_volume == pytest.approx(10.0)
    assert summary.full_reroute_accepted_volume == pytest.approx(10.0)
    assert summary.accepted_volume_delta == pytest.approx(0.0)


def test_event_rows_cover_complete_timeline(
    equal_evaluation,
) -> None:
    """Exports must include every request in timeline order."""
    assert len(equal_evaluation.events) == 3

    assert tuple(event.sequence_number for event in equal_evaluation.events) == (1, 2, 3)

    assert tuple(event.demand_id for event in equal_evaluation.events) == ("K001", "K002", "K003")


def test_event_rows_preserve_acceptance_results(
    equal_evaluation,
) -> None:
    """Event comparison must retain both mechanisms."""
    assert tuple(event.ordinary_acceptance for event in equal_evaluation.events) == pytest.approx(
        (1.0, 0.75, 0.0)
    )

    assert tuple(
        event.full_reroute_acceptance for event in equal_evaluation.events
    ) == pytest.approx((1.0, 0.75, 0.0))


def test_later_events_are_marked_not_run_after_failure() -> None:
    """Rows after terminal infeasibility must remain explicit."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                10,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
            Demand(
                "K002",
                1,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K003",
                1,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                20,
            ),
        ),
    )

    evaluation = evaluate_full_reroute_against_sequential(instance)
    third = evaluation.events[2]

    assert third.ordinary_acceptance is None
    assert third.full_reroute_acceptance is None
    assert third.ordinary_solve_status == "not-run"
    assert third.full_reroute_solve_status == "not-run"


def test_evaluation_export_is_complete(
    equal_evaluation,
    tmp_path,
) -> None:
    """CSV, JSON, and Markdown outputs must be readable."""
    paths = write_phase7_evaluation(
        equal_evaluation,
        output_directory=tmp_path / "results",
        report_path=tmp_path / "report.md",
    )

    assert paths.event_csv.is_file()
    assert paths.evaluation_json.is_file()
    assert paths.report_markdown.is_file()

    with paths.event_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 3
    assert rows[0]["event_id"] == "booking::0001::K001"

    payload = json.loads(paths.evaluation_json.read_text(encoding="utf-8"))

    assert payload["summary"]["revenue_delta"] == pytest.approx(0.0)
    assert len(payload["events"]) == 3

    report = paths.report_markdown.read_text(encoding="utf-8")

    assert "Phase 7 Canonical Full-Reroute Evaluation" in report
    assert "Assumption A003" in report
    assert "booking::0003::K003" in report


def test_evaluation_is_deterministic() -> None:
    """Repeated evaluations must be exactly identical."""
    instance = build_equal_mechanism_instance()

    first = evaluate_full_reroute_against_sequential(instance)
    second = evaluate_full_reroute_against_sequential(instance)

    assert first == second


def test_canonical_failure_recovery_metrics_are_explicit() -> None:
    """Canonical gains must be identified as continuation gains."""
    instance = assemble_experiment_instance(quiet_config())

    evaluation = evaluate_full_reroute_against_sequential(instance)
    summary = evaluation.summary

    assert summary.ordinary_failure_event_id == ("booking::0009::K0011")
    assert summary.full_reroute_failure_event_id == ("booking::0012::K0017")

    assert summary.ordinary_failure_recovered
    assert summary.additional_processed_events == 3
    assert summary.failure_sequence_shift == 3

    assert summary.paired_acceptance_improvement_count == 0
    assert summary.common_prefix_revenue_delta == (pytest.approx(0.0))
    assert summary.common_prefix_accepted_volume_delta == pytest.approx(0.0)

    assert summary.continuation_revenue_after_ordinary_failure == pytest.approx(155.01)
    assert summary.continuation_volume_after_ordinary_failure == pytest.approx(5.0)
