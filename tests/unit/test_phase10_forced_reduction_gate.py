"""Final forced-reduction validation gate for Phase 10.

This is a controlled mechanism-validation instance, not a numerical
reproduction of the paper's experimental tables.

The original 10-TEU booking is forced onto a primary barge route.
A later water-level update reduces that route to 7 TEU. An unused
one-TEU alternative barge route remains available. Recovery must
therefore produce:

    7 TEU primary barge
  + 1 TEU alternative barge
  + 2 TEU truck
  = 10 TEU accepted demand.

The test demonstrates that raw arc overload is not itself truck
volume: network rerouting is attempted before truck recourse.
"""

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
    build_operational_execution_snapshot,
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
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def build_forced_reduction_instance():
    """Build primary and one-TEU alternate barge corridors."""
    config = ExperimentConfig(
        experiment_name="phase10-forced-reduction-gate",
        random_seed=10,
        network=NetworkConfig(
            terminals=("A", "B", "C", "D"),
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
                ScheduledTransportLeg(
                    service_id="S2",
                    origin="A",
                    destination="D",
                    departure_time=1,
                    arrival_time=2,
                    capacity=1,
                ),
                ScheduledTransportLeg(
                    service_id="S2",
                    origin="D",
                    destination="C",
                    departure_time=2,
                    arrival_time=3,
                    capacity=1,
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
                demand_id="K1",
                volume=10,
                origin="A",
                destination="C",
                reservation_time=0,
                availability_time=0,
                due_time=3,
                category=CustomerCategory.REGULAR,
                fare_per_teu=10,
            ),
        ),
    )


def _transport_arc_ids_for_service(
    instance,
    service_id: str,
) -> tuple[str, ...]:
    """Return deterministic transport arcs for one service."""
    return tuple(
        sorted(
            str(arc.arc_id)
            for arc in instance.arcs
            if (arc.is_transport and getattr(arc, "service_id", None) == service_id)
        )
    )


def build_forced_reduction_example():
    """Create nominal booking followed by forced recovery."""
    instance = build_forced_reduction_instance()

    primary_arc_ids = _transport_arc_ids_for_service(
        instance,
        "S1",
    )
    alternate_arc_ids = _transport_arc_ids_for_service(
        instance,
        "S2",
    )

    assert len(primary_arc_ids) == 2
    assert len(alternate_arc_ids) == 2

    timeline = build_booking_timeline(instance)
    event = timeline.event_at_sequence(1)

    state = RollingBookingState.empty(instance)

    # The alternate route exists physically but is deliberately
    # unavailable for the original booking. This makes the original
    # commitment deterministic: all 10 TEU are booked on S1.
    initial_capacity_overrides = {
        arc_id: (
            0.0
            if arc_id in alternate_arc_ids
            else float(instance.arc_by_id(arc_id).nominal_capacity)
        )
        for arc_id in (
            *primary_arc_ids,
            *alternate_arc_ids,
        )
    }

    booking_artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
        residual_capacity_overrides=(initial_capacity_overrides),
    )

    try:
        booking_solution = solve_sequential_booking_model(booking_artifacts)

        assert booking_solution.is_solved
        assert booking_solution.acceptance_fraction == pytest.approx(1.0)

        state = apply_sequential_booking_solution(
            booking_artifacts,
            booking_solution,
        )
    finally:
        booking_artifacts.model.end()

    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )

    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )

    # Only primary service S1 is affected by the water reduction.
    # S2 remains at its nominal one-TEU capacity.
    status = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=1,
        valid_from=1,
        valid_until=3,
        water_level_factor=0.7,
        affected_service_ids=("S1",),
    )

    actual_capacity = build_actual_capacity_profile(
        instance,
        physical_time=1,
        status_updates=(status,),
    )

    fragments = build_recovery_fragment_snapshot(
        instance,
        state,
        execution,
        ordinary_capacity,
        status,
    )

    recovery_capacity = build_recovery_capacity_snapshot(
        instance,
        ordinary_capacity,
        actual_capacity,
        fragments,
    )

    networks = build_recovery_fragment_network_snapshot(
        instance,
        fragments,
        recovery_capacity,
    )

    artifacts = build_truck_recourse_model(
        instance,
        fragments,
        recovery_capacity,
        networks,
        truck_penalty_per_teu_by_demand={
            "K1": 25.0,
        },
    )

    solution = solve_truck_recourse_model(artifacts)

    return {
        "instance": instance,
        "state": state,
        "status": status,
        "ordinary_capacity": ordinary_capacity,
        "actual_capacity": actual_capacity,
        "fragments": fragments,
        "recovery_capacity": recovery_capacity,
        "networks": networks,
        "artifacts": artifacts,
        "solution": solution,
        "primary_arc_ids": primary_arc_ids,
        "alternate_arc_ids": alternate_arc_ids,
    }


def test_forced_reduction_old_plan_has_three_teu_overload() -> None:
    """Nominal ten-TEU plan exceeds reduced primary capacity by three."""
    example = build_forced_reduction_example()

    try:
        ordinary = example["ordinary_capacity"]
        actual = example["actual_capacity"]

        overloads = []

        for arc_id in example["primary_arc_ids"]:
            ordinary_state = ordinary.state_for(arc_id)
            actual_state = actual.state_for(arc_id)

            assert ordinary_state.future_reserved_volume == pytest.approx(10.0)
            assert actual_state.nominal_capacity == pytest.approx(10.0)
            assert actual_state.actual_capacity == pytest.approx(7.0)

            overloads.append(ordinary_state.future_reserved_volume - actual_state.actual_capacity)

        assert max(overloads) == pytest.approx(3.0)

        for arc_id in example["alternate_arc_ids"]:
            ordinary_state = ordinary.state_for(arc_id)
            actual_state = actual.state_for(arc_id)

            assert ordinary_state.future_reserved_volume == pytest.approx(0.0)
            assert actual_state.actual_capacity == pytest.approx(1.0)
    finally:
        example["artifacts"].model.end()


def test_rerouting_reduces_truck_shortfall_from_three_to_two() -> None:
    """One TEU reroutes by barge before unavoidable truck recourse."""
    example = build_forced_reduction_example()

    try:
        artifacts = example["artifacts"]
        solution = example["solution"]

        assert solution.is_solved

        report = validate_truck_recourse_solution(
            artifacts,
            solution,
        )

        assert report.is_valid
        assert report.violations == ()

        assert solution.total_truck_volume == pytest.approx(2.0)
        assert solution.total_truck_penalty == pytest.approx(50.0)

        index = example["networks"].indexes[0]
        fragment_id = index.fragment_id

        for arc_id in example["primary_arc_ids"]:
            assert solution.fragment_flow_on(
                fragment_id,
                arc_id,
            ) == pytest.approx(7.0)

        for arc_id in example["alternate_arc_ids"]:
            assert solution.fragment_flow_on(
                fragment_id,
                arc_id,
            ) == pytest.approx(1.0)

        barge_delivered = sum(
            solution.fragment_flow_on(
                fragment_id,
                sink_arc_id,
            )
            for sink_arc_id in index.sink_arc_ids
        )

        assert barge_delivered == pytest.approx(8.0)

        assert barge_delivered + solution.total_truck_volume == pytest.approx(10.0)

        # Critical Phase-10 gate:
        #
        # raw primary overload = 3 TEU
        # actual unavoidable truck shortfall = 2 TEU
        #
        # because one TEU was recovered through S2.
        assert solution.total_truck_volume < 3.0
    finally:
        example["artifacts"].model.end()


def test_forced_reduction_persistence_reconciles_eight_plus_two() -> None:
    """Operational execution preserves the recovered 8+2 split."""
    example = build_forced_reduction_example()

    try:
        before = RecoveryOperationalState.empty(example["state"])

        transition = apply_truck_recourse_solution(
            example["artifacts"],
            example["solution"],
            before,
        )

        assert transition.state_after.total_truck_volume == pytest.approx(2.0)
        assert transition.state_after.total_truck_penalty == pytest.approx(50.0)

        at_recovery = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=1,
        )

        k1_at_recovery = at_recovery.demand_state_for("K1")

        assert k1_at_recovery.remaining_volume == pytest.approx(8.0)
        assert k1_at_recovery.delivered_truck_volume == pytest.approx(2.0)

        final = build_operational_execution_snapshot(
            example["instance"],
            transition.state_after,
            physical_time=3,
        )

        k1_final = final.demand_state_for("K1")

        assert k1_final.remaining_volume == pytest.approx(0.0)
        assert k1_final.delivered_barge_volume == pytest.approx(8.0)
        assert k1_final.delivered_truck_volume == pytest.approx(2.0)
        assert k1_final.is_complete

        assert k1_final.delivered_barge_volume + k1_final.delivered_truck_volume == pytest.approx(
            10.0
        )
    finally:
        example["artifacts"].model.end()
