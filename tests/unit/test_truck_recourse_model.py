"""Tests for explicit truck recourse after capacity reduction."""

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
    build_actual_capacity_profile,
    build_recovery_capacity_snapshot,
    build_recovery_fragment_network_snapshot,
    build_recovery_fragment_snapshot,
    build_truck_recourse_model,
    solve_truck_recourse_model,
    validate_truck_recourse_solution,
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
    """Build one mandatory ten-TEU corridor."""
    config = ExperimentConfig(
        experiment_name="phase10-truck-recourse-test",
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


def build_recovery_example(
    water_level_factor: float,
):
    """Create one committed fragment and its recovery model."""
    instance = build_instance()

    run = run_time_aware_sequential_dca(instance)

    assert run.completed
    assert run.accepted_volume == pytest.approx(10)

    state = run.final_state

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
        water_level_factor=water_level_factor,
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

    networks = build_recovery_fragment_network_snapshot(
        instance,
        recovery,
        capacity,
    )

    artifacts = build_truck_recourse_model(
        instance,
        recovery,
        capacity,
        networks,
        truck_penalty_per_teu_by_demand={
            "K1": 25.0,
        },
    )

    solution = solve_truck_recourse_model(artifacts)

    return {
        "instance": instance,
        "recovery": recovery,
        "capacity": capacity,
        "networks": networks,
        "artifacts": artifacts,
        "solution": solution,
        "state": state,
    }


def test_forced_reduction_requires_three_teu_by_truck() -> None:
    """Ten committed TEU with capacity seven leaves three for truck."""
    example = build_recovery_example(0.7)

    try:
        solution = example["solution"]
        recovery = example["recovery"]

        fragment_id = recovery.fragment_ids[0]

        assert solution.is_solved
        assert solution.truck_volume_for(fragment_id) == pytest.approx(3.0)

        assert solution.total_truck_volume == pytest.approx(3.0)
        assert solution.objective_value == pytest.approx(75.0)
        assert solution.total_truck_penalty == pytest.approx(75.0)
    finally:
        example["artifacts"].model.end()


def test_remaining_seven_teu_stay_on_barge() -> None:
    """Every affected transport leg carries seven TEU."""
    example = build_recovery_example(0.7)

    try:
        solution = example["solution"]
        networks = example["networks"]

        index = networks.indexes[0]

        transport_arc_ids = tuple(
            arc_id
            for arc_id in index.feasible_arc_ids
            if example["instance"].arc_by_id(arc_id).is_transport
        )

        assert len(transport_arc_ids) == 2

        for arc_id in transport_arc_ids:
            assert solution.fragment_flow_on(
                index.fragment_id,
                arc_id,
            ) == pytest.approx(7.0)
    finally:
        example["artifacts"].model.end()


def test_barge_plus_truck_reproduces_fragment_volume() -> None:
    """The recourse identity holds at delivery."""
    example = build_recovery_example(0.7)

    try:
        solution = example["solution"]
        index = example["networks"].indexes[0]

        barge_delivered = sum(
            solution.fragment_flow_on(
                index.fragment_id,
                arc_id,
            )
            for arc_id in index.sink_arc_ids
        )

        truck = solution.truck_volume_for(index.fragment_id)

        assert barge_delivered == pytest.approx(7.0)
        assert truck == pytest.approx(3.0)
        assert (barge_delivered + truck) == pytest.approx(index.volume)
    finally:
        example["artifacts"].model.end()


def test_actual_capacity_is_respected() -> None:
    """Barge recovery uses actual rather than nominal capacity."""
    example = build_recovery_example(0.7)

    try:
        solution = example["solution"]
        artifacts = example["artifacts"]
        index = example["networks"].indexes[0]

        for (
            arc_id,
            available,
        ) in artifacts.available_capacities.items():
            used = (
                solution.fragment_flow_on(
                    index.fragment_id,
                    arc_id,
                )
                if arc_id in index.feasible_arc_ids
                else 0.0
            )

            assert available == pytest.approx(7.0)
            assert used <= available + 1e-6
    finally:
        example["artifacts"].model.end()


def test_nominal_capacity_uses_no_truck() -> None:
    """No capacity reduction means the penalty-minimizer stays on barge."""
    example = build_recovery_example(1.0)

    try:
        solution = example["solution"]
        fragment_id = example["recovery"].fragment_ids[0]

        assert solution.is_solved
        assert solution.truck_volume_for(fragment_id) == pytest.approx(0.0)
        assert solution.total_truck_volume == pytest.approx(0.0)
        assert solution.objective_value == pytest.approx(0.0)
    finally:
        example["artifacts"].model.end()


def test_independent_validator_accepts_solution() -> None:
    """Independent residual checks reproduce all model identities."""
    example = build_recovery_example(0.7)

    try:
        report = validate_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
        )

        assert report.is_valid
        assert report.violations == ()
        assert report.max_flow_balance_violation <= 1e-6
        assert report.max_delivery_balance_violation <= 1e-6
        assert report.max_capacity_violation <= 1e-6
        assert report.objective_violation <= 1e-6
    finally:
        example["artifacts"].model.end()


def test_missing_truck_penalty_is_rejected() -> None:
    """The ambiguous paper penalty must be supplied explicitly."""
    example = build_recovery_example(0.7)

    try:
        with pytest.raises(
            ValueError,
            match="must cover exactly",
        ):
            build_truck_recourse_model(
                example["instance"],
                example["recovery"],
                example["capacity"],
                example["networks"],
                truck_penalty_per_teu_by_demand={},
            )
    finally:
        example["artifacts"].model.end()


def test_repeated_solution_is_deterministic() -> None:
    """The controlled recovery solve is deterministic."""
    example = build_recovery_example(0.7)

    try:
        second = solve_truck_recourse_model(example["artifacts"])

        assert second == example["solution"]
    finally:
        example["artifacts"].model.end()


def test_recovery_transition_preserves_booking_history() -> None:
    """A status event changes operations, not the booking decision."""
    example = build_recovery_example(0.7)

    try:
        before = RecoveryOperationalState.empty(example["state"])

        transition = apply_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
            before,
        )

        assert transition.state_after.booking_state == example["state"]
        assert (
            transition.state_after.booking_state.processed_event_count
            == example["state"].processed_event_count
        )
        assert transition.state_after.recovery_event_count == 1
        assert transition.state_after.recovery_event_ids == (example["recovery"].event_id,)
    finally:
        example["artifacts"].model.end()


def test_recovery_transition_persists_seven_plus_three_split() -> None:
    """The 10-TEU fragment persists as seven barge and three truck."""
    example = build_recovery_example(0.7)

    try:
        before = RecoveryOperationalState.empty(example["state"])

        transition = apply_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
            before,
        )

        fragment_id = example["recovery"].fragment_ids[0]
        plan = transition.state_after.plan_for(fragment_id)

        assert plan.original_remaining_volume == pytest.approx(10.0)
        assert plan.barge_volume == pytest.approx(7.0)
        assert plan.truck_volume == pytest.approx(3.0)

        assert plan.truck_transfer is not None
        assert plan.truck_transfer.transfer_node == ("A", 0)
        assert plan.truck_transfer.penalty_value == pytest.approx(75.0)

        assert transition.state_after.total_truck_volume == pytest.approx(3.0)
        assert transition.state_after.total_truck_penalty == pytest.approx(75.0)

        for arc_id in example["capacity"].available_arc_ids:
            assert plan.barge_flow_on(arc_id) == pytest.approx(7.0)
    finally:
        example["artifacts"].model.end()


def test_nominal_recovery_persists_no_truck_transfer() -> None:
    """Unreduced capacity preserves the full barge plan."""
    example = build_recovery_example(1.0)

    try:
        before = RecoveryOperationalState.empty(example["state"])

        transition = apply_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
            before,
        )

        fragment_id = example["recovery"].fragment_ids[0]
        plan = transition.state_after.plan_for(fragment_id)

        assert plan.barge_volume == pytest.approx(10.0)
        assert plan.truck_volume == pytest.approx(0.0)
        assert plan.truck_transfer is None

        assert transition.state_after.truck_transfer_history == ()
        assert transition.state_after.total_truck_volume == pytest.approx(0.0)
    finally:
        example["artifacts"].model.end()


def test_recovery_event_cannot_be_persisted_twice() -> None:
    """Operational recovery events are idempotence-protected."""
    example = build_recovery_example(0.7)

    try:
        before = RecoveryOperationalState.empty(example["state"])

        first = apply_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
            before,
        )

        with pytest.raises(
            ValueError,
            match="cannot be applied twice",
        ):
            apply_truck_recourse_solution(
                example["artifacts"],
                example["solution"],
                first.state_after,
            )
    finally:
        example["artifacts"].model.end()
