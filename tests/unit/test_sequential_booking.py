"""Tests for actual sequential DCA booking decisions."""

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
    commitment_from_sequential_solution,
    solve_sequential_booking_model,
)


def build_sequential_instance():
    """Create a known three-request sequential booking instance."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    demands = (
        Demand(
            demand_id="K001",
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
            demand_id="K002",
            volume=8.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=20.0,
        ),
        Demand(
            demand_id="K003",
            volume=6.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.FULLY_SPOT,
            fare_per_teu=100.0,
        ),
    )

    return assemble_experiment_instance(
        config,
        demands=demands,
    )


def s6_arc_id(instance) -> str:
    """Return the shared S6 transport arc."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == "S6"))


def test_first_booking_uses_full_nominal_capacity() -> None:
    """No capacity is reserved before the first booking event."""
    instance = build_sequential_instance()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    artifacts = build_sequential_booking_model(
        instance,
        state,
        timeline.event_at_sequence(1),
    )

    assert artifacts.residual_capacities[s6_arc_id(instance)] == pytest.approx(10.0)


def test_sequential_decisions_use_prior_residual_capacity() -> None:
    """Each accepted request reduces the next request's capacity."""
    instance = build_sequential_instance()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)
    solutions = []

    for event in timeline.events:
        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)
        solutions.append(solution)

        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

    assert solutions[0].acceptance_fraction == pytest.approx(1.0)
    assert solutions[1].acceptance_fraction == pytest.approx(0.75)
    assert solutions[2].acceptance_fraction == pytest.approx(0.0)

    assert state.accepted_demand_ids == ("K001", "K002")
    assert state.rejected_demand_ids == ("K003",)

    assert state.reserved_transport_volume(
        instance,
        s6_arc_id(instance),
    ) == pytest.approx(10.0)

    assert state.residual_transport_capacity(
        instance,
        s6_arc_id(instance),
    ) == pytest.approx(0.0)


def test_partially_spot_commitment_stores_accepted_volume() -> None:
    """A fractional acceptance must persist only the accepted volume."""
    instance = build_sequential_instance()
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

    second_artifacts = build_sequential_booking_model(
        instance,
        state,
        timeline.event_at_sequence(2),
    )
    second_solution = solve_sequential_booking_model(second_artifacts)
    commitment = commitment_from_sequential_solution(
        second_artifacts,
        second_solution,
    )

    assert commitment is not None
    assert commitment.acceptance_fraction == pytest.approx(0.75)
    assert commitment.accepted_volume == pytest.approx(6.0)
    assert commitment.planned_volume_on(s6_arc_id(instance)) == pytest.approx(6.0)


def test_fully_spot_request_is_rejected_when_it_cannot_fit() -> None:
    """Binary demand cannot use the zero residual capacity fractionally."""
    instance = build_sequential_instance()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    for event in timeline.events[:2]:
        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)
        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

    third_artifacts = build_sequential_booking_model(
        instance,
        state,
        timeline.event_at_sequence(3),
    )
    third_solution = solve_sequential_booking_model(third_artifacts)

    assert third_solution.is_solved
    assert third_solution.acceptance_fraction == pytest.approx(0.0)
    assert (
        commitment_from_sequential_solution(
            third_artifacts,
            third_solution,
        )
        is None
    )


def test_model_rejects_out_of_order_event() -> None:
    """The sequential solver cannot skip an earlier request."""
    instance = build_sequential_instance()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    with pytest.raises(ValueError, match="next unprocessed"):
        build_sequential_booking_model(
            instance,
            state,
            timeline.event_at_sequence(2),
        )
