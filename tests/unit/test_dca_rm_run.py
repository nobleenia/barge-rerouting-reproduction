"""Tests for complete time-aware sequential DCA-RM."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.run import (
    run_time_aware_dca_rm,
)
from barge_rerouting.rolling_horizon import (
    run_time_aware_sequential_dca,
)


def build_instance():
    """Build current and realised future requests."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    current = Demand(
        "CURRENT",
        4,
        "A",
        "C",
        0,
        0,
        2,
        CustomerCategory.PARTIALLY_SPOT,
        10,
    )
    future = Demand(
        "FUTURE",
        4,
        "B",
        "C",
        1,
        1,
        2,
        CustomerCategory.FULLY_SPOT,
        100,
    )

    return assemble_experiment_instance(
        config,
        demands=(current, future),
    )


def provider(probability_four: float):
    """Return forecasts only before the FUTURE demand arrives."""
    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(
                0,
                1.0 - probability_four,
            ),
            VolumeProbability(
                4,
                probability_four,
            ),
        ),
    )

    def provide(event, state):
        del state

        if event.demand_id == "CURRENT":
            return (forecast,)

        return ()

    return provide


def run_rm(probability_four: float):
    """Run one complete explicit DCA-RM scenario."""
    return run_time_aware_dca_rm(
        build_instance(),
        provider(probability_four),
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )


def test_myopic_dca_accepts_current_and_loses_future() -> None:
    """Baseline commits the shared bottleneck too early."""
    baseline = run_time_aware_sequential_dca(build_instance())

    assert baseline.completed
    assert baseline.total_revenue == pytest.approx(40.0)
    assert baseline.final_state.accepted_demand_ids == ("CURRENT",)
    assert baseline.final_state.rejected_demand_ids == ("FUTURE",)


def test_high_probability_protection_improves_realised_revenue() -> None:
    """DCA-RM protects capacity and later accepts FUTURE."""
    run = run_rm(0.50)

    assert run.completed
    assert run.total_realised_revenue == pytest.approx(400.0)
    assert run.accepted_volume == pytest.approx(4.0)
    assert run.final_state.accepted_demand_ids == ("FUTURE",)
    assert run.final_state.rejected_demand_ids == ("CURRENT",)


def test_low_probability_reverses_full_timeline_decision() -> None:
    """Low forecast value reproduces the myopic outcome."""
    run = run_rm(0.05)

    assert run.completed
    assert run.total_realised_revenue == pytest.approx(40.0)
    assert run.final_state.accepted_demand_ids == ("CURRENT",)
    assert run.final_state.rejected_demand_ids == ("FUTURE",)


def test_tentative_protection_does_not_reduce_persisted_capacity() -> None:
    """Event-one protection is discarded before event two."""
    run = run_rm(0.50)
    first = run.results[0]

    transition = first.capacity_transition_for("transport::1::S_BOTTLENECK")

    assert first.protection_for("FUTURE").protected_volume == pytest.approx(4.0)

    assert transition.residual_before == pytest.approx(4.0)
    assert transition.residual_after == pytest.approx(4.0)


def test_objective_sum_is_not_reported_as_realised_revenue() -> None:
    """Expected and realised values must remain separate."""
    run = run_rm(0.50)

    assert run.summed_event_objectives == pytest.approx(600.0)
    assert run.total_expected_future_contribution == pytest.approx(200.0)
    assert run.total_realised_revenue == pytest.approx(400.0)


def test_time_aware_dca_rm_run_is_deterministic() -> None:
    """Identical inputs must reproduce the same run."""
    first = run_rm(0.50)
    second = run_rm(0.50)

    assert first == second
