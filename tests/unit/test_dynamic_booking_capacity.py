"""Tests for bookings after water-adjusted disruption recovery."""

import pytest

from barge_rerouting.config import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    NetworkConfig,
    SolverConfig,
)
from barge_rerouting.disruption import (
    RecoveryOperationalState,
    ServiceStatusUpdateEvent,
    apply_truck_recourse_solution,
    build_actual_bookable_capacity_snapshot,
    build_actual_capacity_profile,
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
    build_recovery_capacity_snapshot,
    build_recovery_fragment_network_snapshot,
    build_recovery_fragment_snapshot,
    build_truck_recourse_model,
    solve_truck_recourse_model,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    ScheduledTransportLeg,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def build_instance():
    """Build one committed request followed by a later spot request."""
    config = ExperimentConfig(
        experiment_name="phase10-dynamic-booking-test",
        random_seed=10,
        network=NetworkConfig(
            terminals=("A", "B", "C"),
            time_periods=(0, 1, 2, 3, 4),
            transport_legs=(
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="A",
                    destination="B",
                    departure_time=1,
                    arrival_time=2,
                    capacity=10,
                ),
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="B",
                    destination="C",
                    departure_time=2,
                    arrival_time=3,
                    capacity=10,
                ),
            ),
        ),
        demand_generation=DemandGenerationConfig(
            number_of_demands=2,
            minimum_volume=1,
            maximum_volume=10,
            minimum_fare_per_teu=10,
            maximum_fare_per_teu=100,
            minimum_reservation_time=0,
            maximum_reservation_time=1,
            minimum_availability_lag=0,
            maximum_availability_lag=0,
            minimum_due_slack=2,
            maximum_due_slack=3,
            customer_mix=CustomerMix(
                regular_probability=0.5,
                partially_spot_probability=0.0,
                fully_spot_probability=0.5,
            ),
        ),
        solver=SolverConfig(
            time_limit_seconds=30,
            relative_mip_gap=0.0,
            log_output=False,
        ),
    )

    return assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "K1",
                10,
                "A",
                "C",
                0,
                0,
                3,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K2",
                1,
                "A",
                "C",
                1,
                1,
                3,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )


def build_status_then_booking_example():
    """Recover K1 at t=1 immediately before booking K2."""
    instance = build_instance()
    timeline = build_booking_timeline(instance)

    state = RollingBookingState.empty(instance)

    first_event = timeline.event_at_sequence(1)

    first_artifacts = build_sequential_booking_model(
        instance,
        state,
        first_event,
    )
    first_solution = solve_sequential_booking_model(first_artifacts)

    assert first_solution.is_solved
    assert first_solution.acceptance_fraction == pytest.approx(1.0)

    state = apply_sequential_booking_solution(
        first_artifacts,
        first_solution,
    )

    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    ordinary = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    status_event = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=1,
        valid_from=1,
        valid_until=3,
        water_level_factor=0.7,
    )

    actual = build_actual_capacity_profile(
        instance,
        physical_time=1,
        status_updates=(status_event,),
    )

    recovery = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary,
        status_event,
    )

    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary,
        actual,
        recovery,
    )

    recovery_networks = build_recovery_fragment_network_snapshot(
        instance,
        recovery,
        recovery_capacity,
    )

    recovery_artifacts = build_truck_recourse_model(
        instance,
        recovery,
        recovery_capacity,
        recovery_networks,
        truck_penalty_per_teu_by_demand={
            "K1": 25.0,
        },
    )

    recovery_solution = solve_truck_recourse_model(recovery_artifacts)

    assert recovery_solution.is_solved
    assert recovery_solution.total_truck_volume == pytest.approx(3.0)

    operational_before = RecoveryOperationalState.empty(state)

    transition = apply_truck_recourse_solution(
        recovery_artifacts,
        recovery_solution,
        operational_before,
    )

    operational_capacity = build_operational_transport_capacity_snapshot(
        instance,
        transition.state_after,
        physical_time=1,
    )

    actual_bookable = build_actual_bookable_capacity_snapshot(
        instance,
        operational_capacity,
        actual,
    )

    current_event = timeline.event_at_sequence(2)

    return {
        "instance": instance,
        "current_event": current_event,
        "transition": transition,
        "actual": actual,
        "operational_capacity": operational_capacity,
        "actual_bookable": actual_bookable,
        "recovery_artifacts": recovery_artifacts,
    }


def test_actual_residual_is_zero_not_nominal_three() -> None:
    """Seven recovered TEU exactly fill reduced seven-TEU capacity."""
    example = build_status_then_booking_example()

    try:
        nominal_capacity = example["operational_capacity"]
        actual_capacity = example["actual_bookable"]

        bookable_arcs = tuple(state for state in nominal_capacity.arc_states if state.is_bookable)

        assert len(bookable_arcs) == 2

        for state in bookable_arcs:
            assert state.future_reserved_volume == pytest.approx(7.0)
            assert state.bookable_residual_capacity == pytest.approx(3.0)
            assert actual_capacity.bookable_capacity_for(state.arc_id) == pytest.approx(0.0)
    finally:
        example["recovery_artifacts"].model.end()


def test_booking_uses_actual_not_nominal_residual() -> None:
    """K2 must be rejected because reduced capacity is already full."""
    example = build_status_then_booking_example()

    try:
        instance = example["instance"]
        event = example["current_event"]
        operational_state = example["transition"].state_after

        nominal_artifacts = build_sequential_booking_model(
            instance,
            operational_state.booking_state,
            event,
            capacity_snapshot=example["operational_capacity"],
        )
        nominal_solution = solve_sequential_booking_model(nominal_artifacts)

        assert nominal_solution.is_solved
        assert nominal_solution.acceptance_fraction == pytest.approx(1.0)

        actual_artifacts = build_sequential_booking_model(
            instance,
            operational_state.booking_state,
            event,
            residual_capacity_overrides=(
                example["actual_bookable"].as_residual_capacity_overrides()
            ),
        )
        actual_solution = solve_sequential_booking_model(actual_artifacts)

        assert actual_solution.is_solved
        assert actual_solution.acceptance_fraction == pytest.approx(0.0)
    finally:
        example["recovery_artifacts"].model.end()


def test_booking_advancement_preserves_recovery_overlay() -> None:
    """Processing K2 must not erase K1's recovery history."""
    example = build_status_then_booking_example()

    try:
        instance = example["instance"]
        event = example["current_event"]
        before = example["transition"].state_after

        artifacts = build_sequential_booking_model(
            instance,
            before.booking_state,
            event,
            residual_capacity_overrides=(
                example["actual_bookable"].as_residual_capacity_overrides()
            ),
        )
        solution = solve_sequential_booking_model(artifacts)

        booking_after = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

        after = before.with_booking_state(booking_after)

        assert after.booking_state.processed_event_count == 2
        assert after.booking_state.rejected_demand_ids == ("K2",)

        assert after.recovery_event_ids == before.recovery_event_ids
        assert after.total_truck_volume == pytest.approx(3.0)
        assert after.total_truck_penalty == pytest.approx(75.0)

        snapshot = build_operational_execution_snapshot(
            instance,
            after,
            physical_time=1,
        )

        k1 = snapshot.demand_state_for("K1")

        assert k1.remaining_volume == pytest.approx(7.0)
        assert k1.delivered_truck_volume == pytest.approx(3.0)
    finally:
        example["recovery_artifacts"].model.end()
