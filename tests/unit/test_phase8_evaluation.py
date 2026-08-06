"""Tests for canonical synthetic DCA-RM evaluation."""

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureValueInterpretation,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management.evaluation import (
    ForecastSensitivityRegime,
    build_attribute_conditioned_forecast_provider,
    default_sensitivity_regimes,
    evaluate_phase8_canonical,
    write_phase8_evaluation,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
)


def quiet_config():
    """Load the controlled network without solver logs."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def build_instance(
    future_volume: int = 4,
):
    """Build a two-event shared-bottleneck instance."""
    return assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "CURRENT",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                10,
            ),
            Demand(
                "FUTURE",
                future_volume,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )


def test_default_regimes_cover_printed_and_capped() -> None:
    """Three probabilities must be evaluated twice."""
    regimes = default_sensitivity_regimes()

    assert len(regimes) == 6

    assert {regime.value_interpretation for regime in regimes} == {
        FutureValueInterpretation.PRINTED,
        FutureValueInterpretation.CAPPED,
    }

    assert {regime.occurrence_probability for regime in regimes} == {0.20, 0.50, 0.80}


def test_forecast_does_not_use_realised_future_volume() -> None:
    """Changing realised volume must not change the forecast."""
    first_instance = build_instance(future_volume=2)
    second_instance = build_instance(future_volume=4)

    first_timeline = build_booking_timeline(first_instance)
    second_timeline = build_booking_timeline(second_instance)

    first_provider = build_attribute_conditioned_forecast_provider(
        first_timeline,
        maximum_volume=10,
        occurrence_probability=0.50,
    )
    second_provider = build_attribute_conditioned_forecast_provider(
        second_timeline,
        maximum_volume=10,
        occurrence_probability=0.50,
    )

    first_forecasts = first_provider(
        first_timeline.event_at_sequence(1),
        RollingBookingState.empty(first_instance),
    )
    second_forecasts = second_provider(
        second_timeline.event_at_sequence(1),
        RollingBookingState.empty(second_instance),
    )

    assert first_forecasts == second_forecasts

    forecast = first_forecasts[0]

    assert forecast.maximum_volume == 10
    assert forecast.expected_volume == pytest.approx(2.75)


def test_evaluation_contains_baseline_and_all_regimes() -> None:
    """The evaluation must include one DCA and six RM rows."""
    evaluation = evaluate_phase8_canonical(
        build_instance(),
        maximum_volume=10,
    )

    assert len(evaluation.summaries) == 7

    assert evaluation.summaries[0].policy_key == "dca"

    assert len(evaluation.events) == (7 * evaluation.total_booking_events)


def test_high_printed_probability_can_protect_capacity() -> None:
    """High probability should reject CURRENT and accept FUTURE."""
    regimes = (
        ForecastSensitivityRegime(
            key="printed_low",
            label="Printed low",
            occurrence_probability=0.20,
            value_interpretation=(FutureValueInterpretation.PRINTED),
        ),
        ForecastSensitivityRegime(
            key="printed_high",
            label="Printed high",
            occurrence_probability=0.80,
            value_interpretation=(FutureValueInterpretation.PRINTED),
        ),
    )

    evaluation = evaluate_phase8_canonical(
        build_instance(),
        regimes=regimes,
        maximum_volume=10,
    )

    baseline = evaluation.summary_for("dca")
    low = evaluation.summary_for("printed_low")
    high = evaluation.summary_for("printed_high")

    assert baseline.realised_revenue == pytest.approx(40.0)
    assert low.realised_revenue == pytest.approx(40.0)
    assert high.realised_revenue == pytest.approx(400.0)

    assert low.accepted_demand_ids == ("CURRENT",)
    assert high.accepted_demand_ids == ("FUTURE",)

    assert high.positive_protection_count >= 1
    assert high.selected_protection_volume >= 4.0


def test_event_rows_separate_objective_and_revenue() -> None:
    """Expected contribution must not be reported as earned."""
    regime = ForecastSensitivityRegime(
        key="printed_high",
        label="Printed high",
        occurrence_probability=0.80,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    evaluation = evaluate_phase8_canonical(
        build_instance(),
        regimes=(regime,),
        maximum_volume=10,
    )

    first_rm_event = next(
        record
        for record in evaluation.events
        if (record.policy_key == "printed_high" and record.sequence_number == 1)
    )

    assert first_rm_event.current_realised_revenue == pytest.approx(0.0)
    assert first_rm_event.future_expected_revenue is not None
    assert first_rm_event.future_expected_revenue > 0.0
    assert first_rm_event.optimisation_objective == pytest.approx(
        first_rm_event.future_expected_revenue
    )


def test_phase8_evaluation_is_deterministic() -> None:
    """Repeated evaluation must be identical."""
    regimes = (
        ForecastSensitivityRegime(
            key="printed_high",
            label="Printed high",
            occurrence_probability=0.80,
            value_interpretation=(FutureValueInterpretation.PRINTED),
        ),
        ForecastSensitivityRegime(
            key="capped_high",
            label="Capped high",
            occurrence_probability=0.80,
            value_interpretation=(FutureValueInterpretation.CAPPED),
        ),
    )
    instance = build_instance()

    first = evaluate_phase8_canonical(
        instance,
        regimes=regimes,
        maximum_volume=10,
    )
    second = evaluate_phase8_canonical(
        instance,
        regimes=regimes,
        maximum_volume=10,
    )

    assert first == second


def test_phase8_export_is_complete(
    tmp_path,
) -> None:
    """CSV, JSON, and Markdown outputs must be complete."""
    regime = ForecastSensitivityRegime(
        key="printed_high",
        label="Printed high",
        occurrence_probability=0.80,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )
    evaluation = evaluate_phase8_canonical(
        build_instance(),
        regimes=(regime,),
        maximum_volume=10,
    )

    paths = write_phase8_evaluation(
        evaluation,
        output_directory=tmp_path / "results",
        report_path=tmp_path / "report.md",
    )

    assert paths.policy_summary_csv.is_file()
    assert paths.event_results_csv.is_file()
    assert paths.evaluation_json.is_file()
    assert paths.report_markdown.is_file()

    with paths.policy_summary_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        summary_rows = list(csv.DictReader(stream))

    with paths.event_results_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        event_rows = list(csv.DictReader(stream))

    assert len(summary_rows) == 2
    assert len(event_rows) == 4

    assert summary_rows[0]["policy_key"] == "dca"
    assert summary_rows[1]["policy_key"] == ("printed_high")

    payload = json.loads(paths.evaluation_json.read_text(encoding="utf-8"))

    assert payload["instance_fingerprint"] == (evaluation.instance_fingerprint)
    assert len(payload["summaries"]) == 2
    assert len(payload["events"]) == 4


def test_phase8_report_discloses_scientific_boundary(
    tmp_path,
) -> None:
    """Generated report must not overclaim reproduction."""
    regime = ForecastSensitivityRegime(
        key="capped_high",
        label="Capped high",
        occurrence_probability=0.80,
        value_interpretation=(FutureValueInterpretation.CAPPED),
    )
    evaluation = evaluate_phase8_canonical(
        build_instance(),
        regimes=(regime,),
        maximum_volume=10,
    )

    paths = write_phase8_evaluation(
        evaluation,
        output_directory=tmp_path / "results",
        report_path=tmp_path / "report.md",
    )

    report = paths.report_markdown.read_text(encoding="utf-8")

    assert "attribute-conditioned synthetic" in report
    assert "not an exact numerical reproduction" in report
    assert "Assumption A004" in report
    assert "Assumption A005" in report
    assert "Assumption A016" in report
    assert "Realised revenue is the primary" in report
