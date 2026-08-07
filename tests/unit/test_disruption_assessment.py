"""Tests for detection of actual-capacity overload."""

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
    build_disruption_assessment,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    ScheduledTransportLeg,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.rolling_horizon.execution import (
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.time_aware_run import (
    run_time_aware_sequential_dca,
)


def build_instance():
    """Build one mandatory ten-TEU corridor demand."""
    config = ExperimentConfig(
        experiment_name="phase10-disruption-test",
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
    """Accept and commit the mandatory demand."""
    run = run_time_aware_sequential_dca(instance)

    assert run.completed
    assert run.accepted_volume == 10

    return run.final_state


def transport_arc(
    instance,
    *,
    departure_time: int,
):
    """Return one corridor transport arc."""
    matches = tuple(
        arc for arc in instance.arcs if (arc.is_transport and arc.tail[1] == departure_time)
    )

    assert len(matches) == 1
    return matches[0]


def test_nominal_profile_keeps_plan_feasible() -> None:
    """The original ten-TEU plan fits nominal capacity."""
    instance = build_instance()
    state = committed_state(instance)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
    )

    assessment = build_disruption_assessment(
        instance,
        execution,
        profile,
    )

    assert assessment.is_feasible
    assert assessment.disrupted_arc_ids == ()
    assert assessment.affected_demand_ids == ()
    assert assessment.maximum_arc_overload == 0


def test_forced_reduction_detects_three_teu_overload() -> None:
    """A 0.7 factor makes the ten-TEU plan infeasible."""
    instance = build_instance()
    state = committed_state(instance)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    update = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=3,
        water_level_factor=0.7,
        affected_service_ids=("S1",),
    )
    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
        status_updates=(update,),
    )

    assessment = build_disruption_assessment(
        instance,
        execution,
        profile,
    )

    assert not assessment.is_feasible
    assert len(assessment.disrupted_arc_ids) == 2
    assert assessment.affected_demand_ids == ("K1",)
    assert assessment.affected_path_ids == ("K1::path::0001",)
    assert assessment.maximum_arc_overload == 3

    for arc_id in assessment.disrupted_arc_ids:
        disrupted = assessment.state_for(arc_id)

        assert disrupted.nominal_capacity == 10
        assert disrupted.actual_capacity == 7
        assert disrupted.committed_volume == 10
        assert disrupted.actual_bookable_capacity == 0
        assert disrupted.overload_volume == 3


def test_overload_is_not_summed_as_truck_volume() -> None:
    """One path may overload several service legs."""
    instance = build_instance()
    state = committed_state(instance)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=0,
                valid_from=0,
                valid_until=3,
                water_level_factor=0.7,
            ),
        ),
    )

    assessment = build_disruption_assessment(
        instance,
        execution,
        profile,
    )

    summed_arc_overload = sum(
        assessment.state_for(arc_id).overload_volume for arc_id in assessment.disrupted_arc_ids
    )

    assert summed_arc_overload == 6
    assert assessment.maximum_arc_overload == 3
    assert assessment.affected_path_ids == ("K1::path::0001",)


def test_completed_leg_is_not_reassessed() -> None:
    """A completed first leg remains historically fixed."""
    instance = build_instance()
    state = committed_state(instance)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=2,
    )
    profile = build_actual_capacity_profile(
        instance,
        physical_time=2,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=2,
                valid_from=2,
                valid_until=3,
                water_level_factor=0.7,
            ),
        ),
    )

    assessment = build_disruption_assessment(
        instance,
        execution,
        profile,
    )

    completed_arc = transport_arc(
        instance,
        departure_time=1,
    )
    future_arc = transport_arc(
        instance,
        departure_time=2,
    )

    assert completed_arc.arc_id not in tuple(state.arc_id for state in assessment.arc_states)
    assert assessment.disrupted_arc_ids == (future_arc.arc_id,)
    assert assessment.maximum_arc_overload == 3


def test_profile_and_execution_times_must_match() -> None:
    """Capacity and execution snapshots require one epoch."""
    import pytest

    instance = build_instance()
    state = committed_state(instance)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    profile = build_actual_capacity_profile(
        instance,
        physical_time=1,
    )

    with pytest.raises(
        ValueError,
        match="same physical time",
    ):
        build_disruption_assessment(
            instance,
            execution,
            profile,
        )
