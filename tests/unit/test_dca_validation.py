"""Tests for independent DCA-solution validation."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.optimization import (
    DcaSolution,
    build_dca_model,
    solve_dca_model,
    validate_dca_solution,
)


def build_and_solve_controlled_model():
    """Build and solve the known three-demand example."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    instance = assemble_experiment_instance(
        config,
        demands=(
            Demand(
                demand_id="R001",
                volume=4.0,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10.0,
            ),
            Demand(
                demand_id="P001",
                volume=6.0,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.PARTIALLY_SPOT,
                fare_per_teu=20.0,
            ),
            Demand(
                demand_id="F001",
                volume=8.0,
                origin="B",
                destination="A",
                reservation_time=0,
                availability_time=1,
                due_time=2,
                category=CustomerCategory.FULLY_SPOT,
                fare_per_teu=100.0,
            ),
        ),
    )

    solution = solve_dca_model(build_dca_model(instance))

    return instance, solution


def test_valid_controlled_solution_passes_independent_validation() -> None:
    """The known optimal example must satisfy every validation check."""
    instance, solution = build_and_solve_controlled_model()

    report = validate_dca_solution(
        instance,
        solution,
    )

    assert report.is_valid
    assert report.violations == ()
    assert report.recomputed_objective == pytest.approx(160.0)
    assert report.reported_objective == pytest.approx(160.0)
    assert report.max_acceptance_violation <= 1e-6
    assert report.max_negative_flow_violation <= 1e-6
    assert report.max_flow_balance_violation <= 1e-6
    assert report.max_sink_balance_violation <= 1e-6
    assert report.max_capacity_violation <= 1e-6
    assert report.objective_violation <= 1e-6


def test_unsolved_solution_cannot_be_validated() -> None:
    """Validation requires actual decision-variable values."""
    instance, _ = build_and_solve_controlled_model()

    unsolved = DcaSolution(
        is_solved=False,
        solve_status="infeasible",
        objective_value=None,
        acceptances=(),
        flows=(),
    )

    with pytest.raises(ValueError, match="solved"):
        validate_dca_solution(
            instance,
            unsolved,
        )
