"""Tests for physical-time execution of accepted commitments."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    accepted_demand_state_at_time,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    commitment_from_sequential_solution,
    decompose_commitment_paths,
    solve_sequential_booking_model,
)


def build_two_leg_commitment():
    """Build one accepted A-to-C commitment using S1 then S2."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    quiet_config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(
        quiet_config,
        demands=(
            Demand(
                demand_id="KEXEC",
                volume=4.0,
                origin="A",
                destination="C",
                reservation_time=0,
                availability_time=0,
                due_time=2,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10.0,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)
    event = timeline.event_at_sequence(1)

    artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
    )
    solution = solve_sequential_booking_model(artifacts)
    commitment = commitment_from_sequential_solution(
        artifacts,
        solution,
    )

    assert commitment is not None

    state = apply_sequential_booking_solution(
        artifacts,
        solution,
    )

    return instance, state, commitment


def service_arc_id(instance, service_id: str) -> str:
    """Return one scheduled service arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def test_commitment_decomposes_into_one_two_leg_path() -> None:
    """The controlled flow must produce one deterministic path."""
    instance, _, commitment = build_two_leg_commitment()

    paths = decompose_commitment_paths(
        instance,
        commitment,
    )

    assert len(paths) == 1

    path = paths[0]

    assert path.volume == pytest.approx(4.0)
    assert path.physical_arc_ids == (
        service_arc_id(instance, "S1"),
        service_arc_id(instance, "S2"),
    )
    assert path.delivery_arc_id.startswith("delivery::KEXEC::C@2")


def test_time_zero_keeps_fragment_at_origin() -> None:
    """No arc arriving after time zero has executed yet."""
    instance, _, commitment = build_two_leg_commitment()

    demand_state, _ = accepted_demand_state_at_time(
        instance,
        commitment,
        physical_time=0,
    )

    assert demand_state.delivered_barge_volume == pytest.approx(0.0)
    assert demand_state.remaining_volume == pytest.approx(4.0)
    assert len(demand_state.fragments) == 1

    fragment = demand_state.fragments[0]

    assert fragment.current_node == ("A", 0)
    assert fragment.executed_arc_ids == ()


def test_time_one_executes_first_service_and_moves_fragment() -> None:
    """S1 has arrived by time one while S2 remains future."""
    instance, _, commitment = build_two_leg_commitment()

    demand_state, _ = accepted_demand_state_at_time(
        instance,
        commitment,
        physical_time=1,
    )

    assert demand_state.delivered_barge_volume == pytest.approx(0.0)
    assert demand_state.remaining_volume == pytest.approx(4.0)

    fragment = demand_state.fragments[0]

    assert fragment.current_node == ("B", 1)
    assert fragment.executed_arc_ids == (service_arc_id(instance, "S1"),)


def test_time_two_completes_barge_delivery() -> None:
    """The destination delivery arc completes when C at time two is reached."""
    instance, _, commitment = build_two_leg_commitment()

    demand_state, _ = accepted_demand_state_at_time(
        instance,
        commitment,
        physical_time=2,
    )

    assert demand_state.is_complete
    assert demand_state.fragments == ()
    assert demand_state.remaining_volume == pytest.approx(0.0)
    assert demand_state.delivered_barge_volume == pytest.approx(4.0)


def test_snapshot_separates_executed_and_unexecuted_transport_volume() -> None:
    """Time advancement must move reservation volume between categories."""
    instance, booking_state, _ = build_two_leg_commitment()

    s1 = service_arc_id(instance, "S1")
    s2 = service_arc_id(instance, "S2")

    time_zero = build_execution_snapshot(
        instance,
        booking_state,
        physical_time=0,
    )
    time_one = build_execution_snapshot(
        instance,
        booking_state,
        physical_time=1,
    )
    time_two = build_execution_snapshot(
        instance,
        booking_state,
        physical_time=2,
    )

    assert time_zero.executed_transport_volume(
        instance,
        s1,
    ) == pytest.approx(0.0)
    assert time_zero.unexecuted_transport_volume(
        instance,
        s1,
    ) == pytest.approx(4.0)
    assert time_zero.unexecuted_transport_volume(
        instance,
        s2,
    ) == pytest.approx(4.0)

    assert time_one.executed_transport_volume(
        instance,
        s1,
    ) == pytest.approx(4.0)
    assert time_one.unexecuted_transport_volume(
        instance,
        s1,
    ) == pytest.approx(0.0)
    assert time_one.executed_transport_volume(
        instance,
        s2,
    ) == pytest.approx(0.0)
    assert time_one.unexecuted_transport_volume(
        instance,
        s2,
    ) == pytest.approx(4.0)

    assert time_two.executed_transport_volume(
        instance,
        s1,
    ) == pytest.approx(4.0)
    assert time_two.executed_transport_volume(
        instance,
        s2,
    ) == pytest.approx(4.0)
    assert time_two.unexecuted_transport_volume(
        instance,
        s2,
    ) == pytest.approx(0.0)


def test_equal_time_booking_does_not_execute_future_service() -> None:
    """Booking at time zero reserves routes but does not move cargo."""
    instance, booking_state, _ = build_two_leg_commitment()

    snapshot = build_execution_snapshot(
        instance,
        booking_state,
        physical_time=0,
    )

    assert snapshot.active_fragment_count == 1
    assert snapshot.delivered_barge_volume == pytest.approx(0.0)

    for service_id in ("S1", "S2"):
        arc_id = service_arc_id(instance, service_id)

        assert snapshot.executed_transport_volume(
            instance,
            arc_id,
        ) == pytest.approx(0.0)


def test_volume_accounting_holds_at_every_physical_time() -> None:
    """Accepted volume must remain fully accounted for during execution."""
    instance, booking_state, commitment = build_two_leg_commitment()

    for physical_time in (0, 1, 2):
        snapshot = build_execution_snapshot(
            instance,
            booking_state,
            physical_time=physical_time,
        )
        demand_state = snapshot.demand_state_for("KEXEC")

        assert (
            demand_state.remaining_volume
            + demand_state.delivered_barge_volume
            + demand_state.delivered_truck_volume
        ) == pytest.approx(commitment.accepted_volume)
