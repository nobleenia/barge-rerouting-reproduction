"""Tests for residual-capacity booking diagnostics."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_sequential_booking_model,
    diagnose_booking_feasibility,
    run_sequential_dca,
    solve_sequential_booking_model,
)


def load_quiet_config():
    """Load the toy configuration with solver output disabled."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def test_diagnostic_detects_zero_capacity_shared_service() -> None:
    """A full early commitment must block the later regular request."""
    instance = assemble_experiment_instance(
        load_quiet_config(),
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

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    first_artifacts = build_sequential_booking_model(
        instance,
        state,
        timeline.event_at_sequence(1),
    )
    first_solution = solve_sequential_booking_model(first_artifacts)
    state = apply_sequential_booking_solution(
        first_artifacts,
        first_solution,
    )

    diagnostic = diagnose_booking_feasibility(
        instance,
        state,
        timeline.event_at_sequence(2),
    )

    assert not diagnostic.is_feasible
    assert diagnostic.maximum_routable_volume == pytest.approx(0.0)
    assert diagnostic.volume_shortfall == pytest.approx(1.0)
    assert diagnostic.bottleneck_arc_ids == ("transport::5::S6",)


def test_diagnostic_measures_partial_capacity_shortfall() -> None:
    """The diagnostic must quantify volume exceeding residual capacity."""
    instance = assemble_experiment_instance(
        load_quiet_config(),
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
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    first_artifacts = build_sequential_booking_model(
        instance,
        state,
        timeline.event_at_sequence(1),
    )
    first_solution = solve_sequential_booking_model(first_artifacts)
    state = apply_sequential_booking_solution(
        first_artifacts,
        first_solution,
    )

    diagnostic = diagnose_booking_feasibility(
        instance,
        state,
        timeline.event_at_sequence(2),
        required_volume=8.0,
    )

    assert not diagnostic.is_feasible
    assert diagnostic.maximum_routable_volume == pytest.approx(6.0)
    assert diagnostic.volume_shortfall == pytest.approx(2.0)
    assert diagnostic.bottleneck_arc_ids == ("transport::5::S6",)


def test_canonical_failure_is_caused_by_s2_residual_capacity() -> None:
    """The canonical K0011 failure must identify its exact cut arc."""
    instance = assemble_experiment_instance(load_quiet_config())
    run = run_sequential_dca(instance)

    failure = run.failure_result

    assert failure is not None
    assert failure.demand_id == "K0011"

    diagnostic = diagnose_booking_feasibility(
        instance,
        run.final_state,
        failure.event,
    )

    assert not diagnostic.is_feasible
    assert diagnostic.required_volume == pytest.approx(2.0)
    assert diagnostic.maximum_routable_volume == pytest.approx(0.0)
    assert diagnostic.volume_shortfall == pytest.approx(2.0)
    assert diagnostic.bottleneck_arc_ids == ("transport::1::S2",)

    bottleneck = diagnostic.bottleneck_arcs[0]

    assert bottleneck.service_id == "S2"
    assert bottleneck.residual_capacity == pytest.approx(0.0)
    assert bottleneck.nominal_capacity == pytest.approx(10.0)
