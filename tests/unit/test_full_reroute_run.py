"""Tests for complete event-by-event Full-Reroute runs."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import run_full_reroute
from barge_rerouting.rolling_horizon import run_sequential_dca


def load_config():
    """Load the canonical toy network."""
    return load_experiment_config(Path("configs/toy_experiment.yaml"))


def build_shared_service_instance():
    """Build three requests sharing the ten-TEU S6 service."""
    return assemble_experiment_instance(
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


def test_full_reroute_processes_every_booking_event() -> None:
    """Every incoming request must invoke Full-Reroute."""
    run = run_full_reroute(build_shared_service_instance())

    assert run.completed
    assert run.processed_event_count == 3
    assert len(run.results) == 3
    assert run.failure_result is None

    assert tuple(result.event.sequence_number for result in run.results) == (1, 2, 3)

    assert tuple(result.reroute_acceptance_fraction for result in run.results) == pytest.approx(
        (1.0, 0.75, 0.0)
    )


def test_run_carries_state_between_events() -> None:
    """Each event must begin with the preceding output state."""
    run = run_full_reroute(build_shared_service_instance())

    assert run.results[0].state_before.processed_event_count == 0
    assert run.results[0].state_after == run.results[1].state_before
    assert run.results[1].state_after == run.results[2].state_before
    assert run.results[2].state_after == run.final_state

    assert run.final_state.accepted_demand_ids == (
        "K001",
        "K002",
    )
    assert run.final_state.rejected_demand_ids == ("K003",)


def test_single_route_run_matches_sequential_dca() -> None:
    """Without route alternatives, both mechanisms must agree."""
    instance = build_shared_service_instance()

    full_reroute = run_full_reroute(instance)
    sequential = run_sequential_dca(instance)

    assert tuple(
        result.reroute_acceptance_fraction for result in full_reroute.results
    ) == pytest.approx(tuple(result.acceptance_fraction for result in sequential.results))

    assert full_reroute.total_revenue == pytest.approx(160.0)
    assert full_reroute.ordinary_total_revenue == pytest.approx(160.0)
    assert full_reroute.accepted_volume == pytest.approx(10.0)
    assert full_reroute.acceptance_improvement_count == 0


def test_run_stops_at_first_infeasible_regular_request() -> None:
    """Mandatory old and current cargo may make the joint model infeasible."""
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

    run = run_full_reroute(instance)

    assert not run.completed
    assert len(run.results) == 2
    assert run.processed_event_count == 1

    assert run.final_state.processed_event_count == 1
    assert run.final_state.accepted_demand_ids == ("K001",)

    failure = run.failure_result

    assert failure is not None
    assert failure.event.demand_id == "K002"
    assert not failure.reroute_solution.is_solved
    assert failure.transition is None
    assert failure.state_after == failure.state_before


def test_complete_run_is_deterministic() -> None:
    """Repeated Full-Reroute runs must produce identical results."""
    instance = build_shared_service_instance()

    first = run_full_reroute(instance)
    second = run_full_reroute(instance)

    assert first == second
