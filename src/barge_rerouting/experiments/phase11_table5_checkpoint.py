"""Resumable checkpoint persistence for the Phase-11 Table-5 campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from barge_rerouting.experiments.phase11_table5_campaign import (
    build_default_table5_run_plan,
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

TABLE5_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION: Final = 1
TABLE5_CAMPAIGN_EXPERIMENT_KEY: Final = "phase11_table5_campaign"


def _as_mapping(
    value: object,
    context: str,
) -> dict[str, Any]:
    """Return one validated JSON mapping."""
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a mapping.")

    result: dict[str, Any] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"Every key in {context} must be a string.")

        result[key] = item

    return result


def _as_list(
    value: object,
    context: str,
) -> list[Any]:
    """Return one validated JSON list."""
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a list.")

    return value


def _restore_original_arc_allocation(
    payload: dict[str, Any],
) -> Table5OriginalArcAllocation:
    """Restore one original booking-time arc-flow record."""
    return Table5OriginalArcAllocation(
        arc_id=payload["arc_id"],
        volume=payload["volume"],
    )


def _restore_demand_allocation(
    payload: dict[str, Any],
) -> Table5DemandAllocation:
    """Restore one accepted demand's reporting evidence."""
    raw_arcs = _as_list(
        payload["original_arc_allocations"],
        "original_arc_allocations",
    )

    arc_allocations = tuple(
        _restore_original_arc_allocation(
            _as_mapping(
                raw,
                "original_arc_allocation",
            )
        )
        for raw in raw_arcs
    )

    return Table5DemandAllocation(
        demand_id=payload["demand_id"],
        requested_volume=payload["requested_volume"],
        acceptance_fraction=payload["acceptance_fraction"],
        accepted_volume=payload["accepted_volume"],
        decision_sequence=payload["decision_sequence"],
        decision_time=payload["decision_time"],
        original_arc_allocations=arc_allocations,
        truck_volume=payload["truck_volume"],
        truck_penalty=payload["truck_penalty"],
        final_barge_volume=payload["final_barge_volume"],
    )


def _restore_allocation_snapshot(
    payload: dict[str, Any],
) -> Table5AllocationSnapshot:
    """Restore the per-demand allocation snapshot."""
    raw_demands = _as_list(
        payload["demands"],
        "allocation_snapshot.demands",
    )

    return Table5AllocationSnapshot(
        demands=tuple(
            _restore_demand_allocation(
                _as_mapping(
                    raw,
                    "demand_allocation",
                )
            )
            for raw in raw_demands
        )
    )


def _restore_volume_ledger(
    payload: dict[str, Any],
) -> Table5VolumeLedger:
    """Restore the aggregate Table-5 volume ledger."""
    return Table5VolumeLedger(
        requested_request_count=payload["requested_request_count"],
        accepted_request_count=payload["accepted_request_count"],
        requested_volume=payload["requested_volume"],
        accepted_volume=payload["accepted_volume"],
        truck_volume=payload["truck_volume"],
        final_barge_volume=payload["final_barge_volume"],
        gross_revenue=payload["gross_revenue"],
        truck_penalty=payload["truck_penalty"],
        net_value=payload["net_value"],
    )


def _restore_record(
    payload: dict[str, Any],
) -> Table5CampaignPolicyRecord:
    """Restore one rich Table-5 campaign record."""
    return Table5CampaignPolicyRecord(
        reporting_schema_version=payload["reporting_schema_version"],
        run_key=payload["run_key"],
        cell_key=payload["cell_key"],
        service_family=payload["service_family"],
        capacity_teu=payload["capacity_teu"],
        policy_key=payload["policy_key"],
        configuration_fingerprint=payload["configuration_fingerprint"],
        demand_fingerprint=payload["demand_fingerprint"],
        solver_backend=payload["solver_backend"],
        completed=payload["completed"],
        requested_booking_count=payload["requested_booking_count"],
        processed_booking_count=payload["processed_booking_count"],
        processed_status_count=payload["processed_status_count"],
        feasibility_rejection_count=payload["feasibility_rejection_count"],
        ordinary_rejection_count=payload["ordinary_rejection_count"],
        solver_failure_count=payload["solver_failure_count"],
        runtime_seconds=payload["runtime_seconds"],
        volume_ledger=_restore_volume_ledger(
            _as_mapping(
                payload["volume_ledger"],
                "volume_ledger",
            )
        ),
        allocation_snapshot=(
            _restore_allocation_snapshot(
                _as_mapping(
                    payload["allocation_snapshot"],
                    "allocation_snapshot",
                )
            )
        ),
    )


def _ordered_records(
    records: list[Table5CampaignPolicyRecord],
) -> tuple[
    Table5CampaignPolicyRecord,
    ...,
]:
    """Return records in canonical 24-run order."""
    run_plan = build_default_table5_run_plan()

    order = {run.run_key: index for index, run in enumerate(run_plan)}

    return tuple(
        sorted(
            records,
            key=lambda record: order[record.run_key],
        )
    )


def validate_table5_checkpoint_records(
    records: list[Table5CampaignPolicyRecord],
) -> None:
    """Reject duplicate, incomplete, or foreign records."""
    run_plan = build_default_table5_run_plan()

    expected = {run.run_key: run for run in run_plan}

    seen: set[str] = set()

    for record in records:
        if record.run_key in seen:
            raise RuntimeError(f"Duplicate Table-5 checkpoint run key: {record.run_key}.")

        seen.add(record.run_key)

        planned = expected.get(record.run_key)

        if planned is None:
            raise RuntimeError(f"Checkpoint contains a foreign Table-5 run: {record.run_key}.")

        if not record.completed:
            raise RuntimeError("Successful Table-5 checkpoint records must be completed.")

        if record.solver_failure_count != 0:
            raise RuntimeError(
                "Successful Table-5 checkpoint records cannot contain solver failures."
            )

        if record.cell_key != planned.cell_key:
            raise RuntimeError("Checkpoint cell key disagrees with the frozen run plan.")

        if record.service_family != planned.service_family:
            raise RuntimeError("Checkpoint service family disagrees with the frozen run plan.")

        if record.capacity_teu != planned.capacity_teu:
            raise RuntimeError("Checkpoint capacity disagrees with the frozen run plan.")

        if record.policy_key != planned.policy_key:
            raise RuntimeError("Checkpoint policy disagrees with the frozen run plan.")


def _atomic_json_write(
    payload: dict[str, object],
    path: Path,
) -> None:
    """Atomically replace one JSON output."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)


def load_table5_campaign_checkpoint(
    checkpoint_path: str | Path,
) -> tuple[
    list[Table5CampaignPolicyRecord],
    dict[str, dict[str, object]],
]:
    """Load validated Table-5 campaign state."""
    path = Path(checkpoint_path)

    if not path.exists():
        return [], {}

    raw_payload = json.loads(path.read_text(encoding="utf-8"))

    payload = _as_mapping(
        raw_payload,
        "Table-5 checkpoint",
    )

    if payload.get("schema_version") != TABLE5_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION:
        raise RuntimeError("Unsupported Table-5 campaign checkpoint schema.")

    if payload.get("experiment") != TABLE5_CAMPAIGN_EXPERIMENT_KEY:
        raise RuntimeError("Checkpoint belongs to another experiment.")

    if payload.get("reporting_schema_version") != TABLE5_CAMPAIGN_RECORD_SCHEMA:
        raise RuntimeError(
            "Checkpoint reporting schema disagrees with the current Table-5 contract."
        )

    raw_records = _as_list(
        payload.get(
            "records",
            [],
        ),
        "checkpoint records",
    )

    records = [
        _restore_record(
            _as_mapping(
                raw,
                "checkpoint record",
            )
        )
        for raw in raw_records
    ]

    validate_table5_checkpoint_records(records)

    raw_metadata = _as_mapping(
        payload.get(
            "cell_metadata",
            {},
        ),
        "cell_metadata",
    )

    metadata: dict[
        str,
        dict[str, object],
    ] = {}

    for key, value in raw_metadata.items():
        metadata[key] = dict(
            _as_mapping(
                value,
                f"cell_metadata[{key}]",
            )
        )

    return (
        list(_ordered_records(records)),
        metadata,
    )


def write_table5_campaign_checkpoint(
    records: list[Table5CampaignPolicyRecord],
    cell_metadata: dict[
        str,
        dict[str, object],
    ],
    checkpoint_path: str | Path,
) -> Path:
    """Atomically persist resumable Table-5 campaign state."""
    validate_table5_checkpoint_records(records)

    ordered = _ordered_records(records)

    path = Path(checkpoint_path)

    payload: dict[str, object] = {
        "schema_version": (TABLE5_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION),
        "experiment": (TABLE5_CAMPAIGN_EXPERIMENT_KEY),
        "reporting_schema_version": (TABLE5_CAMPAIGN_RECORD_SCHEMA),
        "records": [record.to_mapping() for record in ordered],
        "cell_metadata": cell_metadata,
    }

    _atomic_json_write(
        payload,
        path,
    )

    return path
