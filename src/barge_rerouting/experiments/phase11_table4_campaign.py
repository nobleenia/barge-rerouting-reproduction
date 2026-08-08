"""Resumable Phase 11 Table 4 experimental campaign.

This module executes the complete stable-capacity Table 4 matrix:

    2 service families
    x 3 capacities
    x 5 paired demand sets
    x 4 policies
    = 120 policy runs.

Raw policy results are checkpointed after every completed policy run.
Derived paired improvement rates are generated only from complete
four-policy cells. Paper-facing aggregates are generated only when the
full 30-cell campaign is complete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Final

from barge_rerouting.config import (
    ExperimentConfig,
)
from barge_rerouting.experiments.phase11_execution import (
    Phase11EventDisposition,
)
from barge_rerouting.experiments.phase11_forecasts import (
    TABLE4_FORECAST_LOOKAHEAD_PERIODS,
    TABLE4_FORECAST_SELECTION_MODE,
    TABLE4_FORECAST_VALUE_INTERPRETATION,
    Table4ForecastCatalogue,
    build_table4_forecast_catalogue,
    build_table4_forecast_provider,
)
from barge_rerouting.experiments.phase11_pilot import (
    build_table4_controlled_demand_set,
    build_table4_pilot_config,
)
from barge_rerouting.experiments.phase11_policy_execution import (
    Phase11PolicyRun,
    run_phase11_dca,
    run_phase11_dca_r,
    run_phase11_dca_rm,
    run_phase11_dca_rrm,
)
from barge_rerouting.experiments.phase11_services import (
    build_table4_network_config,
)
from barge_rerouting.experiments.phase11_table4 import (
    CONTROLLED_SUBSTITUTE_INPUT,
    TABLE4_POLICY_KEYS,
    Table4CellSpec,
    Table4PolicyRunRecord,
    aggregate_table4_comparisons,
    build_default_table4_cells,
    build_default_table4_run_plan,
    build_table4_paired_comparisons,
    experiment_config_fingerprint,
    write_table4_aggregates_csv,
    write_table4_comparisons_csv,
    write_table4_run_plan_json,
    write_table4_run_records_csv,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
)
from barge_rerouting.rolling_horizon import (
    BookingTimeline,
    build_booking_timeline,
)

TABLE4_CAMPAIGN_TIME_LIMIT_SECONDS: Final = 60.0
TABLE4_CAMPAIGN_RELATIVE_MIP_GAP: Final = 0.0
TABLE4_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class Table4CellInputs:
    """Fully assembled frozen inputs for one paired Table 4 cell."""

    cell: Table4CellSpec
    config: ExperimentConfig
    instance: ExperimentInstance
    timeline: BookingTimeline
    forecast_catalogue: Table4ForecastCatalogue
    configuration_fingerprint: str
    demand_fingerprint: str
    forecast_fingerprint: str


def build_table4_cell_config(
    cell: Table4CellSpec,
) -> ExperimentConfig:
    """Build one controlled Table 4 cell from the frozen pilot config.

    The validated pilot configuration is the canonical Phase 11A
    Table 4 baseline. A campaign cell changes only the experiment
    identity, random seed, service family, and nominal capacity.
    """
    if not isinstance(cell, Table4CellSpec):
        raise TypeError("cell must be a Table4CellSpec.")

    base = build_table4_pilot_config()

    network = build_table4_network_config(
        time_periods=base.network.time_periods,
        service_family=cell.service_family,
        capacity_teu=cell.capacity_teu,
    )

    return replace(
        base,
        experiment_name=(
            f"phase11_table4_{cell.service_family}_capacity{cell.capacity_teu}_{cell.demand_set_id}"
        ),
        random_seed=cell.seed,
        network=network,
    )


def build_table4_cell_inputs(
    cell: Table4CellSpec,
) -> Table4CellInputs:
    """Assemble realised demands, forecasts, network and timeline."""
    if not isinstance(cell, Table4CellSpec):
        raise TypeError("cell must be a Table4CellSpec.")

    demand_set = build_table4_controlled_demand_set(
        seed=cell.seed,
    )

    catalogue = build_table4_forecast_catalogue(
        seed=cell.seed,
    )

    config = build_table4_cell_config(cell)

    instance = assemble_experiment_instance(
        config,
        demands=demand_set.demands,
    )

    if instance.demand_fingerprint != demand_set.demand_fingerprint:
        raise RuntimeError("Assembled Table 4 instance changed the controlled demand fingerprint.")

    timeline = build_booking_timeline(instance)

    return Table4CellInputs(
        cell=cell,
        config=config,
        instance=instance,
        timeline=timeline,
        forecast_catalogue=catalogue,
        configuration_fingerprint=(experiment_config_fingerprint(config)),
        demand_fingerprint=(instance.demand_fingerprint),
        forecast_fingerprint=(catalogue.catalogue_fingerprint),
    )


def _execute_policy(
    inputs: Table4CellInputs,
    policy_key: str,
) -> Phase11PolicyRun:
    """Execute one Phase 11 Table 4 policy."""
    instance = inputs.instance
    timeline = inputs.timeline

    if policy_key == "dca":
        return run_phase11_dca(
            instance,
            timeline=timeline,
        )

    if policy_key == "dca_r":
        return run_phase11_dca_r(
            instance,
            timeline=timeline,
            solver_backend=(SolverBackend.CPLEX_CE_AWARE),
        )

    provider = build_table4_forecast_provider(inputs.forecast_catalogue)

    if policy_key == "dca_rm":
        return run_phase11_dca_rm(
            instance,
            provider,
            value_interpretation=(TABLE4_FORECAST_VALUE_INTERPRETATION),
            selection_mode=(TABLE4_FORECAST_SELECTION_MODE),
            timeline=timeline,
            lookahead_periods=(TABLE4_FORECAST_LOOKAHEAD_PERIODS),
            solver_backend=(SolverBackend.CPLEX_CE_AWARE),
        )

    if policy_key == "dca_rrm":
        return run_phase11_dca_rrm(
            instance,
            provider,
            value_interpretation=(TABLE4_FORECAST_VALUE_INTERPRETATION),
            selection_mode=(TABLE4_FORECAST_SELECTION_MODE),
            timeline=timeline,
            lookahead_periods=(TABLE4_FORECAST_LOOKAHEAD_PERIODS),
            solver_backend=(SolverBackend.CPLEX_CE_AWARE),
        )

    raise ValueError(f"Unsupported Table 4 policy: {policy_key}")


def _run_solver_status(
    run: Phase11PolicyRun,
) -> str:
    """Return stable campaign-level solver status."""
    if run.completed:
        return "all_events_processed"

    for result in run.event_results:
        if result.disposition is Phase11EventDisposition.SOLVER_FAILURE:
            return str(result.solver_status)

    return "run_incomplete"


def run_table4_cell_policy(
    inputs: Table4CellInputs,
    policy_key: str,
) -> Table4PolicyRunRecord:
    """Execute and record one policy in one paired cell."""
    if not isinstance(inputs, Table4CellInputs):
        raise TypeError("inputs must be Table4CellInputs.")

    if policy_key not in TABLE4_POLICY_KEYS:
        raise ValueError(f"Unknown Table 4 policy: {policy_key}")

    start = perf_counter()

    run = _execute_policy(
        inputs,
        policy_key,
    )

    elapsed = perf_counter() - start

    return Table4PolicyRunRecord(
        service_family=inputs.cell.service_family,
        capacity_teu=inputs.cell.capacity_teu,
        demand_set_id=inputs.cell.demand_set_id,
        seed=inputs.cell.seed,
        policy_key=policy_key,
        reproduction_class=(inputs.cell.reproduction_class),
        configuration_fingerprint=(inputs.configuration_fingerprint),
        demand_fingerprint=(inputs.demand_fingerprint),
        completed=run.completed,
        total_revenue=float(run.total_revenue),
        # Table 4 is stable-capacity and truck-disabled.
        transported_volume=float(run.accepted_volume),
        accepted_volume=float(run.accepted_volume),
        solver_status=_run_solver_status(run),
        ordinary_rejection_count=(run.ordinary_rejection_count),
        feasibility_rejection_count=(run.feasibility_rejection_count),
        feasibility_rejected_demand_ids=(run.feasibility_rejected_demand_ids),
        solver_failure_count=(run.solver_failure_count),
        solve_time_seconds=float(elapsed),
        mip_gap=None,
        variable_count=None,
        constraint_count=None,
        solver_node_count=None,
    )


def _record_key(
    record: Table4PolicyRunRecord,
) -> tuple[str, int, str, int, str]:
    return (
        record.service_family,
        record.capacity_teu,
        record.demand_set_id,
        record.seed,
        record.policy_key,
    )


def _cell_key(
    cell: Table4CellSpec,
) -> tuple[str, int, str, int]:
    return (
        cell.service_family,
        cell.capacity_teu,
        cell.demand_set_id,
        cell.seed,
    )


def _cell_slug(
    cell: Table4CellSpec,
) -> str:
    return (
        f"{cell.service_family}"
        f"__capacity_{cell.capacity_teu}"
        f"__{cell.demand_set_id}"
        f"__seed_{cell.seed}"
    )


def _serialisable_record(
    record: Table4PolicyRunRecord,
) -> dict[str, object]:
    """Serialize only constructor fields."""
    return {
        field.name: getattr(record, field.name)
        for field in fields(Table4PolicyRunRecord)
        if field.init
    }


def _restore_record(
    payload: dict[str, Any],
) -> Table4PolicyRunRecord:
    """Restore one validated record from JSON checkpoint."""
    constructor_fields = {field.name for field in fields(Table4PolicyRunRecord) if field.init}

    kwargs: dict[str, Any] = {name: payload[name] for name in constructor_fields if name in payload}

    rejected_ids = kwargs.get(
        "feasibility_rejected_demand_ids",
        (),
    )

    kwargs["feasibility_rejected_demand_ids"] = tuple(rejected_ids)

    return Table4PolicyRunRecord(**kwargs)


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


def load_table4_campaign_checkpoint(
    checkpoint_path: str | Path,
) -> tuple[
    list[Table4PolicyRunRecord],
    dict[str, dict[str, object]],
]:
    """Load campaign state, or return an empty state."""
    path = Path(checkpoint_path)

    if not path.exists():
        return [], {}

    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != TABLE4_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION:
        raise RuntimeError("Unsupported Table 4 campaign checkpoint schema.")

    raw_records = payload.get("records", [])

    if not isinstance(raw_records, list):
        raise TypeError("Checkpoint records must be a list.")

    records = [_restore_record(record) for record in raw_records]

    raw_metadata = payload.get(
        "cell_metadata",
        {},
    )

    if not isinstance(raw_metadata, dict):
        raise TypeError("Checkpoint cell_metadata must be a mapping.")

    metadata: dict[str, dict[str, object]] = {}

    for key, value in raw_metadata.items():
        if not isinstance(key, str):
            raise TypeError("Checkpoint cell metadata keys must be strings.")

        if not isinstance(value, dict):
            raise TypeError("Checkpoint cell metadata values must be mappings.")

        metadata[key] = value

    return records, metadata


def write_table4_campaign_checkpoint(
    records: list[Table4PolicyRunRecord],
    cell_metadata: dict[
        str,
        dict[str, object],
    ],
    checkpoint_path: str | Path,
) -> Path:
    """Atomically persist resumable campaign state."""
    path = Path(checkpoint_path)

    payload: dict[str, object] = {
        "schema_version": (TABLE4_CAMPAIGN_CHECKPOINT_SCHEMA_VERSION),
        "experiment": "phase11_table4_campaign",
        "records": [_serialisable_record(record) for record in records],
        "cell_metadata": cell_metadata,
    }

    _atomic_json_write(
        payload,
        path,
    )

    return path


def _ordered_records(
    records: list[Table4PolicyRunRecord],
) -> tuple[Table4PolicyRunRecord, ...]:
    """Return records in canonical 120-run-plan order."""
    run_plan = build_default_table4_run_plan()

    order = {
        (
            run.service_family,
            run.capacity_teu,
            run.demand_set_id,
            run.seed,
            run.policy_key,
        ): index
        for index, run in enumerate(run_plan)
    }

    return tuple(
        sorted(
            records,
            key=lambda record: order[_record_key(record)],
        )
    )


def _validate_checkpoint_records(
    records: list[Table4PolicyRunRecord],
) -> None:
    """Reject duplicate or foreign checkpoint records."""
    run_plan = build_default_table4_run_plan()

    expected_keys = {
        (
            run.service_family,
            run.capacity_teu,
            run.demand_set_id,
            run.seed,
            run.policy_key,
        )
        for run in run_plan
    }

    seen: set[tuple[str, int, str, int, str]] = set()

    for record in records:
        key = _record_key(record)

        if key not in expected_keys:
            raise RuntimeError(f"Checkpoint contains a run outside the frozen Table 4 plan: {key}")

        if key in seen:
            raise RuntimeError(f"Checkpoint contains duplicate run record: {key}")

        seen.add(key)


def _write_partial_comparisons(
    records: tuple[
        Table4PolicyRunRecord,
        ...,
    ],
    output_path: Path,
) -> int:
    """Write IR rows for complete four-policy cells."""
    grouped: dict[
        tuple[str, int, str, int],
        list[Table4PolicyRunRecord],
    ] = {}

    for record in records:
        grouped.setdefault(
            record.cell_key,
            [],
        ).append(record)

    complete_cell_records: list[Table4PolicyRunRecord] = []

    for cell_records in grouped.values():
        policies = {record.policy_key for record in cell_records if record.completed}

        if policies == set(TABLE4_POLICY_KEYS) and len(cell_records) == len(TABLE4_POLICY_KEYS):
            complete_cell_records.extend(cell_records)

    if not complete_cell_records:
        if output_path.exists():
            output_path.unlink()
        return 0

    comparisons = build_table4_paired_comparisons(
        complete_cell_records,
        require_completed=True,
    )

    write_table4_comparisons_csv(
        comparisons,
        output_path,
    )

    return len(comparisons) // len(TABLE4_POLICY_KEYS)


def _write_campaign_manifest(
    *,
    output_directory: Path,
    records: tuple[
        Table4PolicyRunRecord,
        ...,
    ],
    cell_metadata: dict[
        str,
        dict[str, object],
    ],
) -> Path:
    """Write traceable current campaign status."""
    expected_run_count = len(build_default_table4_run_plan())
    expected_cell_count = len(build_default_table4_cells())

    completed_records = tuple(record for record in records if record.completed)

    a036_by_policy = {
        policy_key: sum(
            record.feasibility_rejection_count
            for record in records
            if record.policy_key == policy_key
        )
        for policy_key in TABLE4_POLICY_KEYS
    }

    ordinary_by_policy = {
        policy_key: sum(
            record.ordinary_rejection_count for record in records if record.policy_key == policy_key
        )
        for policy_key in TABLE4_POLICY_KEYS
    }

    payload: dict[str, object] = {
        "experiment": "phase11_table4_campaign",
        "classification": (CONTROLLED_SUBSTITUTE_INPUT),
        "expected_paired_cell_count": (expected_cell_count),
        "expected_policy_run_count": (expected_run_count),
        "recorded_policy_run_count": len(records),
        "completed_policy_run_count": len(completed_records),
        "all_runs_completed": (len(completed_records) == expected_run_count),
        "solver_backends": {
            "dca": SolverBackend.CPLEX.value,
            "dca_r": SolverBackend.CPLEX_CE_AWARE.value,
            "dca_rm": (SolverBackend.CPLEX_CE_AWARE.value),
            "dca_rrm": (SolverBackend.CPLEX_CE_AWARE.value),
        },
        "ordinary_rejection_count_by_policy": (ordinary_by_policy),
        "a036_feasibility_rejection_count_by_policy": (a036_by_policy),
        "cell_metadata": cell_metadata,
    }

    path = output_directory / "campaign_manifest.json"

    _atomic_json_write(
        payload,
        path,
    )

    return path


def run_table4_campaign(
    *,
    output_directory: str | Path,
    max_new_cells: int | None = None,
) -> tuple[Table4PolicyRunRecord, ...]:
    """Execute or resume the complete Table 4 campaign."""
    if max_new_cells is not None and (
        isinstance(max_new_cells, bool) or not isinstance(max_new_cells, int) or max_new_cells <= 0
    ):
        raise ValueError("max_new_cells must be a positive integer or None.")

    directory = Path(output_directory)

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint_path = directory / "campaign_checkpoint.json"
    raw_path = directory / "table4_policy_runs.csv"
    comparison_path = directory / "table4_paired_comparisons.csv"
    aggregate_path = directory / "table4_aggregates.csv"

    write_table4_run_plan_json(directory / "run_plan.json")

    records, cell_metadata = load_table4_campaign_checkpoint(checkpoint_path)

    _validate_checkpoint_records(records)

    print()
    print("=" * 94)
    print("PHASE 11 TABLE 4 — RESUMABLE 30-CELL CAMPAIGN")
    print("=" * 94)
    print(
        "Existing checkpoint records:",
        len(records),
        "/ 120",
    )
    print()

    new_cells_completed = 0

    cells = build_default_table4_cells()

    for cell_number, cell in enumerate(
        cells,
        start=1,
    ):
        cell_key = _cell_key(cell)

        existing = [record for record in records if record.cell_key == cell_key]

        completed_policies = {record.policy_key for record in existing if record.completed}

        if completed_policies == set(TABLE4_POLICY_KEYS):
            print(
                f"[{cell_number:02d}/30] "
                f"{cell.service_family} | "
                f"{cell.capacity_teu:>2} TEU | "
                f"{cell.demand_set_id} "
                "— already complete, skipping."
            )
            continue

        print()
        print("-" * 94)
        print(
            f"[{cell_number:02d}/30] "
            f"{cell.service_family} | "
            f"{cell.capacity_teu} TEU | "
            f"{cell.demand_set_id} | "
            f"seed {cell.seed}"
        )
        print("-" * 94)

        inputs = build_table4_cell_inputs(cell)

        for record in existing:
            if record.configuration_fingerprint != inputs.configuration_fingerprint:
                raise RuntimeError(
                    f"Checkpoint configuration fingerprint disagrees with current cell {cell_key}."
                )

            if record.demand_fingerprint != inputs.demand_fingerprint:
                raise RuntimeError(
                    f"Checkpoint demand fingerprint disagrees with current cell {cell_key}."
                )

        cell_metadata[_cell_slug(cell)] = {
            "service_family": (cell.service_family),
            "capacity_teu": (cell.capacity_teu),
            "demand_set_id": (cell.demand_set_id),
            "seed": cell.seed,
            "configuration_fingerprint": (inputs.configuration_fingerprint),
            "demand_fingerprint": (inputs.demand_fingerprint),
            "forecast_fingerprint": (inputs.forecast_fingerprint),
            "booking_event_count": (inputs.timeline.event_count),
        }

        for policy_key in TABLE4_POLICY_KEYS:
            current = next(
                (
                    record
                    for record in records
                    if (record.cell_key == cell_key and record.policy_key == policy_key)
                ),
                None,
            )

            if current is not None and current.completed:
                print(f"  {policy_key:<8} already complete — skip")
                continue

            if current is not None:
                records.remove(current)

            print(
                f"  {policy_key:<8} START",
                flush=True,
            )

            record = run_table4_cell_policy(
                inputs,
                policy_key,
            )

            records.append(record)

            ordered = _ordered_records(records)

            write_table4_campaign_checkpoint(
                list(ordered),
                cell_metadata,
                checkpoint_path,
            )

            write_table4_run_records_csv(
                ordered,
                raw_path,
            )

            _write_partial_comparisons(
                ordered,
                comparison_path,
            )

            _write_campaign_manifest(
                output_directory=directory,
                records=ordered,
                cell_metadata=cell_metadata,
            )

            print(
                f"  {policy_key:<8} "
                f"DONE={record.completed!s:<5} "
                f"Revenue={record.total_revenue:>10.2f} "
                f"Volume={record.transported_volume:>7.2f} "
                f"A036={record.feasibility_rejection_count:>2} "
                f"Time={record.solve_time_seconds:>8.3f}s",
                flush=True,
            )

            if not record.completed:
                raise RuntimeError(
                    "Table 4 campaign stopped on "
                    "an incomplete policy run. "
                    "Checkpoint has been written. "
                    f"Cell={cell_key}, "
                    f"policy={policy_key}, "
                    f"status={record.solver_status}"
                )

        cell_records = tuple(record for record in records if record.cell_key == cell_key)

        cell_comparisons = build_table4_paired_comparisons(
            cell_records,
            require_completed=True,
        )

        print()
        print("  DCA-relative IR:")

        for comparison in cell_comparisons:
            print(
                f"    "
                f"{comparison.policy_key:<8} "
                f"Revenue "
                f"{comparison.revenue_ir_percent:+8.3f}% "
                f"Volume "
                f"{comparison.volume_ir_percent:+8.3f}%"
            )

        new_cells_completed += 1

        if max_new_cells is not None and new_cells_completed >= max_new_cells:
            print()
            print(f"Reached max_new_cells={max_new_cells}; checkpoint preserved.")
            break

    ordered = _ordered_records(records)

    write_table4_campaign_checkpoint(
        list(ordered),
        cell_metadata,
        checkpoint_path,
    )

    write_table4_run_records_csv(
        ordered,
        raw_path,
    )

    complete_cell_count = _write_partial_comparisons(
        ordered,
        comparison_path,
    )

    all_completed = len(ordered) == len(build_default_table4_run_plan()) and all(
        record.completed for record in ordered
    )

    if all_completed:
        comparisons = build_table4_paired_comparisons(
            ordered,
            require_completed=True,
        )

        aggregates = aggregate_table4_comparisons(comparisons)

        write_table4_comparisons_csv(
            comparisons,
            comparison_path,
        )

        write_table4_aggregates_csv(
            aggregates,
            aggregate_path,
        )

    _write_campaign_manifest(
        output_directory=directory,
        records=ordered,
        cell_metadata=cell_metadata,
    )

    print()
    print("=" * 94)
    print("CAMPAIGN STATUS")
    print("=" * 94)
    print(
        "Completed cells:",
        complete_cell_count,
        "/ 30",
    )
    print(
        "Recorded policy runs:",
        len(ordered),
        "/ 120",
    )
    print(
        "All campaign runs complete:",
        all_completed,
    )
    print(
        "Raw records:",
        raw_path,
    )
    print(
        "Checkpoint:",
        checkpoint_path,
    )
    print(
        "Paired comparisons:",
        comparison_path,
    )

    if all_completed:
        print(
            "Aggregates:",
            aggregate_path,
        )

    return ordered
