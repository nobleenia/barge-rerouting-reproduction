"""Tests for resumable Phase-11 Table-5 checkpoints."""

import json
from dataclasses import replace

import pytest

from barge_rerouting.experiments.phase11_table5_checkpoint import (
    TABLE5_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION,
    load_table5_campaign_checkpoint,
    validate_table5_checkpoint_records,
    write_table5_campaign_checkpoint,
)
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


def _record(
    *,
    capacity_teu: int = 10,
    policy_key: str = "dca",
) -> Table5CampaignPolicyRecord:
    cell_key = f"service_family_1__capacity_{capacity_teu}"

    run_key = f"{cell_key}__{policy_key}"

    snapshot = Table5AllocationSnapshot(
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
                ),
                truck_volume=0.0,
                truck_penalty=0.0,
                final_barge_volume=2.0,
            ),
        )
    )

    ledger = Table5VolumeLedger(
        requested_request_count=1,
        accepted_request_count=1,
        requested_volume=2.0,
        accepted_volume=2.0,
        truck_volume=0.0,
        final_barge_volume=2.0,
        gross_revenue=500.0,
        truck_penalty=0.0,
        net_value=500.0,
    )

    service_snapshot = Table5ServiceCapacitySnapshot(
        reporting_time=98,
        instance_fingerprint=(DEMAND_FINGERPRINT),
        arcs=(
            Table5TransportArcEvidence(
                arc_id="transport::a",
                service_id="service::slot01",
                origin="A",
                destination="B",
                departure_time=0,
                arrival_time=1,
                nominal_capacity=float(capacity_teu),
                actual_capacity=float(capacity_teu),
                original_load=2.0,
                final_load=2.0,
            ),
        ),
    )

    return Table5CampaignPolicyRecord(
        reporting_schema_version=(TABLE5_CAMPAIGN_RECORD_SCHEMA),
        run_key=run_key,
        cell_key=cell_key,
        service_family="service_family_1",
        capacity_teu=capacity_teu,
        policy_key=policy_key,
        configuration_fingerprint="config",
        demand_fingerprint=DEMAND_FINGERPRINT,
        solver_backend="cplex",
        completed=True,
        requested_booking_count=1,
        processed_booking_count=1,
        processed_status_count=0,
        feasibility_rejection_count=0,
        ordinary_rejection_count=0,
        solver_failure_count=0,
        runtime_seconds=1.5,
        volume_ledger=ledger,
        allocation_snapshot=snapshot,
        service_capacity_snapshot=(service_snapshot),
    )


def test_missing_checkpoint_returns_empty_state(
    tmp_path,
) -> None:
    records, metadata = load_table5_campaign_checkpoint(tmp_path / "missing.json")

    assert records == []
    assert metadata == {}


def test_checkpoint_round_trip_preserves_rich_evidence(
    tmp_path,
) -> None:
    path = tmp_path / "campaign_checkpoint.json"

    record = _record()

    metadata = {
        record.cell_key: {
            "capacity_teu": 10,
            "demand_fingerprint": (DEMAND_FINGERPRINT),
        }
    }

    write_table5_campaign_checkpoint(
        [record],
        metadata,
        path,
    )

    restored, restored_metadata = load_table5_campaign_checkpoint(path)

    assert len(restored) == 1

    result = restored[0]

    assert result.run_key == record.run_key

    assert result.volume_ledger.accepted_volume == pytest.approx(2.0)

    assert (
        result.allocation_snapshot.demands[0].original_arc_allocations[0].arc_id == "transport::a"
    )

    assert result.service_capacity_snapshot.arcs[0].arc_id == "transport::a"

    assert result.service_capacity_snapshot.arcs[0].actual_capacity == pytest.approx(10.0)

    assert restored_metadata == metadata


def test_checkpoint_uses_expected_schema(
    tmp_path,
) -> None:
    path = tmp_path / "campaign_checkpoint.json"

    write_table5_campaign_checkpoint(
        [_record()],
        {},
        path,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == TABLE5_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION

    assert payload["reporting_schema_version"] == TABLE5_CAMPAIGN_RECORD_SCHEMA

    assert payload["records"][0]["service_capacity_snapshot"]["arcs"][0]["arc_id"] == "transport::a"


def test_duplicate_run_keys_are_rejected() -> None:
    record = _record()

    with pytest.raises(
        RuntimeError,
        match="Duplicate Table-5 checkpoint",
    ):
        validate_table5_checkpoint_records(
            [
                record,
                record,
            ]
        )


def test_foreign_run_is_rejected() -> None:
    record = replace(
        _record(),
        run_key="foreign__run",
    )

    with pytest.raises(
        RuntimeError,
        match="foreign Table-5 run",
    ):
        validate_table5_checkpoint_records([record])


def test_records_are_written_in_frozen_run_order(
    tmp_path,
) -> None:
    first = _record(
        capacity_teu=10,
        policy_key="dca",
    )

    second = _record(
        capacity_teu=10,
        policy_key="fr",
    )

    path = tmp_path / "campaign_checkpoint.json"

    write_table5_campaign_checkpoint(
        [
            second,
            first,
        ],
        {},
        path,
    )

    restored, _ = load_table5_campaign_checkpoint(path)

    assert [record.policy_key for record in restored] == [
        "dca",
        "fr",
    ]


def test_wrong_checkpoint_schema_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "campaign_checkpoint.json"

    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "experiment": ("phase11_table5_campaign"),
                "reporting_schema_version": (TABLE5_CAMPAIGN_RECORD_SCHEMA),
                "records": [],
                "cell_metadata": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported Table-5",
    ):
        load_table5_campaign_checkpoint(path)
