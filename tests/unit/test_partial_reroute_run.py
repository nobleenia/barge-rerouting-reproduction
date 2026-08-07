"""Tests for dynamic Partial-Reroute orchestration."""

import pytest
from test_dynamic_booking_capacity import build_instance

from barge_rerouting.disruption import (
    ServiceStatusUpdateEvent,
    build_operational_execution_snapshot,
    run_partial_reroute,
)


def build_pr_run():
    """Run booking K1, forecast reduction, then booking K2."""
    instance = build_instance()

    status = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=1,
        valid_from=1,
        valid_until=3,
        water_level_factor=0.7,
    )

    run = run_partial_reroute(
        instance,
        status_updates=(status,),
        truck_penalty_per_teu_by_demand={
            "K1": 25.0,
            "K2": 25.0,
        },
    )

    return instance, status, run


def test_pr_uses_status_before_same_time_booking() -> None:
    """The t=1 forecast must be processed before booking K2."""
    _, status, run = build_pr_run()

    assert run.timeline.event_count == 3

    assert run.timeline.entries[0].is_booking
    assert run.timeline.entries[0].event_id.endswith("K1")

    assert run.timeline.entries[1].is_status_update
    assert run.timeline.entries[1].event_id == (status.event_id)

    assert run.timeline.entries[2].is_booking
    assert run.timeline.entries[2].event_id.endswith("K2")


def test_pr_status_update_trucks_three_teu() -> None:
    """The 10-to-7 reduction sends only unavoidable shortfall to truck."""
    _, _, run = build_pr_run()

    status_result = run.event_results[1]

    assert status_result.entry.is_status_update
    assert status_result.event_was_processed
    assert status_result.recovery_solution is not None
    assert status_result.recovery_solution.total_truck_volume == pytest.approx(3.0)

    assert run.total_truck_volume == pytest.approx(3.0)
    assert run.total_truck_penalty == pytest.approx(75.0)


def test_pr_booking_does_not_reroute_prior_cargo() -> None:
    """K2 booking performs ordinary DCA, not another reroute."""
    _, _, run = build_pr_run()

    status_result = run.event_results[1]
    booking_result = run.event_results[2]

    assert status_result.recovery_transition is not None
    assert booking_result.entry.is_booking
    assert booking_result.recovery_solution is None
    assert booking_result.recovery_transition is None

    assert booking_result.state_before.recovery_event_count == 1
    assert booking_result.state_after.recovery_event_count == 1


def test_pr_rejects_k2_under_reduced_actual_capacity() -> None:
    """K2 cannot use the nominal three-TEU residual."""
    _, _, run = build_pr_run()

    booking_result = run.event_results[2]

    assert booking_result.booking_solution is not None
    assert booking_result.booking_solution.acceptance_fraction == pytest.approx(0.0)

    assert run.final_state.booking_state.accepted_demand_ids == ("K1",)
    assert run.final_state.booking_state.rejected_demand_ids == ("K2",)


def test_pr_final_operational_accounting_preserves_7_plus_3() -> None:
    """K1 remains seven TEU on barge and three terminal truck TEU."""
    instance, _, run = build_pr_run()

    snapshot = build_operational_execution_snapshot(
        instance,
        run.final_state,
        physical_time=1,
    )

    k1 = snapshot.demand_state_for("K1")

    assert run.completed
    assert run.processed_booking_count == 2
    assert run.processed_status_count == 1

    assert k1.accepted_volume == pytest.approx(10.0)
    assert k1.remaining_volume == pytest.approx(7.0)
    assert k1.delivered_truck_volume == pytest.approx(3.0)

    assert run.accepted_volume == pytest.approx(10.0)
    assert run.total_revenue == pytest.approx(100.0)
