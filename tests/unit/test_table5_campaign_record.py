"""Tests for rich persisted Table-5 campaign policy records."""

import pytest

from barge_rerouting.reporting.table5_allocations import (
    Table5AllocationSnapshot,
    Table5DemandAllocation,
    Table5OriginalArcAllocation,
)
from barge_rerouting.reporting.table5_campaign_record import (
    TABLE5_CAMPAIGN_RECORD_SCHEMA,
    Table5CampaignPolicyRecord,
)
from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
)

DEMAND_FINGERPRINT = "d" * 64


def _allocation_snapshot() -> Table5AllocationSnapshot:
    return Table5AllocationSnapshot(
        demands=(
            Table5DemandAllocation(
                demand_id="K0001",
                requested_volume=2.0,
                acceptance_fraction=1.0,
                accepted_volume=2.0,
                decision_sequence=1,
                decision_time=0,
                original_arc_allocations=(
                    Table5OriginalArcAllocation(
                        arc_id="transport::a",
                        volume=2.0,
                    ),
                    Table5OriginalArcAllocation(
                        arc_id="transport::b",
                        volume=2.0,
                    ),
                ),
                truck_volume=0.5,
                truck_penalty=50.0,
                final_barge_volume=1.5,
            ),
        )
    )


def _volume_ledger() -> Table5VolumeLedger:
    return Table5VolumeLedger(
        requested_request_count=1,
        accepted_request_count=1,
        requested_volume=2.0,
        accepted_volume=2.0,
        truck_volume=0.5,
        final_barge_volume=1.5,
        gross_revenue=500.0,
        truck_penalty=50.0,
        net_value=450.0,
    )


def _service_snapshot(
    *,
    fingerprint: str = DEMAND_FINGERPRINT,
    final_load: float = 1.5,
) -> Table5ServiceCapacitySnapshot:
    legs = (
        ("a", "A", "B"),
        ("b", "B", "C"),
        ("c", "C", "D"),
        ("d", "D", "E"),
    )

    return Table5ServiceCapacitySnapshot(
        reporting_time=98,
        instance_fingerprint=fingerprint,
        arcs=tuple(
            Table5TransportArcEvidence(
                arc_id=f"transport::{letter}",
                service_id="service::slot01",
                origin=origin,
                destination=destination,
                departure_time=index,
                arrival_time=index + 1,
                nominal_capacity=10.0,
                actual_capacity=10.0,
                original_load=2.0,
                final_load=final_load,
            )
            for index, (
                letter,
                origin,
                destination,
            ) in enumerate(legs)
        ),
    )


def _record(
    *,
    volume_ledger: Table5VolumeLedger | None = None,
    allocation_snapshot: Table5AllocationSnapshot | None = None,
    service_capacity_snapshot: Table5ServiceCapacitySnapshot | None = None,
    runtime_seconds: float = 10.0,
) -> Table5CampaignPolicyRecord:
    return Table5CampaignPolicyRecord(
        reporting_schema_version=(TABLE5_CAMPAIGN_RECORD_SCHEMA),
        run_key=("service_family_1__capacity_10__fr"),
        cell_key=("service_family_1__capacity_10"),
        service_family="service_family_1",
        capacity_teu=10,
        policy_key="fr",
        configuration_fingerprint="config-fingerprint",
        demand_fingerprint=DEMAND_FINGERPRINT,
        solver_backend="cplex_ce_aware",
        completed=True,
        requested_booking_count=1,
        processed_booking_count=1,
        processed_status_count=0,
        feasibility_rejection_count=0,
        ordinary_rejection_count=0,
        solver_failure_count=0,
        runtime_seconds=runtime_seconds,
        volume_ledger=(_volume_ledger() if volume_ledger is None else volume_ledger),
        allocation_snapshot=(
            _allocation_snapshot() if allocation_snapshot is None else allocation_snapshot
        ),
        service_capacity_snapshot=(
            _service_snapshot() if service_capacity_snapshot is None else service_capacity_snapshot
        ),
    )


def test_campaign_record_accepts_consistent_evidence() -> None:
    record = _record()

    assert record.policy_key == "fr"

    assert record.volume_ledger.accepted_volume == pytest.approx(2.0)

    assert record.allocation_snapshot.final_barge_volume == pytest.approx(1.5)

    assert record.service_capacity_snapshot.transport_arc_count == 4


def test_campaign_record_serialises_all_nested_evidence() -> None:
    mapping = _record().to_mapping()

    assert mapping["reporting_schema_version"] == TABLE5_CAMPAIGN_RECORD_SCHEMA

    volume_ledger = mapping["volume_ledger"]

    assert isinstance(
        volume_ledger,
        dict,
    )

    assert volume_ledger["accepted_volume"] == pytest.approx(2.0)

    snapshot = mapping["allocation_snapshot"]

    assert isinstance(
        snapshot,
        dict,
    )

    demands = snapshot["demands"]

    assert demands[0]["demand_id"] == "K0001"

    service_snapshot = mapping["service_capacity_snapshot"]

    assert isinstance(
        service_snapshot,
        dict,
    )

    assert service_snapshot["reporting_time"] == 98

    assert service_snapshot["arcs"][0]["arc_id"] == "transport::a"


def test_campaign_record_rejects_cross_ledger_volume_mismatch() -> None:
    inconsistent_ledger = Table5VolumeLedger(
        requested_request_count=1,
        accepted_request_count=1,
        requested_volume=2.0,
        accepted_volume=1.5,
        truck_volume=0.5,
        final_barge_volume=1.0,
        gross_revenue=500.0,
        truck_penalty=50.0,
        net_value=450.0,
    )

    with pytest.raises(
        ValueError,
        match="accepted_volume disagrees",
    ):
        _record(volume_ledger=inconsistent_ledger)


def test_campaign_record_rejects_request_count_mismatch() -> None:
    inconsistent_ledger = Table5VolumeLedger(
        requested_request_count=2,
        accepted_request_count=1,
        requested_volume=2.0,
        accepted_volume=2.0,
        truck_volume=0.5,
        final_barge_volume=1.5,
        gross_revenue=500.0,
        truck_penalty=50.0,
        net_value=450.0,
    )

    with pytest.raises(
        ValueError,
        match="request count disagrees",
    ):
        _record(volume_ledger=inconsistent_ledger)


def test_campaign_record_rejects_service_fingerprint_mismatch() -> None:
    foreign = _service_snapshot(fingerprint="e" * 64)

    with pytest.raises(
        ValueError,
        match="snapshot fingerprint disagrees",
    ):
        _record(service_capacity_snapshot=foreign)


def test_campaign_record_rejects_material_capacity_overload() -> None:
    overloaded = _service_snapshot(final_load=11.0)

    with pytest.raises(
        ValueError,
        match="material actual-capacity overload",
    ):
        _record(service_capacity_snapshot=overloaded)


def test_campaign_record_rejects_negative_runtime() -> None:
    with pytest.raises(
        ValueError,
        match="runtime_seconds",
    ):
        _record(runtime_seconds=-1.0)


def test_campaign_record_rejects_unknown_schema() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported Table-5 reporting schema",
    ):
        Table5CampaignPolicyRecord(
            reporting_schema_version="unknown",
            run_key="cell__fr",
            cell_key="cell",
            service_family="service_family_1",
            capacity_teu=10,
            policy_key="fr",
            configuration_fingerprint="config",
            demand_fingerprint=DEMAND_FINGERPRINT,
            solver_backend="cplex_ce_aware",
            completed=True,
            requested_booking_count=1,
            processed_booking_count=1,
            processed_status_count=0,
            feasibility_rejection_count=0,
            ordinary_rejection_count=0,
            solver_failure_count=0,
            runtime_seconds=1.0,
            volume_ledger=_volume_ledger(),
            allocation_snapshot=_allocation_snapshot(),
            service_capacity_snapshot=_service_snapshot(),
        )


def test_campaign_record_derives_indicator_snapshot_from_raw_evidence() -> None:
    record = _record()

    indicators = record.indicator_snapshot

    assert indicators.standard_water

    assert indicators.gross_revenue == pytest.approx(500.0)

    assert indicators.truck_penalty == pytest.approx(50.0)

    assert indicators.net_realised_value == pytest.approx(450.0)

    assert indicators.solving_time_seconds == pytest.approx(10.0)

    assert indicators.volume_indicator_candidates.vob_requested_volume_pct == pytest.approx(100.0)

    assert indicators.volume_indicator_candidates.vfb_requested_volume_pct == pytest.approx(75.0)

    assert indicators.volume_indicator_candidates.vtr_requested_volume_pct == pytest.approx(25.0)


def test_campaign_record_mapping_persists_derived_indicator_snapshot() -> None:
    mapping = _record().to_mapping()

    indicators = mapping["indicator_snapshot"]

    assert isinstance(
        indicators,
        dict,
    )

    assert indicators["indicator_schema_version"] == "table5-indicators-v1"

    assert indicators["gross_revenue"] == pytest.approx(500.0)

    assert indicators["solving_time_seconds"] == pytest.approx(10.0)

    volume_candidates = indicators["volume_indicator_candidates"]

    assert volume_candidates["vob_requested_volume_pct"] == pytest.approx(100.0)
