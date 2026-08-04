"""Tests for complete event-by-event sequential DCA runs."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import run_sequential_dca


def load_config():
    """Load the committed toy configuration."""
    return load_experiment_config(Path("configs/toy_experiment.yaml"))


def test_controlled_sequential_run_completes() -> None:
    """The known regular-partial-binary example must complete."""
    instance = assemble_experiment_instance(
        load_config(),
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

    run = run_sequential_dca(instance)

    assert run.completed
    assert len(run.results) == 3
    assert run.failure_result is None
    assert run.total_revenue == pytest.approx(160.0)
    assert run.accepted_volume == pytest.approx(10.0)

    assert tuple(result.acceptance_fraction for result in run.results) == pytest.approx(
        (1.0, 0.75, 0.0)
    )


def test_capacity_transitions_match_persistent_commitments() -> None:
    """Each event must report the capacity consumed by its commitment."""
    instance = assemble_experiment_instance(
        load_config(),
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

    run = run_sequential_dca(instance)

    transitions = [result.capacity_transitions[0] for result in run.results]

    assert transitions[0].residual_before == pytest.approx(10.0)
    assert transitions[0].residual_after == pytest.approx(6.0)

    assert transitions[1].residual_before == pytest.approx(6.0)
    assert transitions[1].residual_after == pytest.approx(0.0)

    assert transitions[2].residual_before == pytest.approx(0.0)
    assert transitions[2].residual_after == pytest.approx(0.0)


def test_run_stops_when_later_regular_demand_is_infeasible() -> None:
    """An early spot commitment may block a later mandatory request."""
    instance = assemble_experiment_instance(
        load_config(),
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

    run = run_sequential_dca(instance)

    assert not run.completed
    assert len(run.results) == 2
    assert run.final_state.processed_event_count == 1
    assert run.final_state.accepted_demand_ids == ("K001",)

    failure = run.failure_result

    assert failure is not None
    assert failure.demand_id == "K002"
    assert failure.event.demand.category is CustomerCategory.REGULAR
    assert not failure.is_solved
