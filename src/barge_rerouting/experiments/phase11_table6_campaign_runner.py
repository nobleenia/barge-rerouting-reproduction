"""Resumable 24-run Phase-11C Table-6 production runner."""

from __future__ import annotations

import json
import os
import subprocess
from math import isclose
from pathlib import Path
from typing import Final

from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCellInputs,
)
from barge_rerouting.experiments.phase11_table6_campaign import (
    Table6CampaignRunInputs,
    build_default_table6_new_run_plan,
    build_table6_base_inputs,
    build_table6_campaign_run_inputs,
)
from barge_rerouting.experiments.phase11_table6_campaign_execution import (
    execute_table6_campaign_run,
)
from barge_rerouting.reporting.table5_campaign_record import (
    TABLE5_CAMPAIGN_RECORD_SCHEMA,
    Table5CampaignPolicyRecord,
)

TABLE6_PERSISTED_RECORD_SCHEMA: Final = "table6-policy-record-v1"

_TABLE6_RUN_COUNT: Final = 24


def _validate_max_new_runs(
    max_new_runs: int | None,
) -> None:
    if max_new_runs is None:
        return

    if isinstance(max_new_runs, bool) or not isinstance(max_new_runs, int) or max_new_runs <= 0:
        raise ValueError("max_new_runs must be a positive integer or None.")


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _atomic_write_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    temporary.replace(path)


def _record_payload(
    *,
    record: Table5CampaignPolicyRecord,
    inputs: Table6CampaignRunInputs,
    source_commit: str,
) -> dict[str, object]:
    run_spec = inputs.run_spec

    return {
        "schema_version": TABLE6_PERSISTED_RECORD_SCHEMA,
        "experiment": "phase11_table6_campaign",
        "reporting_schema_version": TABLE5_CAMPAIGN_RECORD_SCHEMA,
        "source_commit": source_commit,
        "run_key": run_spec.run_key,
        "cell_key": run_spec.cell_key,
        "service_family": run_spec.service_family,
        "capacity_teu": run_spec.capacity_teu,
        "policy_key": run_spec.policy_key,
        "water_factor": run_spec.water_factor,
        "reproduction_class": run_spec.reproduction_class,
        "base_configuration_fingerprint": inputs.base_configuration_fingerprint,
        "scenario_fingerprint": inputs.scenario_fingerprint,
        "demand_fingerprint": inputs.demand_fingerprint,
        "completed": record.completed,
        "record": record.to_mapping(),
    }


def _validate_existing_payload(
    payload: dict[str, object],
    inputs: Table6CampaignRunInputs,
) -> None:
    run_spec = inputs.run_spec

    expected = {
        "schema_version": TABLE6_PERSISTED_RECORD_SCHEMA,
        "experiment": "phase11_table6_campaign",
        "reporting_schema_version": TABLE5_CAMPAIGN_RECORD_SCHEMA,
        "run_key": run_spec.run_key,
        "cell_key": run_spec.cell_key,
        "service_family": run_spec.service_family,
        "capacity_teu": run_spec.capacity_teu,
        "policy_key": run_spec.policy_key,
        "reproduction_class": run_spec.reproduction_class,
        "base_configuration_fingerprint": inputs.base_configuration_fingerprint,
        "scenario_fingerprint": inputs.scenario_fingerprint,
        "demand_fingerprint": inputs.demand_fingerprint,
        "completed": True,
    }

    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise RuntimeError(
                "Persisted Table-6 record disagrees "
                f"with frozen inputs for {run_spec.run_key}: "
                f"{key}."
            )

    water = payload.get("water_factor")

    if (
        isinstance(water, bool)
        or not isinstance(water, (int, float))
        or not isclose(
            float(water),
            run_spec.water_factor,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    ):
        raise RuntimeError("Persisted Table-6 water factor changed.")

    if not isinstance(
        payload.get("record"),
        dict,
    ):
        raise RuntimeError("Persisted Table-6 rich record is missing.")


def _load_existing(
    path: Path,
    inputs: Table6CampaignRunInputs,
) -> bool:
    if not path.exists():
        return False

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid Table-6 record file: {path}.")

    _validate_existing_payload(
        payload,
        inputs,
    )

    return True


def run_table6_campaign(
    *,
    output_directory: str | Path,
    max_new_runs: int | None = None,
) -> tuple[str, ...]:
    """Execute or resume the 24 new reduced-water PR rows."""
    _validate_max_new_runs(max_new_runs)

    directory = Path(output_directory)
    records_directory = directory / "records"
    prevalidation_directory = directory / "prevalidation"

    records_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    prevalidation_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_plan = build_default_table6_new_run_plan()

    if len(run_plan) != _TABLE6_RUN_COUNT:
        raise RuntimeError("Frozen Table-6 run plan changed.")

    source_commit = _git_head()

    base_cache: dict[
        str,
        Table5CampaignCellInputs,
    ] = {}

    completed_keys: list[str] = []
    newly_completed = 0

    print()
    print("=" * 88)
    print("PHASE 11 TABLE 6 — RESUMABLE 24-RUN REDUCED-WATER PR CAMPAIGN")
    print("=" * 88)
    print(f"source commit: {source_commit}")
    print()

    for position, run_spec in enumerate(
        run_plan,
        start=1,
    ):
        base = base_cache.get(run_spec.base_cell_key)

        if base is None:
            base = build_table6_base_inputs(run_spec)
            base_cache[run_spec.base_cell_key] = base

        inputs = build_table6_campaign_run_inputs(
            run_spec,
            base_inputs=base,
        )

        record_path = records_directory / f"{run_spec.run_key}.json"

        if _load_existing(
            record_path,
            inputs,
        ):
            completed_keys.append(run_spec.run_key)
            print(f"[{position:02d}/24] SKIP {run_spec.run_key}")
            continue

        if max_new_runs is not None and newly_completed >= max_new_runs:
            break

        print(f"[{position:02d}/24] RUN  {run_spec.run_key}")

        prevalidation_path = prevalidation_directory / f"{run_spec.run_key}.json"

        record = execute_table6_campaign_run(
            inputs,
            prevalidation_path=prevalidation_path,
        )

        payload = _record_payload(
            record=record,
            inputs=inputs,
            source_commit=source_commit,
        )

        _atomic_write_json(
            record_path,
            payload,
        )

        completed_keys.append(run_spec.run_key)
        newly_completed += 1

        print(
            f"         PASS "
            f"time={record.runtime_seconds:.3f}s "
            f"accepted="
            f"{record.volume_ledger.accepted_volume:.3f} "
            f"truck="
            f"{record.volume_ledger.truck_volume:.3f}"
        )

    existing_count = sum(
        1 for run_spec in run_plan if (records_directory / f"{run_spec.run_key}.json").exists()
    )

    print()
    print(f"Persisted completed rows: {existing_count} / 24")

    return tuple(completed_keys)
