"""Tests for persistent booking commitments and residual capacity."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
    commitment_from_dca_solution,
    validate_commitment_against_instance,
)


def build_controlled_solution():
    """Build and solve the known three-demand shared-capacity example."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    instance = assemble_experiment_instance(
        config,
        demands=(
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
        ),
    )

    solution = solve_dca_model(build_dca_model(instance))

    return instance, solution


def transport_arc_id(instance: ExperimentInstance) -> str:
    """Return the shared S6 transport arc identifier."""
    return next(arc.arc_id for arc in instance.arcs if arc.service_id == "S6")


def test_accepted_solution_creates_valid_persistent_commitment() -> None:
    """A positive booking decision must preserve its complete flow plan."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)
    event = timeline.event_for_demand("P001")

    commitment = commitment_from_dca_solution(
        instance,
        event,
        solution,
    )

    assert commitment is not None
    assert commitment.acceptance_fraction == pytest.approx(1.0)
    assert commitment.accepted_volume == pytest.approx(6.0)

    arc_id = transport_arc_id(instance)
    network_index = instance.network_index_for("P001")

    assert commitment.planned_volume_on(arc_id) == pytest.approx(6.0)
    assert commitment.planned_volume_on(network_index.sink_arc_ids[0]) == pytest.approx(6.0)

    report = validate_commitment_against_instance(
        instance,
        commitment,
    )

    assert report.is_valid
    assert report.violations == ()


def test_rejected_solution_creates_no_commitment() -> None:
    """A zero acceptance decision is stored as rejection rather than commitment."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)
    event = timeline.event_for_demand("F001")

    commitment = commitment_from_dca_solution(
        instance,
        event,
        solution,
    )

    assert commitment is None


def test_booking_state_records_decisions_immutably_in_sequence() -> None:
    """Each advance must return a new persistent state."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)

    state = RollingBookingState.empty(instance)
    original_state = state

    for event in timeline.events:
        commitment = commitment_from_dca_solution(
            instance,
            event,
            solution,
        )
        state = state.advance(
            instance,
            event=event,
            commitment=commitment,
        )

    assert original_state.processed_event_count == 0
    assert state.processed_event_count == 3
    assert state.accepted_demand_ids == ("P001", "R001")
    assert state.rejected_demand_ids == ("F001",)


def test_commitments_reserve_shared_transport_capacity() -> None:
    """Accepted plans must reduce capacity available to later bookings."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)
    arc_id = transport_arc_id(instance)

    for event in timeline.events:
        commitment = commitment_from_dca_solution(
            instance,
            event,
            solution,
        )
        state = state.advance(
            instance,
            event=event,
            commitment=commitment,
        )

    assert state.reserved_transport_volume(
        instance,
        arc_id,
    ) == pytest.approx(10.0)

    assert state.residual_transport_capacity(
        instance,
        arc_id,
    ) == pytest.approx(0.0)


def test_same_time_booking_events_do_not_imply_execution() -> None:
    """Sequential equal-time bookings create plans but do not move cargo."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    assert {event.decision_time for event in timeline.events} == {0}

    for event in timeline.events:
        commitment = commitment_from_dca_solution(
            instance,
            event,
            solution,
        )
        state = state.advance(
            instance,
            event=event,
            commitment=commitment,
        )

    assert all(commitment.decision_time == 0 for commitment in state.commitments)
    assert all(commitment.planned_arc_flows for commitment in state.commitments)


def test_state_rejects_out_of_order_booking_event() -> None:
    """Sequential state cannot skip earlier booking events."""
    instance, solution = build_controlled_solution()
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    second_event = timeline.event_at_sequence(2)
    commitment = commitment_from_dca_solution(
        instance,
        second_event,
        solution,
    )

    with pytest.raises(ValueError, match="sequence order"):
        state.advance(
            instance,
            event=second_event,
            commitment=commitment,
        )
