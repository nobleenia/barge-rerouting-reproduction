"""Tests for physical-time-aware sequential DCA runs."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    run_time_aware_sequential_dca,
)


def quiet_config():
    """Load the toy configuration without solver logs."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled service arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def test_two_time_epoch_run_advances_execution() -> None:
    """A time-one event must see the time-zero service as completed."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "B",
                0,
                0,
                1,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                6,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.REGULAR,
                20,
            ),
        ),
    )

    run = run_time_aware_sequential_dca(instance)

    assert run.completed
    assert tuple(epoch.physical_time for epoch in run.epochs) == (0, 1)

    assert run.total_revenue == pytest.approx(160.0)
    assert run.accepted_volume == pytest.approx(10.0)

    time_one = run.epochs[1]

    first_demand_state = time_one.execution_before.demand_state_for("K001")

    assert first_demand_state.is_complete
    assert first_demand_state.delivered_barge_volume == pytest.approx(4.0)


def test_time_one_capacity_closes_s1_and_keeps_s2_open() -> None:
    """Past capacity cannot be reused while the current service remains open."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "B",
                0,
                0,
                1,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                6,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.REGULAR,
                20,
            ),
        ),
    )

    run = run_time_aware_sequential_dca(instance)
    time_one = run.epochs[1]

    s1_before = time_one.capacity_before.state_for(service_arc_id(instance, "S1"))
    s2_before = time_one.capacity_before.state_for(service_arc_id(instance, "S2"))
    s2_after = time_one.capacity_after.state_for(service_arc_id(instance, "S2"))

    assert s1_before.is_completed
    assert s1_before.bookable_residual_capacity == pytest.approx(0.0)

    assert s2_before.is_bookable
    assert s2_before.bookable_residual_capacity == pytest.approx(10.0)

    assert s2_after.future_reserved_volume == pytest.approx(6.0)
    assert s2_after.bookable_residual_capacity == pytest.approx(4.0)


def test_canonical_time_aware_run_preserves_known_failure() -> None:
    """Physical-time orchestration must reproduce the time-zero bottleneck."""
    instance = assemble_experiment_instance(quiet_config())

    run = run_time_aware_sequential_dca(instance)

    assert not run.completed
    assert len(run.epochs) == 1
    assert run.epochs[0].physical_time == 0

    failure = run.failure_result

    assert failure is not None
    assert failure.demand_id == "K0011"
    assert failure.solve_status == "infeasible"
    assert run.final_state.processed_event_count == 8
