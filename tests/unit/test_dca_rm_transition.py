"""Tests for persistence of realised DCA-RM decisions."""

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
)
from barge_rerouting.revenue_management.future_set import (
    select_explicit_future_set,
)
from barge_rerouting.revenue_management.transition import (
    apply_dca_rm_solution,
    commitment_from_dca_rm_solution,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
)


def build_decision(probability_four: float):
    """Build and solve one first-event DCA-RM decision."""
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
    instance = assemble_experiment_instance(
        config,
        demands=(current,),
    )
    state = RollingBookingState.empty(instance)
    event = build_booking_timeline(instance).event_at_sequence(1)
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
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )
    solution = solve_dca_rm_model(artifacts)

    return artifacts, solution


def test_rejected_current_demand_creates_no_commitment() -> None:
    """High future value must not become a fake commitment."""
    artifacts, solution = build_decision(0.50)

    try:
        commitment = commitment_from_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert solution.acceptance_fraction == pytest.approx(0.0)
    assert solution.future_flow_on(
        "FUTURE",
        "transport::1::S_BOTTLENECK",
    ) == pytest.approx(4.0)
    assert commitment is None


def test_future_tentative_flow_is_not_persisted() -> None:
    """Only the current rejection is written to state."""
    artifacts, solution = build_decision(0.50)

    try:
        state = apply_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert state.processed_event_count == 1
    assert state.accepted_demand_ids == ()
    assert state.rejected_demand_ids == ("CURRENT",)
    assert state.commitments == ()


def test_low_future_value_persists_only_current_demand() -> None:
    """A realised current acceptance becomes one commitment."""
    artifacts, solution = build_decision(0.05)

    try:
        state = apply_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert solution.acceptance_fraction == pytest.approx(1.0)
    assert state.accepted_demand_ids == ("CURRENT",)
    assert len(state.commitments) == 1
    assert state.commitments[0].demand_id == "CURRENT"


def test_objective_is_split_before_persistence() -> None:
    """Expected future value must not masquerade as revenue."""
    artifacts, solution = build_decision(0.50)

    try:
        state = apply_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert solution.objective_value == pytest.approx(200.0)
    assert solution.current_revenue == pytest.approx(0.0)
    assert solution.future_expected_revenue == pytest.approx(200.0)
    assert state.commitments == ()
