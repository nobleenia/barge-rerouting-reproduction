"""End-to-end tests for dynamic Full-Reroute."""

import pytest
from test_dynamic_booking_capacity import build_instance

from barge_rerouting.disruption import (
    ServiceStatusUpdateEvent,
    build_operational_execution_snapshot,
    build_operational_transport_capacity_snapshot,
    run_dynamic_full_reroute,
    run_partial_reroute,
)


def build_runs():
    """Run PR and FR on the same controlled disruption."""
    instance = build_instance()

    status = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=1,
        valid_from=1,
        valid_until=3,
        water_level_factor=0.7,
    )

    penalties = {
        "K1": 25.0,
        "K2": 1000.0,
    }

    partial = run_partial_reroute(
        instance,
        status_updates=(status,),
        truck_penalty_per_teu_by_demand=penalties,
    )

    full = run_dynamic_full_reroute(
        instance,
        status_updates=(status,),
        truck_penalty_per_teu_by_demand=penalties,
    )

    return instance, status, partial, full


def test_dynamic_fr_uses_status_before_same_time_booking() -> None:
    """The t=1 forecast precedes K2 in operational order."""
    _, status, _, run = build_runs()

    assert run.timeline.event_count == 3

    assert run.timeline.entries[0].is_booking
    assert run.timeline.entries[1].is_status_update
    assert run.timeline.entries[1].event_id == status.event_id
    assert run.timeline.entries[2].is_booking


def test_dynamic_fr_accepts_k2_that_partial_reroute_rejects() -> None:
    """FR booking-triggered rerouting creates the policy difference."""
    _, _, partial, full = build_runs()

    assert partial.completed
    assert full.completed

    assert partial.final_state.booking_state.rejected_demand_ids == ("K2",)

    assert full.final_state.booking_state.accepted_demand_ids == (
        "K1",
        "K2",
    )

    k2_result = full.event_results[2]

    assert k2_result.booking_solution is not None
    assert k2_result.booking_solution.acceptance_fraction == pytest.approx(1.0)


def test_dynamic_fr_accumulates_incremental_truck_history() -> None:
    """Status trucks three TEU and K2-triggered FR trucks one more."""
    _, _, _, run = build_runs()

    status_result = run.event_results[1]
    booking_result = run.event_results[2]

    assert status_result.additional_truck_volume == pytest.approx(3.0)
    assert booking_result.additional_truck_volume == pytest.approx(1.0)

    assert run.total_truck_volume == pytest.approx(4.0)
    assert run.total_truck_penalty == pytest.approx(100.0)


def test_dynamic_fr_final_execution_is_six_plus_four_and_one() -> None:
    """Final operational state is K1 6+4 and K2 1 barge."""
    instance, _, _, run = build_runs()

    execution = build_operational_execution_snapshot(
        instance,
        run.final_state,
        physical_time=1,
    )

    k1 = execution.demand_state_for("K1")
    k2 = execution.demand_state_for("K2")

    assert k1.remaining_volume == pytest.approx(6.0)
    assert k1.delivered_truck_volume == pytest.approx(4.0)

    assert k2.remaining_volume == pytest.approx(1.0)
    assert k2.delivered_truck_volume == pytest.approx(0.0)

    capacity = build_operational_transport_capacity_snapshot(
        instance,
        run.final_state,
        physical_time=1,
    )

    for state in capacity.arc_states:
        if state.is_bookable:
            assert state.future_reserved_volume == pytest.approx(7.0)


def test_dynamic_fr_run_reconciles_revenue_and_penalty() -> None:
    """Revenue and truck penalties remain separate accounting."""
    _, _, _, run = build_runs()

    assert run.completed
    assert run.processed_booking_count == 2
    assert run.processed_status_count == 1

    assert run.accepted_volume == pytest.approx(11.0)

    # K1: 10 TEU * 10 = 100.
    # K2:  1 TEU * 100 = 100.
    assert run.total_revenue == pytest.approx(200.0)

    # K1 ultimately has four truck TEU at 25/TEU.
    assert run.total_truck_penalty == pytest.approx(100.0)

    assert run.net_realised_value == pytest.approx(100.0)
