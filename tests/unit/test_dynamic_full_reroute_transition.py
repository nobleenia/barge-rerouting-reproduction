"""Tests for operational persistence of dynamic Full-Reroute."""

import pytest
from test_dynamic_booking_capacity import (
    build_status_then_booking_example,
)

from barge_rerouting.disruption import (
    apply_dynamic_full_reroute_solution,
    build_dynamic_full_reroute_model,
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
    build_recovery_capacity_snapshot,
    build_recovery_fragment_network_snapshot,
    build_recovery_fragment_snapshot,
    solve_dynamic_full_reroute_model,
)


def build_operational_fr_booking():
    """Build the true post-status FR booking context."""
    example = build_status_then_booking_example()

    instance = example["instance"]
    state_before = example["transition"].state_after
    event = example["current_event"]

    execution = build_operational_execution_snapshot(
        instance,
        state_before,
        physical_time=event.decision_time,
    )

    ordinary_capacity = build_operational_transport_capacity_snapshot(
        instance,
        state_before,
        physical_time=event.decision_time,
    )

    fragments = build_recovery_fragment_snapshot(
        instance,
        state_before.booking_state,
        execution,
        ordinary_capacity,
        event,
    )

    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary_capacity,
        example["actual"],
        fragments,
    )

    networks = build_recovery_fragment_network_snapshot(
        instance,
        fragments,
        recovery_capacity,
    )

    artifacts = build_dynamic_full_reroute_model(
        instance,
        state_before.booking_state,
        event,
        recovery_capacity,
        networks,
        truck_penalty_per_teu_by_demand={
            "K1": 25.0,
            "K2": 1000.0,
        },
        allow_current_truck=False,
    )

    solution = solve_dynamic_full_reroute_model(artifacts)

    return (
        example,
        state_before,
        fragments,
        artifacts,
        solution,
    )


def test_fr_booking_optimizes_only_remaining_seven_teu() -> None:
    """Already-trucked volume never re-enters the booking solve."""
    (
        example,
        state_before,
        fragments,
        artifacts,
        solution,
    ) = build_operational_fr_booking()

    try:
        assert state_before.total_truck_volume == pytest.approx(3.0)
        assert fragments.total_remaining_volume == pytest.approx(7.0)

        assert solution.is_solved
        assert solution.acceptance_fraction == pytest.approx(1.0)

        # To fit K2, only one of K1's remaining seven TEU
        # needs to move to truck.
        assert solution.prior_truck_volume == pytest.approx(1.0)
        assert solution.current_truck_volume == pytest.approx(0.0)

        # K2 revenue 100 - one incremental K1 truck TEU * 25.
        assert solution.objective_value == pytest.approx(75.0)
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_fr_transition_accumulates_four_not_seven_truck_teu() -> None:
    """Truck history is incremental across recovery generations."""
    (
        example,
        state_before,
        _,
        artifacts,
        solution,
    ) = build_operational_fr_booking()

    try:
        transition = apply_dynamic_full_reroute_solution(
            artifacts,
            solution,
            state_before,
        )

        assert transition.additional_truck_volume == pytest.approx(1.0)
        assert transition.additional_truck_penalty == pytest.approx(25.0)

        assert transition.state_after.total_truck_volume == pytest.approx(4.0)
        assert transition.state_after.total_truck_penalty == pytest.approx(100.0)

        assert transition.state_after.recovery_event_count == 2

        assert transition.state_after.booking_state.accepted_demand_ids == ("K1", "K2")
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_fr_transition_reconstructs_six_plus_four_and_new_k2() -> None:
    """Operational execution reflects latest FR generation."""
    (
        example,
        state_before,
        _,
        artifacts,
        solution,
    ) = build_operational_fr_booking()

    try:
        transition = apply_dynamic_full_reroute_solution(
            artifacts,
            solution,
            state_before,
        )

        execution = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=1,
        )

        k1 = execution.demand_state_for("K1")
        k2 = execution.demand_state_for("K2")

        assert k1.delivered_truck_volume == pytest.approx(4.0)
        assert k1.remaining_volume == pytest.approx(6.0)

        assert k2.delivered_truck_volume == pytest.approx(0.0)
        assert k2.remaining_volume == pytest.approx(1.0)

        capacity = build_operational_transport_capacity_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=1,
        )

        for state in capacity.arc_states:
            if state.is_bookable:
                assert state.future_reserved_volume == pytest.approx(7.0)
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_fr_transition_refuses_unrepresentable_current_truck() -> None:
    """Never hide a current truck transfer inside a barge commitment."""
    (
        example,
        state_before,
        _,
        artifacts,
        _,
    ) = build_operational_fr_booking()

    artifacts.model.end()

    instance = example["instance"]
    event = example["current_event"]

    execution = build_operational_execution_snapshot(
        instance,
        state_before,
        physical_time=event.decision_time,
    )
    ordinary = build_operational_transport_capacity_snapshot(
        instance,
        state_before,
        physical_time=event.decision_time,
    )
    fragments = build_recovery_fragment_snapshot(
        instance,
        state_before.booking_state,
        execution,
        ordinary,
        event,
    )
    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary,
        example["actual"],
        fragments,
    )
    networks = build_recovery_fragment_network_snapshot(
        instance,
        fragments,
        recovery_capacity,
    )

    current_truck_artifacts = build_dynamic_full_reroute_model(
        instance,
        state_before.booking_state,
        event,
        recovery_capacity,
        networks,
        truck_penalty_per_teu_by_demand={
            "K1": 1000.0,
            "K2": 1.0,
        },
        allow_current_truck=True,
    )

    try:
        solution = solve_dynamic_full_reroute_model(current_truck_artifacts)

        assert solution.is_solved
        assert solution.current_truck_volume == pytest.approx(1.0)

        with pytest.raises(
            ValueError,
            match="allow_current_truck=False",
        ):
            apply_dynamic_full_reroute_solution(
                current_truck_artifacts,
                solution,
                state_before,
            )
    finally:
        current_truck_artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_fr_repeated_recovery_preserves_nested_delivery_identity() -> None:
    """A second recovery must resolve the preceding fragment's sink."""
    (
        example,
        state_before,
        _,
        artifacts,
        solution,
    ) = build_operational_fr_booking()

    try:
        transition = apply_dynamic_full_reroute_solution(
            artifacts,
            solution,
            state_before,
        )

        execution = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=1,
        )

        k1_paths = tuple(path for path in execution.planned_paths if path.demand_id == "K1")

        assert k1_paths

        for path in k1_paths:
            assert path.path_id.count("::recovery::") == 2

        k1 = execution.demand_state_for("K1")

        assert k1.remaining_volume == pytest.approx(6.0)
        assert k1.delivered_truck_volume == pytest.approx(4.0)
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()
