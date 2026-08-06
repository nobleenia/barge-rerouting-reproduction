"""Tests for the canonical four-mechanism evaluation."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import (
    load_experiment_config,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureValueInterpretation,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.rerouting.run import (
    run_full_reroute,
)
from barge_rerouting.revenue_management.evaluation import (
    ForecastSensitivityRegime,
)
from barge_rerouting.revenue_management.rrm_evaluation import (
    evaluate_phase9_canonical,
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


def build_instance():
    """Build the Phase 8 shared-bottleneck example."""
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
                4,
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


def high_regime():
    """Return one high-probability printed regime."""
    return ForecastSensitivityRegime(
        key="rm_printed_p80",
        label="DCA-RM printed p=0.80",
        occurrence_probability=0.80,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )


def evaluate_controlled():
    """Evaluate all four mechanisms once."""
    return evaluate_phase9_canonical(
        build_instance(),
        regimes=(high_regime(),),
        maximum_volume=10,
    )


def test_evaluation_contains_four_mechanisms() -> None:
    """One regime must produce exactly four policy rows."""
    evaluation = evaluate_controlled()

    assert len(evaluation.summaries) == 4
    assert {summary.mechanism for summary in evaluation.summaries} == {
        "DCA",
        "DCA-R",
        "DCA-RM",
        "DCA-RRM",
    }

    assert len(evaluation.events) == (4 * evaluation.total_booking_events)


def test_rm_and_rrm_match_without_reroutable_fragments() -> None:
    """Without useful fragments, DCA-RRM reduces to DCA-RM."""
    evaluation = evaluate_controlled()

    rm = evaluation.summary_for("rm_printed_p80")
    rrm = evaluation.summary_for("rrm_printed_p80")

    assert rrm.accepted_volume == pytest.approx(rm.accepted_volume)
    assert rrm.realised_revenue == pytest.approx(rm.realised_revenue)
    assert rrm.summed_optimisation_objectives == pytest.approx(rm.summed_optimisation_objectives)
    assert rrm.summed_expected_future_contribution == pytest.approx(
        rm.summed_expected_future_contribution
    )
    assert rrm.accepted_demand_ids == rm.accepted_demand_ids


def test_dca_r_summary_matches_standalone_run() -> None:
    """The comparison must not alter Full-Reroute results."""
    instance = build_instance()
    standalone = run_full_reroute(instance)

    evaluation = evaluate_phase9_canonical(
        instance,
        regimes=(high_regime(),),
        maximum_volume=10,
    )
    summary = evaluation.summary_for("dca_r")

    assert summary.processed_events == (standalone.processed_event_count)
    assert summary.accepted_volume == pytest.approx(standalone.accepted_volume)
    assert summary.realised_revenue == pytest.approx(standalone.total_revenue)
    assert summary.accepted_demand_ids == (standalone.final_state.accepted_demand_ids)


def test_future_value_is_not_reported_as_revenue() -> None:
    """RM and RRM objective sums must remain diagnostic."""
    evaluation = evaluate_controlled()

    for policy_key in (
        "rm_printed_p80",
        "rrm_printed_p80",
    ):
        summary = evaluation.summary_for(policy_key)

        assert summary.summed_expected_future_contribution > 0.0
        assert summary.summed_optimisation_objectives > summary.realised_revenue


def test_event_rows_cover_solved_and_not_run_events() -> None:
    """Every policy must retain the complete timeline."""
    evaluation = evaluate_controlled()

    for summary in evaluation.summaries:
        records = evaluation.events_for(summary.policy_key)

        assert len(records) == (evaluation.total_booking_events)
        assert tuple(record.sequence_number for record in records) == tuple(
            range(
                1,
                evaluation.total_booking_events + 1,
            )
        )


def test_phase9_evaluation_is_deterministic() -> None:
    """Repeated four-mechanism evaluation must agree."""
    instance = build_instance()

    first = evaluate_phase9_canonical(
        instance,
        regimes=(high_regime(),),
        maximum_volume=10,
    )
    second = evaluate_phase9_canonical(
        instance,
        regimes=(high_regime(),),
        maximum_volume=10,
    )

    assert first == second


def canonical_instance():
    """Build the repository's canonical seeded instance."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    return assemble_experiment_instance(config)


def test_canonical_headline_results_are_locked() -> None:
    """Freeze the principal Phase 9 canonical findings."""
    evaluation = evaluate_phase9_canonical(canonical_instance())

    dca = evaluation.summary_for("dca")
    dca_r = evaluation.summary_for("dca_r")
    rm = evaluation.summary_for("rm_printed_p80")
    rrm = evaluation.summary_for("rrm_printed_p80")

    assert dca.processed_events == 8
    assert dca.accepted_volume == pytest.approx(26.0)
    assert dca.realised_revenue == pytest.approx(823.90)
    assert dca.failure_event_id == "booking::0009::K0011"

    assert dca_r.processed_events == 11
    assert dca_r.accepted_volume == pytest.approx(31.0)
    assert dca_r.realised_revenue == pytest.approx(978.91)
    assert dca_r.failure_event_id == "booking::0012::K0017"

    for summary in (rm, rrm):
        assert summary.processed_events == 15
        assert summary.accepted_volume == pytest.approx(36.0)
        assert summary.realised_revenue == pytest.approx(1324.86)
        assert summary.failure_event_id == ("booking::0016::K0013")


def test_canonical_rm_rrm_pairs_match_eventwise_realisation() -> None:
    """Observed RM/RRM equality must hold event by event."""
    evaluation = evaluate_phase9_canonical(canonical_instance())

    for regime in evaluation.regimes:
        rm_records = evaluation.events_for(regime.key)

        rrm_key = f"rrm_{regime.key[3:]}" if regime.key.startswith("rm_") else f"rrm_{regime.key}"
        rrm_records = evaluation.events_for(rrm_key)

        for rm_record, rrm_record in zip(
            rm_records,
            rrm_records,
            strict=True,
        ):
            assert rrm_record.event_status == rm_record.event_status
            assert (
                rrm_record.acceptance_fraction == pytest.approx(rm_record.acceptance_fraction)
                if rm_record.acceptance_fraction is not None
                else rrm_record.acceptance_fraction is None
            )
            assert (
                rrm_record.accepted_volume == pytest.approx(rm_record.accepted_volume)
                if rm_record.accepted_volume is not None
                else rrm_record.accepted_volume is None
            )
            assert (
                rrm_record.current_realised_revenue
                == pytest.approx(rm_record.current_realised_revenue)
                if rm_record.current_realised_revenue is not None
                else (rrm_record.current_realised_revenue is None)
            )


def test_phase9_export_is_complete(tmp_path) -> None:
    """CSV, JSON, and Markdown outputs must be complete."""
    import csv
    import json

    from barge_rerouting.revenue_management.rrm_evaluation import (
        write_phase9_evaluation,
    )

    evaluation = evaluate_controlled()

    paths = write_phase9_evaluation(
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
        summaries = list(csv.DictReader(stream))

    with paths.event_results_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        events = list(csv.DictReader(stream))

    assert len(summaries) == 4
    assert len(events) == (4 * evaluation.total_booking_events)

    payload = json.loads(paths.evaluation_json.read_text(encoding="utf-8"))

    assert payload["instance_fingerprint"] == (evaluation.instance_fingerprint)
    assert len(payload["summaries"]) == 4
    assert len(payload["events"]) == len(events)


def test_phase9_report_discloses_boundaries(tmp_path) -> None:
    """The generated report must not overclaim reproduction."""
    from barge_rerouting.revenue_management.rrm_evaluation import (
        write_phase9_evaluation,
    )

    evaluation = evaluate_controlled()

    paths = write_phase9_evaluation(
        evaluation,
        output_directory=tmp_path / "results",
        report_path=tmp_path / "report.md",
    )

    report = paths.report_markdown.read_text(encoding="utf-8")

    assert "not an exact numerical reproduction" in report
    assert "Realised revenue is the primary" in report
    assert "observed property of this canonical instance" in report
    assert "not a general mathematical equivalence" in report
    assert "Assumption A003" in report
    assert "Assumption A004" in report
    assert "current request's feasible transport arcs" in report
    assert "does not prove that every listed physical route changed" in report


def test_phase9_report_declares_truck_disabled_scope(
    tmp_path,
) -> None:
    """The generated report must delimit the Phase 9 model."""
    from barge_rerouting.revenue_management.rrm_evaluation import (
        write_phase9_evaluation,
    )

    evaluation = evaluate_controlled()

    paths = write_phase9_evaluation(
        evaluation,
        output_directory=tmp_path / "results",
        report_path=tmp_path / "report.md",
    )

    report = paths.report_markdown.read_text(encoding="utf-8")

    assert "stable service capacities" in report
    assert "truck recourse disabled" in report
    assert "truck-penalty term is zero by construction" in report
    assert "Service-status changes and explicit truck recourse belong" in report
