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
from barge_rerouting.reporting.table5_fill_rates import (
    Table5FillRateCandidates,
)
from barge_rerouting.reporting.table5_indicators import (
    Table5IndicatorSnapshot,
)
from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
)
from barge_rerouting.reporting.table5_volume_indicators import (
    Table5VolumeIndicatorCandidates,
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
    return Table5OriginalArcAllocation(
        arc_id=payload["arc_id"],
        volume=payload["volume"],
    )


def _restore_demand_allocation(
    payload: dict[str, Any],
) -> Table5DemandAllocation:
    raw_arcs = _as_list(
        payload["original_arc_allocations"],
        "original_arc_allocations",
    )

    return Table5DemandAllocation(
        demand_id=payload["demand_id"],
        requested_volume=payload["requested_volume"],
        acceptance_fraction=payload["acceptance_fraction"],
        accepted_volume=payload["accepted_volume"],
        decision_sequence=payload["decision_sequence"],
        decision_time=payload["decision_time"],
        original_arc_allocations=tuple(
            _restore_original_arc_allocation(
                _as_mapping(
                    raw,
                    "original_arc_allocation",
                )
            )
            for raw in raw_arcs
        ),
        truck_volume=payload["truck_volume"],
        truck_penalty=payload["truck_penalty"],
        final_barge_volume=payload["final_barge_volume"],
    )


def _restore_allocation_snapshot(
    payload: dict[str, Any],
) -> Table5AllocationSnapshot:
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


def _restore_transport_arc_evidence(
    payload: dict[str, Any],
) -> Table5TransportArcEvidence:
    return Table5TransportArcEvidence(
        arc_id=payload["arc_id"],
        service_id=payload["service_id"],
        origin=payload["origin"],
        destination=payload["destination"],
        departure_time=payload["departure_time"],
        arrival_time=payload["arrival_time"],
        nominal_capacity=payload["nominal_capacity"],
        actual_capacity=payload["actual_capacity"],
        original_load=payload["original_load"],
        final_load=payload["final_load"],
        source_update_event_id=payload.get("source_update_event_id"),
    )


def _restore_service_capacity_snapshot(
    payload: dict[str, Any],
) -> Table5ServiceCapacitySnapshot:
    raw_arcs = _as_list(
        payload["arcs"],
        "service_capacity_snapshot.arcs",
    )

    return Table5ServiceCapacitySnapshot(
        reporting_time=payload["reporting_time"],
        instance_fingerprint=payload["instance_fingerprint"],
        arcs=tuple(
            _restore_transport_arc_evidence(
                _as_mapping(
                    raw,
                    "transport_arc_evidence",
                )
            )
            for raw in raw_arcs
        ),
    )


def _restore_fill_rate_candidates(
    payload: dict[str, Any],
) -> Table5FillRateCandidates:
    return Table5FillRateCandidates(
        transport_arc_count=payload["transport_arc_count"],
        sailing_occurrence_count=payload["sailing_occurrence_count"],
        mean_arc_actual_pct=payload["mean_arc_actual_pct"],
        mean_arc_nominal_pct=payload["mean_arc_nominal_pct"],
        capacity_weighted_actual_pct=payload["capacity_weighted_actual_pct"],
        capacity_weighted_nominal_pct=payload["capacity_weighted_nominal_pct"],
        mean_sailing_peak_actual_pct=payload["mean_sailing_peak_actual_pct"],
        mean_sailing_peak_nominal_pct=payload["mean_sailing_peak_nominal_pct"],
    )


def _restore_volume_indicator_candidates(
    payload: dict[str, Any],
) -> Table5VolumeIndicatorCandidates:
    return Table5VolumeIndicatorCandidates(
        requested_volume=payload["requested_volume"],
        accepted_volume=payload["accepted_volume"],
        truck_volume=payload["truck_volume"],
        final_barge_volume=payload["final_barge_volume"],
        requested_request_count=payload["requested_request_count"],
        accepted_request_count=payload["accepted_request_count"],
        vtr_requested_volume_pct=payload["vtr_requested_volume_pct"],
        vfb_requested_volume_pct=payload["vfb_requested_volume_pct"],
        vob_requested_volume_pct=payload["vob_requested_volume_pct"],
        voa_request_count_pct=payload["voa_request_count_pct"],
        voa_requested_volume_pct=payload["voa_requested_volume_pct"],
    )


def _restore_indicator_snapshot(
    payload: dict[str, Any],
) -> Table5IndicatorSnapshot:
    return Table5IndicatorSnapshot(
        indicator_schema_version=payload["indicator_schema_version"],
        fill_rate_candidates=(
            _restore_fill_rate_candidates(
                _as_mapping(
                    payload["fill_rate_candidates"],
                    "indicator_snapshot.fill_rate_candidates",
                )
            )
        ),
        volume_indicator_candidates=(
            _restore_volume_indicator_candidates(
                _as_mapping(
                    payload["volume_indicator_candidates"],
                    "indicator_snapshot.volume_indicator_candidates",
                )
            )
        ),
        gross_revenue=payload["gross_revenue"],
        truck_penalty=payload["truck_penalty"],
        net_realised_value=payload["net_realised_value"],
        solving_time_seconds=payload["solving_time_seconds"],
        standard_water=payload["standard_water"],
    )


def _restore_record(
    payload: dict[str, Any],
) -> Table5CampaignPolicyRecord:
    record = Table5CampaignPolicyRecord(
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
        service_capacity_snapshot=(
            _restore_service_capacity_snapshot(
                _as_mapping(
                    payload["service_capacity_snapshot"],
                    "service_capacity_snapshot",
                )
            )
        ),
    )

    persisted_indicator_snapshot = _restore_indicator_snapshot(
        _as_mapping(
            payload["indicator_snapshot"],
            "indicator_snapshot",
        )
    )

    if persisted_indicator_snapshot != record.indicator_snapshot:
        raise RuntimeError(
            "Persisted Table-5 indicator snapshot disagrees with raw campaign evidence."
        )

    return record


def _ordered_records(
    records: list[Table5CampaignPolicyRecord],
) -> tuple[
    Table5CampaignPolicyRecord,
    ...,
]:
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
