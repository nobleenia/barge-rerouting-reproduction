"""Tests for current allocation with future capacity protection."""

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
from barge_rerouting.optimization.dca_rm import (
    build_dca_rm_model,
    solve_dca_rm_model,
    validate_dca_rm_solution,
)
from barge_rerouting.revenue_management import (
    select_explicit_future_set,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)


def build_example(
    *,
    current_volume: float = 4,
    current_fare: float = 10,
):
    """Build one current request using the shared bottleneck."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    current = Demand(
        demand_id="CURRENT",
        volume=current_volume,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=current_fare,
    )

    instance = assemble_experiment_instance(
        config,
        demands=(current,),
    )
    state = RollingBookingState.empty(instance)
    event = build_booking_timeline(instance).event_at_sequence(1)

    return instance, state, event


def future_forecast(
    *,
    probability_four: float,
    fare: float = 100,
) -> FutureDemandForecast:
    """Build a zero-or-four future-volume forecast."""
    return FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=fare,
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


def solve_rm(
    forecast: FutureDemandForecast,
    *,
    interpretation: FutureValueInterpretation = (FutureValueInterpretation.PRINTED),
    current_volume: float = 4,
    current_fare: float = 10,
):
    """Build and solve one controlled DCA-RM decision."""
    instance, state, event = build_example(
        current_volume=current_volume,
        current_fare=current_fare,
    )
    future_set = select_explicit_future_set(
        instance,
        event,
        (forecast,),
    )
    artifacts = build_dca_rm_model(
        instance,
        state,
        event,
        future_set,
        value_interpretation=interpretation,
    )

    try:
        solution = solve_dca_rm_model(artifacts)
        report = validate_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    return solution, report


def test_myopic_dca_accepts_low_fare_current_request() -> None:
    """DCA without forecasts must use available capacity."""
    instance, state, event = build_example()

    artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
    )

    try:
        solution = solve_sequential_booking_model(artifacts)
    finally:
        artifacts.model.end()

    assert solution.is_solved
    assert solution.acceptance_fraction == pytest.approx(1.0)
    assert solution.objective_value == pytest.approx(40.0)


def test_high_future_value_rejects_current_request() -> None:
    """DCA-RM must protect capacity with higher expected value."""
    solution, report = solve_rm(future_forecast(probability_four=0.5))

    assert solution.is_solved
    assert report.is_valid
    assert solution.acceptance_fraction == pytest.approx(0.0)

    protection = solution.protection_for("FUTURE")

    assert protection.protection_level == 4
    assert protection.protected_volume == pytest.approx(4.0)
    assert protection.credited_expected_revenue == pytest.approx(200.0)
    assert solution.objective_value == pytest.approx(200.0)


def test_lower_future_probability_reverses_decision() -> None:
    """Forecast error can reverse the capacity-protection choice."""
    solution, report = solve_rm(future_forecast(probability_four=0.05))

    assert report.is_valid
    assert solution.acceptance_fraction == pytest.approx(1.0)

    protection = solution.protection_for("FUTURE")

    assert protection.protection_level == 0
    assert protection.protected_volume == pytest.approx(0.0)
    assert solution.objective_value == pytest.approx(40.0)


def test_selector_and_maxvol_linking() -> None:
    """Exactly one selected y level must define maxvol."""
    solution, _ = solve_rm(future_forecast(probability_four=0.5))

    assert tuple(
        solution.selector_value("FUTURE", level) for level in (1, 2, 3, 4)
    ) == pytest.approx((0.0, 0.0, 0.0, 1.0))

    assert solution.protection_for("FUTURE").protected_volume == pytest.approx(4.0)


def test_future_tentative_flow_equals_protected_volume() -> None:
    """Protected volume must be routed through the future network."""
    solution, report = solve_rm(future_forecast(probability_four=0.5))

    assert report.is_valid

    assert solution.future_flow_on(
        "FUTURE",
        "transport::1::S_BOTTLENECK",
    ) == pytest.approx(4.0)

    assert solution.current_flow_on("transport::1::S_BOTTLENECK") == pytest.approx(0.0)


def test_current_and_future_flow_share_capacity() -> None:
    """Current and tentative flow must not exceed four TEU."""
    solution, report = solve_rm(future_forecast(probability_four=0.5))

    used = solution.current_flow_on("transport::1::S_BOTTLENECK") + solution.future_flow_on(
        "FUTURE",
        "transport::1::S_BOTTLENECK",
    )

    assert used == pytest.approx(4.0)
    assert report.max_capacity_violation == pytest.approx(0.0)


def test_no_future_set_reduces_to_current_dca() -> None:
    """Empty K(current) must reproduce current-only allocation."""
    instance, state, event = build_example()
    future_set = select_explicit_future_set(
        instance,
        event,
        (),
    )

    artifacts = build_dca_rm_model(
        instance,
        state,
        event,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        solution = solve_dca_rm_model(artifacts)
        report = validate_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert report.is_valid
    assert solution.acceptance_fraction == pytest.approx(1.0)
    assert solution.future_expected_revenue == pytest.approx(0.0)
    assert solution.objective_value == pytest.approx(40.0)


def test_printed_and_capped_values_change_protection() -> None:
    """The sensitivity interpretation can change the optimum."""
    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10,
        outcomes=(
            VolumeProbability(0, 0.25),
            VolumeProbability(2, 0.25),
            VolumeProbability(4, 0.50),
        ),
    )

    printed, printed_report = solve_rm(
        forecast,
        interpretation=(FutureValueInterpretation.PRINTED),
        current_volume=2,
        current_fare=6,
    )
    capped, capped_report = solve_rm(
        forecast,
        interpretation=(FutureValueInterpretation.CAPPED),
        current_volume=2,
        current_fare=6,
    )

    assert printed_report.is_valid
    assert capped_report.is_valid

    assert printed.protection_for("FUTURE").protection_level == 4
    assert printed.acceptance_fraction == pytest.approx(0.0)

    assert capped.protection_for("FUTURE").protection_level == 2
    assert capped.acceptance_fraction == pytest.approx(1.0)

    assert printed.objective_value == pytest.approx(25.0)
    assert capped.objective_value == pytest.approx(27.0)


def test_solution_is_deterministic() -> None:
    """Identical model inputs must give identical extracted results."""
    forecast = future_forecast(probability_four=0.5)

    first, first_report = solve_rm(forecast)
    second, second_report = solve_rm(forecast)

    assert first_report.is_valid
    assert second_report.is_valid
    assert first == second
