"""Resumable execution driver for the Phase-11 Table-5 campaign.

The frozen campaign contains:

    2 service families
    x 4 nominal capacities
    x 3 policies
    = 24 policy runs.

Each successful policy run is checkpointed immediately before another
policy is allowed to start.
"""

from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import Final

from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCell,
    Table5CampaignCellInputs,
    Table5CampaignRunSpec,
    build_default_table5_run_plan,
    build_table5_campaign_cell_inputs,
)
from barge_rerouting.experiments.phase11_table5_campaign_execution import (
    execute_table5_campaign_policy,
)
from barge_rerouting.experiments.phase11_table5_checkpoint import (
    load_table5_campaign_checkpoint,
    write_table5_campaign_checkpoint,
)
from barge_rerouting.reporting.table5_campaign_record import (
    TABLE5_CAMPAIGN_RECORD_SCHEMA,
    Table5CampaignPolicyRecord,
)

TABLE5_CAMPAIGN_POLICY_RUN_COUNT: Final = 24
_METADATA_VOLUME_TOLERANCE: Final = 1.0e-9


def _validate_max_new_runs(
    max_new_runs: int | None,
) -> None:
    """Validate the optional campaign execution limit."""
    if max_new_runs is None:
        return

    if (
        isinstance(
            max_new_runs,
            bool,
        )
        or not isinstance(
            max_new_runs,
            int,
        )
        or max_new_runs <= 0
    ):
        raise ValueError("max_new_runs must be a positive integer or None.")


def _ordered_records(
    records: list[Table5CampaignPolicyRecord],
) -> tuple[
    Table5CampaignPolicyRecord,
    ...,
]:
    """Return records in canonical frozen run-plan order."""
    run_plan = build_default_table5_run_plan()

    order = {run.run_key: index for index, run in enumerate(run_plan)}

    return tuple(
        sorted(
            records,
            key=lambda record: order[record.run_key],
        )
    )


def _expected_cell_metadata(
    inputs: Table5CampaignCellInputs,
) -> dict[str, object]:
    """Return frozen resumability metadata for one structural cell."""
    return {
        "service_family": (inputs.cell.service_family),
        "capacity_teu": (inputs.cell.capacity_teu),
        "reproduction_class": (inputs.cell.reproduction_class),
        "configuration_fingerprint": (inputs.configuration_fingerprint),
        "demand_fingerprint": (inputs.demand_fingerprint),
        "requested_booking_count": (inputs.requested_booking_count),
        "requested_volume": (inputs.requested_volume),
        "reporting_schema_version": (inputs.reporting_schema_version),
    }


def _validate_cell_metadata(
    *,
    cell_key: str,
    persisted: dict[str, object],
    expected: dict[str, object],
) -> None:
    """Reject resumed cell metadata that no longer matches inputs."""
    for key, expected_value in expected.items():
        if key not in persisted:
            raise RuntimeError(
                f"Table-5 checkpoint metadata is missing {key!r} for cell {cell_key}."
            )

        persisted_value = persisted[key]

        if key == "requested_volume":
            if (
                isinstance(persisted_value, bool)
                or not isinstance(
                    persisted_value,
                    (int, float),
                )
                or isinstance(expected_value, bool)
                or not isinstance(
                    expected_value,
                    (int, float),
                )
            ):
                raise RuntimeError(
                    f"Invalid requested_volume metadata for Table-5 cell {cell_key}."
                )

            matches = isclose(
                persisted_value,
                expected_value,
                rel_tol=0.0,
                abs_tol=_METADATA_VOLUME_TOLERANCE,
            )

        else:
            matches = persisted_value == expected_value

        if not matches:
            raise RuntimeError(f"Table-5 checkpoint metadata disagrees for cell {cell_key}: {key}.")


def _validate_existing_cell_records(
    *,
    records: list[Table5CampaignPolicyRecord],
    inputs: Table5CampaignCellInputs,
) -> None:
    """Verify existing successful records against rebuilt frozen inputs."""
    cell_records = [record for record in records if (record.cell_key == inputs.cell.cell_key)]

    for record in cell_records:
        if record.configuration_fingerprint != inputs.configuration_fingerprint:
            raise RuntimeError(
                "Checkpoint configuration fingerprint "
                "disagrees with rebuilt Table-5 cell "
                f"{inputs.cell.cell_key}."
            )

        if record.demand_fingerprint != inputs.demand_fingerprint:
            raise RuntimeError(
                "Checkpoint demand fingerprint disagrees "
                "with rebuilt Table-5 cell "
                f"{inputs.cell.cell_key}."
            )

        if record.requested_booking_count != inputs.requested_booking_count:
            raise RuntimeError(
                "Checkpoint request count disagrees "
                "with rebuilt Table-5 cell "
                f"{inputs.cell.cell_key}."
            )

        if not isclose(
            record.volume_ledger.requested_volume,
            inputs.requested_volume,
            rel_tol=0.0,
            abs_tol=(_METADATA_VOLUME_TOLERANCE),
        ):
            raise RuntimeError(
                "Checkpoint requested volume disagrees "
                "with rebuilt Table-5 cell "
                f"{inputs.cell.cell_key}."
            )


def _build_validated_cell_inputs(
    run_plan: tuple[
        Table5CampaignRunSpec,
        ...,
    ],
    records: list[Table5CampaignPolicyRecord],
    cell_metadata: dict[str, dict[str, object]],
) -> tuple[
    dict[
        str,
        Table5CampaignCellInputs,
    ],
    dict[
        str,
        dict[str, object],
    ],
]:
    """Build each structural cell once and validate resume evidence."""
    inputs_by_cell: dict[
        str,
        Table5CampaignCellInputs,
    ] = {}

    expected_metadata: dict[
        str,
        dict[str, object],
    ] = {}

    for run_spec in run_plan:
        if run_spec.cell_key in inputs_by_cell:
            continue

        cell = Table5CampaignCell(
            service_family=(run_spec.service_family),
            capacity_teu=(run_spec.capacity_teu),
            reproduction_class=(run_spec.reproduction_class),
        )

        inputs = build_table5_campaign_cell_inputs(cell)

        if inputs.reporting_schema_version != TABLE5_CAMPAIGN_RECORD_SCHEMA:
            raise RuntimeError(
                "Table-5 campaign input reporting "
                "schema disagrees with the current "
                "rich reporting contract."
            )

        inputs_by_cell[run_spec.cell_key] = inputs

        expected_metadata[run_spec.cell_key] = _expected_cell_metadata(inputs)

    if len(inputs_by_cell) != 8:
        raise RuntimeError("Frozen Table-5 campaign must contain exactly eight structural cells.")

    demand_fingerprints = {inputs.demand_fingerprint for inputs in (inputs_by_cell.values())}

    if len(demand_fingerprints) != 1:
        raise RuntimeError(
            "Table-5 structural cells do not share one frozen realised demand fingerprint."
        )

    requested_counts = {inputs.requested_booking_count for inputs in (inputs_by_cell.values())}

    if len(requested_counts) != 1:
        raise RuntimeError("Table-5 structural cells do not share one frozen request count.")

    requested_volumes = {inputs.requested_volume for inputs in (inputs_by_cell.values())}

    if len(requested_volumes) != 1:
        raise RuntimeError("Table-5 structural cells do not share one frozen requested volume.")

    unknown_metadata = set(cell_metadata) - set(inputs_by_cell)

    if unknown_metadata:
        raise RuntimeError(
            "Table-5 checkpoint contains metadata "
            "for foreign structural cells: " + ", ".join(sorted(unknown_metadata))
        )

    for (
        cell_key,
        inputs,
    ) in inputs_by_cell.items():
        cell_records = [record for record in records if (record.cell_key == cell_key)]

        persisted_metadata = cell_metadata.get(cell_key)

        if cell_records and persisted_metadata is None:
            raise RuntimeError(
                "Table-5 checkpoint contains completed "
                "records without cell metadata for "
                f"{cell_key}."
            )

        if persisted_metadata is not None:
            _validate_cell_metadata(
                cell_key=cell_key,
                persisted=(persisted_metadata),
                expected=(expected_metadata[cell_key]),
            )

        _validate_existing_cell_records(
            records=records,
            inputs=inputs,
        )

    return (
        inputs_by_cell,
        expected_metadata,
    )


def run_table5_campaign(
    *,
    output_directory: str | Path,
    max_new_runs: int | None = None,
) -> tuple[
    Table5CampaignPolicyRecord,
    ...,
]:
    """Execute or resume the frozen 24-run Table-5 campaign."""
    _validate_max_new_runs(max_new_runs)

    directory = Path(output_directory)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint_path = directory / "campaign_checkpoint.json"

    records, cell_metadata = load_table5_campaign_checkpoint(checkpoint_path)

    run_plan = build_default_table5_run_plan()

    if len(run_plan) != TABLE5_CAMPAIGN_POLICY_RUN_COUNT:
        raise RuntimeError("Frozen Table-5 campaign must contain exactly 24 policy runs.")

    (
        inputs_by_cell,
        expected_metadata,
    ) = _build_validated_cell_inputs(
        run_plan,
        records,
        cell_metadata,
    )

    records_by_key = {record.run_key: record for record in records}

    print()
    print("=" * 86)
    print("PHASE 11 TABLE 5 — RESUMABLE 24-RUN CAMPAIGN")
    print("=" * 86)
    print(
        "Existing checkpoint records:",
        len(records),
        "/",
        TABLE5_CAMPAIGN_POLICY_RUN_COUNT,
    )
    print()

    new_runs_completed = 0

    for (
        run_number,
        run_spec,
    ) in enumerate(
        run_plan,
        start=1,
    ):
        existing = records_by_key.get(run_spec.run_key)

        if existing is not None:
            print(f"[{run_number:02d}/24] {run_spec.run_key} — already complete, skip")
            continue

        inputs = inputs_by_cell[run_spec.cell_key]

        cell_metadata[run_spec.cell_key] = dict(expected_metadata[run_spec.cell_key])

        print(
            f"[{run_number:02d}/24] {run_spec.run_key} START",
            flush=True,
        )

        record = execute_table5_campaign_policy(
            inputs,
            run_spec,
        )

        if record.run_key != run_spec.run_key:
            raise RuntimeError("Table-5 executor returned a record for the wrong run.")

        if not record.completed:
            raise RuntimeError("Table-5 executor returned an incomplete successful record.")

        if record.solver_failure_count != 0:
            raise RuntimeError(
                "Table-5 executor returned a successful record containing solver failures."
            )

        records.append(record)

        records_by_key[record.run_key] = record

        ordered = _ordered_records(records)

        # Critical durability boundary:
        # persist this successful policy before
        # any subsequent policy may begin.
        write_table5_campaign_checkpoint(
            list(ordered),
            cell_metadata,
            checkpoint_path,
        )

        new_runs_completed += 1

        print(
            f"[{run_number:02d}/24] "
            f"{run_spec.run_key} DONE "
            f"accepted="
            f"{record.volume_ledger.accepted_volume:.6f} "
            f"net="
            f"{record.volume_ledger.net_value:.6f} "
            f"time="
            f"{record.runtime_seconds:.3f}s",
            flush=True,
        )

        if max_new_runs is not None and new_runs_completed >= max_new_runs:
            print()
            print(f"Reached max_new_runs={max_new_runs}; checkpoint preserved.")
            break

    ordered = _ordered_records(records)

    print()
    print("=" * 86)
    print("TABLE 5 CAMPAIGN STATUS")
    print("=" * 86)
    print(
        "Recorded policy runs:",
        len(ordered),
        "/",
        TABLE5_CAMPAIGN_POLICY_RUN_COUNT,
    )
    print(
        "All campaign runs complete:",
        len(ordered) == TABLE5_CAMPAIGN_POLICY_RUN_COUNT,
    )
    print(
        "Checkpoint:",
        checkpoint_path,
    )

    return ordered
