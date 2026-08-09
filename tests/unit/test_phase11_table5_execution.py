"""Tests for Phase 11 Table 5 PR/FR execution semantics."""

from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.domain import CustomerCategory
from barge_rerouting.experiments.phase11_table5_execution import (
    _advance_a036_operational_state,
)
from barge_rerouting.experiments.phase11_table5_pilot import (
    build_table5_pilot_inputs,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def test_table5_a036_advances_regular_booking_and_preserves_overlay() -> None:
    inputs = build_table5_pilot_inputs()
    instance = inputs.instance

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    target_entry = None

    for entry in inputs.pr_timeline.entries:
        if not entry.is_booking:
            continue

        event = entry.booking_event

        assert event is not None

        if event.demand.category is CustomerCategory.REGULAR:
            target_entry = entry
            break

        booking_state = state.booking_state.advance(
            instance,
            event=event,
            commitment=None,
        )

        state = state.with_booking_state(booking_state)

    assert target_entry is not None

    before = state

    after = _advance_a036_operational_state(
        instance,
        before,
        target_entry,
        solve_status="infeasible",
    )

    assert (
        after.booking_state.processed_event_count == before.booking_state.processed_event_count + 1
    )

    assert after.active_fragment_plans == before.active_fragment_plans

    assert after.truck_transfer_history == before.truck_transfer_history

    assert after.recovery_event_ids == before.recovery_event_ids

    assert after.booking_state.records[:-1] == before.booking_state.records

    assert after.booking_state.records[-1].commitment is None


def test_table5_a036_rejects_ambiguous_solver_status() -> None:
    inputs = build_table5_pilot_inputs()
    instance = inputs.instance

    state = RecoveryOperationalState.empty(RollingBookingState.empty(instance))

    first_regular = None

    for entry in inputs.pr_timeline.entries:
        if not entry.is_booking:
            continue

        event = entry.booking_event

        assert event is not None

        if event.demand.category is CustomerCategory.REGULAR:
            first_regular = entry
            break

        booking_state = state.booking_state.advance(
            instance,
            event=event,
            commitment=None,
        )

        state = state.with_booking_state(booking_state)

    assert first_regular is not None

    try:
        _advance_a036_operational_state(
            instance,
            state,
            first_regular,
            solve_status=("infeasible or unbounded"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("A036 accepted an ambiguous solver status.")


def test_fr_prefix_25_handles_pending_truck_state() -> None:
    """Booking 25 must process while earlier truck cargo is pending."""
    import pytest

    from barge_rerouting.disruption.operational_execution import (
        build_operational_execution_snapshot,
        build_operational_transport_capacity_snapshot,
    )
    from barge_rerouting.disruption.timeline import (
        OperationalTimeline,
        build_operational_timeline,
    )
    from barge_rerouting.experiments.phase11_table5_execution import (
        run_phase11_table5_fr,
    )
    from barge_rerouting.experiments.phase11_table5_pilot import (
        build_table5_pilot_inputs,
    )
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
    )

    inputs = build_table5_pilot_inputs()

    full_timeline = build_operational_timeline(
        inputs.instance,
        status_updates=(),
    )

    selected_entries = []
    booking_count = 0

    for entry in full_timeline.entries:
        selected_entries.append(entry)

        if entry.is_booking:
            booking_count += 1

        if booking_count == 25:
            break

    assert booking_count == 25

    timeline = OperationalTimeline(
        entries=tuple(selected_entries),
    )

    run = run_phase11_table5_fr(
        inputs.instance,
        truck_penalty_per_teu_by_demand=(inputs.truck_penalty_per_teu_by_demand),
        timeline=timeline,
        solver_backend=(SolverBackend.CPLEX_CE_AWARE),
    )

    assert run.completed
    assert run.processed_booking_count == 25
    assert run.solver_failure_count == 0
    assert len(run.event_results) == 25

    event_25_result = run.event_results[24]

    physical_time = event_25_result.entry.physical_time

    assert physical_time == 2

    state_before_25 = event_25_result.state_before

    pending_transfers = tuple(
        transfer
        for transfer in state_before_25.truck_transfer_history
        if transfer.transfer_time > physical_time
    )

    # This is the exact state that previously raised.
    assert pending_transfers

    snapshot = build_operational_execution_snapshot(
        inputs.instance,
        state_before_25,
        physical_time=physical_time,
    )

    capacity = build_operational_transport_capacity_snapshot(
        inputs.instance,
        state_before_25,
        physical_time=physical_time,
    )

    assert capacity.physical_time == physical_time

    affected_demand_ids = {transfer.demand_id for transfer in pending_transfers}

    for demand_id in affected_demand_ids:
        expected_pending = sum(
            transfer.volume
            for transfer in state_before_25.truck_transfer_history
            if (transfer.demand_id == demand_id and transfer.transfer_time > physical_time)
        )

        expected_delivered_truck = sum(
            transfer.volume
            for transfer in state_before_25.truck_transfer_history
            if (transfer.demand_id == demand_id and transfer.transfer_time <= physical_time)
        )

        demand_state = snapshot.demand_state_for(demand_id)

        assert demand_state.pending_truck_volume == pytest.approx(expected_pending)
        assert demand_state.delivered_truck_volume == pytest.approx(expected_delivered_truck)

        assert (
            demand_state.remaining_volume
            + demand_state.delivered_barge_volume
            + demand_state.delivered_truck_volume
            == pytest.approx(demand_state.accepted_volume)
        )

    first_pending = min(
        pending_transfers,
        key=lambda transfer: (
            transfer.transfer_time,
            transfer.event_id,
            transfer.fragment_id,
        ),
    )

    at_transfer = build_operational_execution_snapshot(
        inputs.instance,
        state_before_25,
        physical_time=(first_pending.transfer_time),
    )

    transferred_state = at_transfer.demand_state_for(first_pending.demand_id)

    expected_delivered_at_transfer = sum(
        transfer.volume
        for transfer in state_before_25.truck_transfer_history
        if (
            transfer.demand_id == first_pending.demand_id
            and transfer.transfer_time <= first_pending.transfer_time
        )
    )

    assert transferred_state.delivered_truck_volume == pytest.approx(expected_delivered_at_transfer)

    # Persisted truck allocations are not cancelled
    # merely because another FR booking is processed.
    for transfer in pending_transfers:
        assert transfer in (run.final_state.truck_transfer_history)


def test_fr_prefix_42_preserves_recovery_lineage_accounting() -> None:
    """Repeated FR must preserve accepted-volume accounting."""
    from barge_rerouting.disruption.operational_execution import (
        build_operational_execution_snapshot,
    )
    from barge_rerouting.disruption.timeline import (
        OperationalTimeline,
        build_operational_timeline,
    )
    from barge_rerouting.experiments.phase11_table5_execution import (
        run_phase11_table5_fr,
    )
    from barge_rerouting.experiments.phase11_table5_pilot import (
        build_table5_pilot_inputs,
    )
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
    )

    inputs = build_table5_pilot_inputs()

    full = build_operational_timeline(
        inputs.instance,
        status_updates=(),
    )

    entries = []
    booking_count = 0

    for entry in full.entries:
        entries.append(entry)

        if entry.is_booking:
            booking_count += 1

            if booking_count == 42:
                break

    assert booking_count == 42

    run = run_phase11_table5_fr(
        inputs.instance,
        truck_penalty_per_teu_by_demand=(inputs.truck_penalty_per_teu_by_demand),
        timeline=OperationalTimeline(
            entries=tuple(entries),
        ),
        solver_backend=(SolverBackend.CPLEX_CE_AWARE),
    )

    assert run.completed
    assert run.processed_booking_count == 42
    assert run.solver_failure_count == 0

    result_42 = run.event_results[41]

    assert result_42.entry.physical_time == 4

    snapshot = build_operational_execution_snapshot(
        inputs.instance,
        result_42.state_before,
        physical_time=4,
    )

    for demand_state in snapshot.demand_states:
        accounted = (
            demand_state.remaining_volume
            + demand_state.delivered_barge_volume
            + demand_state.delivered_truck_volume
        )

        assert abs(accounted - demand_state.accepted_volume) <= 1e-6
