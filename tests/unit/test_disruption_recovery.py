"""Tests for status-triggered recovery preparation."""

import pytest

from barge_rerouting.config import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    NetworkConfig,
    SolverConfig,
)
from barge_rerouting.disruption import (
    ServiceStatusUpdateEvent,
    build_actual_capacity_profile,
    build_recovery_capacity_snapshot,
    build_recovery_fragment_snapshot,
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
    build_execution_snapshot,
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.time_aware_run import (
    run_time_aware_sequential_dca,
)


def build_instance():
    """Build one ten-TEU mandatory corridor."""
    config = ExperimentConfig(
        experiment_name="phase10-recovery-test",
        random_seed=10,
        network=NetworkConfig(
            terminals=("A", "B", "C"),
            time_periods=(0, 1, 2, 3),
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
            number_of_demands=1,
            minimum_volume=10,
            maximum_volume=10,
            minimum_fare_per_teu=10,
            maximum_fare_per_teu=10,
            minimum_reservation_time=0,
            maximum_reservation_time=0,
            minimum_availability_lag=0,
            maximum_availability_lag=0,
            minimum_due_slack=3,
            maximum_due_slack=3,
            customer_mix=CustomerMix(
                regular_probability=1.0,
                partially_spot_probability=0.0,
                fully_spot_probability=0.0,
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
        ),
    )


def committed_state(instance):
    """Accept the mandatory demand under nominal capacity."""
    run = run_time_aware_sequential_dca(instance)

    assert run.completed
    assert run.accepted_volume == pytest.approx(10)

    return run.final_state


def test_status_recovery_releases_future_commitment() -> None:
    """The full unfinished reservation becomes recoverable."""
    instance = build_instance()
    state = committed_state(instance)

    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    ordinary = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    event = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=3,
        water_level_factor=0.7,
    )

    recovery = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary,
        event,
    )

    assert recovery.fragment_ids == ("K1::path::0001",)
    assert recovery.demand_ids == ("K1",)
    assert recovery.total_remaining_volume == pytest.approx(10)
    assert recovery.locked_fragment_ids == ()

    fragment = recovery.fragments[0]

    assert fragment.rerouting_source == ("A", 0)
    assert len(fragment.releasable_future_transport_arc_ids) == 2


def test_actual_recovery_capacity_is_seven() -> None:
    """A 0.7 water factor exposes seven TEU on each leg."""
    instance = build_instance()
    state = committed_state(instance)

    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    ordinary = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    event = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=3,
        water_level_factor=0.7,
    )

    actual = build_actual_capacity_profile(
        instance,
        physical_time=0,
        status_updates=(event,),
    )
    recovery = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary,
        event,
    )
    capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary,
        actual,
        recovery,
    )

    assert capacity.fixed_overload_arc_ids == ()

    for arc_state in capacity.arc_states:
        assert arc_state.nominal_capacity == pytest.approx(10)
        assert arc_state.actual_capacity == pytest.approx(7)
        assert arc_state.ordinary_reserved_volume == pytest.approx(10)
        assert arc_state.released_recovery_volume == pytest.approx(10)
        assert arc_state.fixed_outside_reserved_volume == pytest.approx(0)
        assert arc_state.recovery_available_capacity == pytest.approx(7)
        assert arc_state.fixed_overload_volume == pytest.approx(0)
        assert arc_state.released_fragment_ids == ("K1::path::0001",)


def test_same_time_departure_remains_recoverable() -> None:
    """A leg departing at the update epoch has not been locked yet."""
    instance = build_instance()
    state = committed_state(instance)

    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    ordinary = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    event = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=1,
        valid_from=1,
        valid_until=3,
        water_level_factor=0.7,
    )

    recovery = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary,
        event,
    )

    fragment = recovery.fragments[0]

    assert fragment.rerouting_source == ("A", 1)
    assert fragment.locked_in_transit_arc_id is None
    assert len(fragment.releasable_future_transport_arc_ids) == 2


def test_in_transit_movement_is_immutable() -> None:
    """A departed leg cannot be undone by a later forecast."""
    instance = build_instance()
    state = committed_state(instance)

    # There is no integer physical time strictly between 1 and 2
    # in this toy service. Instead verify the post-arrival state at 2:
    # the first movement is historical and only the second remains
    # recoverable.
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=2,
    )
    ordinary = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    event = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=2,
        valid_from=2,
        valid_until=3,
        water_level_factor=0.7,
    )

    recovery = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary,
        event,
    )

    fragment = recovery.fragments[0]

    assert fragment.rerouting_source == ("B", 2)
    completed_transport_arc_ids = tuple(
        arc_id for arc_id in fragment.completed_arc_ids if instance.arc_by_id(arc_id).is_transport
    )

    assert len(completed_transport_arc_ids) == 1
    assert fragment.locked_in_transit_arc_id is None
    assert len(fragment.releasable_future_transport_arc_ids) == 1
