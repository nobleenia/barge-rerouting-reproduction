"""Tests for execution after persisted truck/barge recovery."""

import pytest
from test_truck_recourse_model import (
    build_recovery_example,
)

from barge_rerouting.disruption import (
    RecoveryOperationalState,
    apply_truck_recourse_solution,
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon import (
    build_execution_snapshot,
)


def build_transition(
    water_level_factor: float = 0.7,
):
    """Build and persist the controlled recovery example."""
    example = build_recovery_example(water_level_factor)

    before = RecoveryOperationalState.empty(example["state"])

    transition = apply_truck_recourse_solution(
        example["artifacts"],
        example["solution"],
        before,
    )

    return example, transition


def test_legacy_execution_remains_unchanged() -> None:
    """The original booking view still contains ten barge TEU."""
    example, _ = build_transition()

    try:
        legacy = build_execution_snapshot(
            example["instance"],
            example["state"],
            physical_time=0,
        )

        demand_state = legacy.demand_state_for("K1")

        assert demand_state.remaining_volume == pytest.approx(10.0)
        assert demand_state.delivered_truck_volume == pytest.approx(0.0)
    finally:
        example["artifacts"].model.end()


def test_operational_time_zero_is_seven_barge_three_truck() -> None:
    """Recovered execution removes trucked cargo from barge."""
    example, transition = build_transition()

    try:
        snapshot = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=0,
        )

        demand_state = snapshot.demand_state_for("K1")

        assert demand_state.accepted_volume == pytest.approx(10.0)
        assert demand_state.remaining_volume == pytest.approx(7.0)
        assert demand_state.delivered_barge_volume == pytest.approx(0.0)
        assert demand_state.delivered_truck_volume == pytest.approx(3.0)

        assert len(demand_state.fragments) == 1
        assert demand_state.fragments[0].volume == pytest.approx(7.0)
        assert demand_state.fragments[0].current_node == ("A", 0)
    finally:
        example["artifacts"].model.end()


def test_operational_future_reservation_is_seven() -> None:
    """Future barge capacity follows the recovered plan."""
    example, transition = build_transition()

    try:
        capacity = build_operational_transport_capacity_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=0,
        )

        transport_states = tuple(
            state for state in capacity.arc_states if state.future_reserved_volume > 0.0
        )

        assert len(transport_states) == 2

        for state in transport_states:
            assert state.nominal_capacity == pytest.approx(10.0)
            assert state.future_reserved_volume == pytest.approx(7.0)
            assert state.bookable_residual_capacity == pytest.approx(3.0)
    finally:
        example["artifacts"].model.end()


def test_first_recovered_leg_executes_normally() -> None:
    """Seven TEU move to B when the first service arrives."""
    example, transition = build_transition()

    try:
        snapshot = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=2,
        )

        demand_state = snapshot.demand_state_for("K1")

        assert demand_state.remaining_volume == pytest.approx(7.0)
        assert demand_state.delivered_truck_volume == pytest.approx(3.0)

        fragment = demand_state.fragments[0]

        assert fragment.volume == pytest.approx(7.0)
        assert fragment.current_node == ("B", 2)

        capacity = build_operational_transport_capacity_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=2,
        )

        completed = tuple(state for state in capacity.arc_states if state.completed_volume > 0.0)
        future = tuple(state for state in capacity.arc_states if state.future_reserved_volume > 0.0)

        assert len(completed) == 1
        assert completed[0].completed_volume == pytest.approx(7.0)

        assert len(future) == 1
        assert future[0].future_reserved_volume == pytest.approx(7.0)
    finally:
        example["artifacts"].model.end()


def test_final_accounting_is_seven_barge_three_truck() -> None:
    """All ten accepted TEU remain accounted for at completion."""
    example, transition = build_transition()

    try:
        snapshot = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=3,
        )

        demand_state = snapshot.demand_state_for("K1")

        assert demand_state.is_complete
        assert demand_state.fragments == ()
        assert demand_state.remaining_volume == pytest.approx(0.0)
        assert demand_state.delivered_barge_volume == pytest.approx(7.0)
        assert demand_state.delivered_truck_volume == pytest.approx(3.0)

        assert (
            demand_state.delivered_barge_volume + demand_state.delivered_truck_volume
            == pytest.approx(demand_state.accepted_volume)
        )
    finally:
        example["artifacts"].model.end()


def test_nominal_recovery_remains_ten_barge_zero_truck() -> None:
    """The overlay is neutral when water capacity is unchanged."""
    example, transition = build_transition(1.0)

    try:
        snapshot = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=0,
        )

        demand_state = snapshot.demand_state_for("K1")

        assert demand_state.remaining_volume == pytest.approx(10.0)
        assert demand_state.delivered_truck_volume == pytest.approx(0.0)

        capacity = build_operational_transport_capacity_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=0,
        )

        positive = tuple(
            state for state in capacity.arc_states if state.future_reserved_volume > 0.0
        )

        assert len(positive) == 2

        for state in positive:
            assert state.future_reserved_volume == pytest.approx(10.0)
    finally:
        example["artifacts"].model.end()
