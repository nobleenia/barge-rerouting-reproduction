"""Tests for complete time-aware sequential DCA-RRM."""

from dataclasses import replace
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
from barge_rerouting.rerouting.run import (
    run_full_reroute,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.rrm_orchestration import (
    run_dca_rrm_event,
)
from barge_rerouting.revenue_management.rrm_run import (
    run_time_aware_dca_rrm,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)


def quiet_config(path: str):
    """Load a configuration with solver logging disabled."""
    config = load_experiment_config(Path(path))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def empty_provider(event, state):
    """Return no future forecasts."""
    del event, state
    return ()


def high_probability_instance():
    """Build current and realised future requests."""
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
        quiet_config("tests/fixtures/rerouting_switch_experiment.yaml"),
        demands=(current, future),
    )


def high_probability_provider(event, state):
    """Protect FUTURE only before it arrives."""
    del state

    if event.demand_id != "CURRENT":
        return ()

    return (
        FutureDemandForecast(
            forecast_id="FUTURE",
            origin="B",
            destination="C",
            availability_time=1,
            due_time=2,
            category=(CustomerCategory.PARTIALLY_SPOT),
            fare_per_teu=100,
            outcomes=(
                VolumeProbability(0, 0.50),
                VolumeProbability(4, 0.50),
            ),
        ),
    )


def run_high_probability_rrm():
    """Run the controlled high-probability scenario."""
    return run_time_aware_dca_rrm(
        high_probability_instance(),
        high_probability_provider,
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )


def switch_instance():
    """Build the controlled two-event rerouting instance."""
    old = Demand(
        demand_id="KOLD",
        volume=4,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=3,
        category=CustomerCategory.REGULAR,
        fare_per_teu=10,
    )
    current = Demand(
        demand_id="KNEW",
        volume=4,
        origin="B",
        destination="C",
        reservation_time=1,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.FULLY_SPOT,
        fare_per_teu=100,
    )

    return assemble_experiment_instance(
        quiet_config("tests/fixtures/rerouting_switch_experiment.yaml"),
        demands=(old, current),
    )


def combined_event_inputs():
    """Build an event containing past, current, and future flow."""
    instance = assemble_experiment_instance(
        quiet_config("tests/fixtures/rerouting_switch_experiment.yaml"),
        demands=(
            Demand(
                "K001",
                1,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                1,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                20,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)
    first_event = timeline.event_at_sequence(1)

    artifacts = build_sequential_booking_model(
        instance,
        state,
        first_event,
    )

    try:
        solution = solve_sequential_booking_model(artifacts)
        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=(CustomerCategory.PARTIALLY_SPOT),
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(0, 0.50),
            VolumeProbability(4, 0.50),
        ),
    )

    return (
        instance,
        state,
        timeline.event_at_sequence(2),
        forecast,
    )


def test_event_orchestration_contains_all_commodity_groups() -> None:
    """Past, current, and future decisions must coexist."""
    (
        instance,
        state,
        event,
        forecast,
    ) = combined_event_inputs()

    result = run_dca_rrm_event(
        instance,
        state,
        event,
        (forecast,),
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )

    assert result.event_was_processed
    assert result.fragment_networks.indexes
    assert result.solution.fragment_flows
    assert result.solution.future_flows
    assert result.forecast_ids == ("FUTURE",)

    assert result.transition is not None
    assert result.transition.discarded_forecast_ids == ("FUTURE",)
    assert "FUTURE" not in (result.state_after.accepted_demand_ids)


def test_no_forecasts_match_full_reroute_run() -> None:
    """Empty K(current) must reduce to Full-Reroute."""
    instance = switch_instance()

    reroute_run = run_full_reroute(instance)
    rrm_run = run_time_aware_dca_rrm(
        instance,
        empty_provider,
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )

    assert rrm_run.completed
    assert rrm_run.processed_event_count == 2
    assert rrm_run.final_state == reroute_run.final_state
    assert rrm_run.total_realised_revenue == pytest.approx(reroute_run.total_revenue)
    assert rrm_run.accepted_volume == pytest.approx(reroute_run.accepted_volume)
    assert rrm_run.results[1].rerouted_demand_ids == ("KOLD",)


def test_high_probability_protects_and_accepts_future() -> None:
    """DCA-RRM must reproduce DCA-RM without past fragments."""
    run = run_high_probability_rrm()

    assert run.completed
    assert run.processed_event_count == 2
    assert run.total_realised_revenue == pytest.approx(400.0)
    assert run.accepted_volume == pytest.approx(4.0)

    assert run.final_state.accepted_demand_ids == ("FUTURE",)
    assert run.final_state.rejected_demand_ids == ("CURRENT",)

    first = run.results[0]

    assert first.protection_for("FUTURE").protected_volume == pytest.approx(4.0)
    assert first.discarded_tentative_future_volume == pytest.approx(4.0)


def test_objective_and_realised_revenue_remain_separate() -> None:
    """Forecast value must not be reported as earned revenue."""
    run = run_high_probability_rrm()

    assert run.summed_event_objectives == pytest.approx(600.0)
    assert run.total_expected_future_contribution == pytest.approx(200.0)
    assert run.total_realised_revenue == pytest.approx(400.0)
    assert run.cumulative_selected_protection_volume == pytest.approx(4.0)
    assert run.cumulative_discarded_future_volume == pytest.approx(4.0)


def test_run_stops_at_first_infeasible_regular_request() -> None:
    """Mandatory cargo infeasibility must terminate DCA-RRM."""
    instance = assemble_experiment_instance(
        quiet_config("configs/toy_experiment.yaml"),
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
        ),
    )

    run = run_time_aware_dca_rrm(
        instance,
        empty_provider,
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )

    assert not run.completed
    assert run.processed_event_count == 1
    assert len(run.results) == 2

    failure = run.failure_result

    assert failure is not None
    assert failure.event.demand_id == "K002"
    assert not failure.solution.is_solved
    assert failure.transition is None
    assert failure.state_after == failure.state_before


def test_sequential_dca_rrm_is_deterministic() -> None:
    """Identical inputs must reproduce the same run."""
    first = run_high_probability_rrm()
    second = run_high_probability_rrm()

    assert first == second


def test_rrm_capacity_transition_allows_net_release() -> None:
    """Rerouting may legitimately increase bookable capacity."""
    from barge_rerouting.revenue_management.rrm_orchestration import (
        DcaRrmArcCapacityTransition,
    )

    transition = DcaRrmArcCapacityTransition(
        arc_id="transport::1::S_RELEASED",
        residual_before=0.0,
        residual_after=4.0,
    )

    assert transition.reserved_volume_change == pytest.approx(-4.0)
    assert transition.newly_reserved_volume == pytest.approx(0.0)
    assert transition.released_volume == pytest.approx(4.0)
