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


def _record(
    *,
    volume_ledger: Table5VolumeLedger | None = None,
    allocation_snapshot: Table5AllocationSnapshot | None = None,
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
        demand_fingerprint="demand-fingerprint",
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
    )


def test_campaign_record_accepts_consistent_evidence() -> None:
    record = _record()

    assert record.policy_key == "fr"
    assert record.volume_ledger.accepted_volume == pytest.approx(2.0)
    assert record.allocation_snapshot.final_barge_volume == pytest.approx(1.5)


def test_campaign_record_serialises_nested_evidence() -> None:
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
    assert demands[0]["truck_volume"] == pytest.approx(0.5)


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
            demand_fingerprint="demand",
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
        )
