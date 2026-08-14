"""Tests for raw Table-5 transport load/capacity evidence."""

import pytest

from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.experiments.phase11_table5 import (
    default_table5_experiment_spec,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCell,
    build_table5_campaign_cell_inputs,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
    build_table5_service_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def _arc(
    *,
    arc_id: str = "transport::1",
    nominal: float = 10.0,
    actual: float = 10.0,
    original: float = 4.0,
    final: float = 4.0,
) -> Table5TransportArcEvidence:
    return Table5TransportArcEvidence(
        arc_id=arc_id,
        service_id="service::slot01",
        origin="A",
        destination="B",
        departure_time=0,
        arrival_time=1,
        nominal_capacity=nominal,
        actual_capacity=actual,
        original_load=original,
        final_load=final,
    )


def test_standard_water_snapshot_is_detected() -> None:
    snapshot = Table5ServiceCapacitySnapshot(
        reporting_time=10,
        instance_fingerprint="a" * 64,
        arcs=(
            _arc(
                arc_id="transport::1",
            ),
            Table5TransportArcEvidence(
                arc_id="transport::2",
                service_id="service::slot01",
                origin="B",
                destination="C",
                departure_time=1,
                arrival_time=2,
                nominal_capacity=10.0,
                actual_capacity=10.0,
                original_load=4.0,
                final_load=4.0,
            ),
        ),
    )

    assert snapshot.standard_water
    assert snapshot.transport_arc_count == 2
    assert snapshot.total_original_arc_load == pytest.approx(8.0)
    assert snapshot.total_final_arc_load == pytest.approx(8.0)
    assert snapshot.total_nominal_arc_capacity == pytest.approx(20.0)
    assert snapshot.total_actual_arc_capacity == pytest.approx(20.0)


def test_reduced_capacity_is_retained_without_hiding_overload() -> None:
    snapshot = Table5ServiceCapacitySnapshot(
        reporting_time=10,
        instance_fingerprint="b" * 64,
        arcs=(
            _arc(
                nominal=10.0,
                actual=8.0,
                final=9.0,
            ),
        ),
    )

    assert not snapshot.standard_water

    assert snapshot.max_final_actual_capacity_violation == pytest.approx(1.0)


def test_empty_table5_booking_state_builds_112_arc_records() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    state = RollingBookingState.empty(inputs.instance)

    snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=state,
        reporting_time=spec.horizon_end,
        status_updates=inputs.pr_updates,
    )

    assert snapshot.transport_arc_count == 112

    assert len(snapshot.recurring_service_ids) == 4

    assert snapshot.standard_water

    assert snapshot.total_original_arc_load == pytest.approx(0.0)

    assert snapshot.total_final_arc_load == pytest.approx(0.0)

    assert {arc.nominal_capacity for arc in snapshot.arcs} == {10.0}

    assert {arc.actual_capacity for arc in snapshot.arcs} == {10.0}


def test_empty_recovery_state_uses_same_physical_evidence() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    booking_state = RollingBookingState.empty(inputs.instance)

    recovery_state = RecoveryOperationalState(booking_state=booking_state)

    snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=recovery_state,
        reporting_time=spec.horizon_end,
        status_updates=inputs.pr_updates,
    )

    assert snapshot.transport_arc_count == 112
    assert snapshot.standard_water

    assert snapshot.total_final_arc_load == pytest.approx(0.0)


def test_duplicate_arc_ids_are_rejected() -> None:
    arc = _arc()

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        Table5ServiceCapacitySnapshot(
            reporting_time=10,
            instance_fingerprint="c" * 64,
            arcs=(
                arc,
                arc,
            ),
        )


def test_historical_reduced_water_preserves_departure_capacity() -> None:
    """Reduced-water reporting must not revert past arcs to nominal capacity."""
    from dataclasses import replace

    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=spec.reproduction_class,
        ),
        spec=spec,
    )

    reduced_updates = tuple(
        replace(
            update,
            water_level_factor=0.8,
        )
        for update in inputs.pr_updates
    )

    state = RollingBookingState.empty(inputs.instance)

    snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=state,
        reporting_time=spec.horizon_end,
        status_updates=reduced_updates,
        historical_actual_capacity=True,
    )

    assert snapshot.transport_arc_count == 112
    assert not snapshot.standard_water

    assert {arc.nominal_capacity for arc in snapshot.arcs} == {10.0}

    assert {arc.actual_capacity for arc in snapshot.arcs} == {8.0}

    assert all(arc.water_level_factor == pytest.approx(0.8) for arc in snapshot.arcs)
