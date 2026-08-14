from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from barge_rerouting.experiments.phase11_table5_campaign import (
    build_default_table5_run_plan,
)
from barge_rerouting.experiments.phase11_table5_checkpoint import (
    load_table5_campaign_checkpoint,
)

BASE = Path("results/phase11/table5/campaign")
CHECKPOINT = BASE / "campaign_checkpoint.json"
PREVALIDATION = BASE / "prevalidation"

POLICY_RUNS_PATH = BASE / "table5_policy_runs.csv"
COMPARISON_PATH = BASE / "table5_published_comparison.csv"
MANIFEST_PATH = BASE / "campaign_manifest.json"
RUN_PLAN_PATH = BASE / "run_plan.json"

LEGACY_WITHOUT_PREVALIDATION = {
    "service_family_1__capacity_10__dca",
    "service_family_1__capacity_10__pr",
}

# Literal values transcribed from the publication's Table 5.
# The Service-1 / capacity-40 / PR AFR value is deliberately retained
# as 855 exactly as printed.
PUBLISHED_TABLE5: dict[
    tuple[int, int, str],
    dict[str, float | str],
] = {
    (1, 10, "dca"): {
        "afr": 100,
        "vtr": "",
        "vfb": 35,
        "vob": 35,
        "voa": 42,
        "tr": 716,
        "st": 18,
    },
    (1, 10, "pr"): {
        "afr": 98,
        "vtr": 2,
        "vfb": 35,
        "vob": 37,
        "voa": 44,
        "tr": 746,
        "st": 40,
    },
    (1, 10, "fr"): {
        "afr": 100,
        "vtr": 37,
        "vfb": 25,
        "vob": 62,
        "voa": 53,
        "tr": 1735,
        "st": 788,
    },
    (1, 20, "dca"): {
        "afr": 97,
        "vtr": "",
        "vfb": 57,
        "vob": 57,
        "voa": 53,
        "tr": 2184,
        "st": 18,
    },
    (1, 20, "pr"): {
        "afr": 96,
        "vtr": 3,
        "vfb": 56,
        "vob": 59,
        "voa": 56,
        "tr": 2320,
        "st": 64,
    },
    (1, 20, "fr"): {
        "afr": 98,
        "vtr": 35,
        "vfb": 43,
        "vob": 78,
        "voa": 66,
        "tr": 3681,
        "st": 1380,
    },
    (1, 30, "dca"): {
        "afr": 90,
        "vtr": "",
        "vfb": 70,
        "vob": 70,
        "voa": 62,
        "tr": 3570,
        "st": 19,
    },
    (1, 30, "pr"): {
        "afr": 90,
        "vtr": 1,
        "vfb": 70,
        "vob": 71,
        "voa": 63,
        "tr": 3659,
        "st": 84,
    },
    (1, 30, "fr"): {
        "afr": 97,
        "vtr": 25,
        "vfb": 59,
        "vob": 83,
        "voa": 73,
        "tr": 5191,
        "st": 1975,
    },
    (1, 40, "dca"): {
        "afr": 83,
        "vtr": "",
        "vfb": 77,
        "vob": 77,
        "voa": 69,
        "tr": 4667,
        "st": 19,
    },
    (1, 40, "pr"): {
        "afr": 855,
        "vtr": 1,
        "vfb": 78,
        "vob": 79,
        "voa": 71,
        "tr": 4875,
        "st": 89,
    },
    (1, 40, "fr"): {
        "afr": 92,
        "vtr": 13,
        "vfb": 73,
        "vob": 86,
        "voa": 78,
        "tr": 6112,
        "st": 2555,
    },
    (2, 10, "dca"): {
        "afr": 99,
        "vtr": "",
        "vfb": 56,
        "vob": 56,
        "voa": 53,
        "tr": 2054,
        "st": 20,
    },
    (2, 10, "pr"): {
        "afr": 98,
        "vtr": 9,
        "vfb": 52,
        "vob": 61,
        "voa": 56,
        "tr": 2572,
        "st": 78,
    },
    (2, 10, "fr"): {
        "afr": 100,
        "vtr": 46,
        "vfb": 38,
        "vob": 84,
        "voa": 72,
        "tr": 4211,
        "st": 2240,
    },
    (2, 20, "dca"): {
        "afr": 93,
        "vtr": "",
        "vfb": 81,
        "vob": 81,
        "voa": 72,
        "tr": 5034,
        "st": 22,
    },
    (2, 20, "pr"): {
        "afr": 93,
        "vtr": 6,
        "vfb": 76,
        "vob": 83,
        "voa": 75,
        "tr": 5492,
        "st": 128,
    },
    (2, 20, "fr"): {
        "afr": 98,
        "vtr": 29,
        "vfb": 65,
        "vob": 94,
        "voa": 86,
        "tr": 7716,
        "st": 4007,
    },
    (2, 30, "dca"): {
        "afr": 82,
        "vtr": "",
        "vfb": 92,
        "vob": 92,
        "voa": 83,
        "tr": 7641,
        "st": 23,
    },
    (2, 30, "pr"): {
        "afr": 84,
        "vtr": 2,
        "vfb": 91,
        "vob": 93,
        "voa": 85,
        "tr": 7986,
        "st": 160,
    },
    (2, 30, "fr"): {
        "afr": 90,
        "vtr": 17,
        "vfb": 82,
        "vob": 98,
        "voa": 93,
        "tr": 9502,
        "st": 5057,
    },
    (2, 40, "dca"): {
        "afr": 71,
        "vtr": "",
        "vfb": 97,
        "vob": 97,
        "voa": 91,
        "tr": 9292,
        "st": 22,
    },
    (2, 40, "pr"): {
        "afr": 75,
        "vtr": 1,
        "vfb": 97,
        "vob": 98,
        "voa": 92,
        "tr": 9363,
        "st": 175,
    },
    (2, 40, "fr"): {
        "afr": 78,
        "vtr": 6,
        "vfb": 93,
        "vob": 99,
        "voa": 96,
        "tr": 10115,
        "st": 4122,
    },
}


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise RuntimeError(f"No rows supplied for {path}.")

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def delta(
    controlled: float,
    published: float | str,
) -> float | str:
    if published == "":
        return ""

    return controlled - float(published)


records, cell_metadata = load_table5_campaign_checkpoint(CHECKPOINT)

run_plan = build_default_table5_run_plan()

assert len(records) == 24
assert len(run_plan) == 24
assert len(cell_metadata) == 8

records_by_key = {record.run_key: record for record in records}

assert set(records_by_key) == {run.run_key for run in run_plan}

policy_rows: list[dict[str, Any]] = []
comparison_rows: list[dict[str, Any]] = []

for planned in run_plan:
    record = records_by_key[planned.run_key]

    ledger = record.volume_ledger
    fill = record.indicator_snapshot.fill_rate_candidates
    volume = record.indicator_snapshot.volume_indicator_candidates

    service_number = int(record.service_family.removeprefix("service_family_"))

    prevalidation_path = PREVALIDATION / f"{record.run_key}.json"

    policy_row = {
        "run_key": record.run_key,
        "service_family": record.service_family,
        "capacity_teu": record.capacity_teu,
        "policy_key": record.policy_key,
        "reproduction_class": planned.reproduction_class,
        "configuration_fingerprint": record.configuration_fingerprint,
        "demand_fingerprint": record.demand_fingerprint,
        "solver_backend": record.solver_backend,
        "completed": record.completed,
        "requested_request_count": ledger.requested_request_count,
        "accepted_request_count": ledger.accepted_request_count,
        "processed_booking_count": record.processed_booking_count,
        "processed_status_count": record.processed_status_count,
        "ordinary_rejection_count": record.ordinary_rejection_count,
        "feasibility_rejection_count": record.feasibility_rejection_count,
        "solver_failure_count": record.solver_failure_count,
        "requested_volume_teu": ledger.requested_volume,
        "accepted_volume_teu": ledger.accepted_volume,
        "final_barge_volume_teu": ledger.final_barge_volume,
        "truck_volume_teu": ledger.truck_volume,
        "gross_revenue": ledger.gross_revenue,
        "truck_penalty": ledger.truck_penalty,
        "net_revenue": ledger.net_value,
        "afr_arc_pct": fill.mean_arc_actual_pct,
        "nfr_arc_pct": fill.mean_arc_nominal_pct,
        "afr_weighted_pct": fill.capacity_weighted_actual_pct,
        "nfr_weighted_pct": fill.capacity_weighted_nominal_pct,
        "afr_sailing_peak_pct": fill.mean_sailing_peak_actual_pct,
        "nfr_sailing_peak_pct": fill.mean_sailing_peak_nominal_pct,
        "vtr_pct": volume.vtr_requested_volume_pct,
        "vfb_pct": volume.vfb_requested_volume_pct,
        "vob_pct": volume.vob_requested_volume_pct,
        "voa_count_pct": volume.voa_request_count_pct,
        "voa_volume_pct": volume.voa_requested_volume_pct,
        "solving_time_seconds": record.runtime_seconds,
        "prevalidation_available": prevalidation_path.exists(),
    }

    policy_rows.append(policy_row)

    published = PUBLISHED_TABLE5[
        (
            service_number,
            record.capacity_teu,
            record.policy_key,
        )
    ]

    afr_note = ""

    if service_number == 1 and record.capacity_teu == 40 and record.policy_key == "pr":
        afr_note = "Table 5 prints 855; retained literally. Table 6 standard-water row prints 85."

    comparison_rows.append(
        {
            "service_family": record.service_family,
            "capacity_teu": record.capacity_teu,
            "policy_key": record.policy_key,
            "paper_afr_pct": published["afr"],
            "paper_vtr_pct": published["vtr"],
            "paper_vfb_pct": published["vfb"],
            "paper_vob_pct": published["vob"],
            "paper_voa_pct": published["voa"],
            "paper_tr": published["tr"],
            "paper_st_seconds": published["st"],
            "paper_afr_note": afr_note,
            "controlled_afr_arc_pct": fill.mean_arc_actual_pct,
            "controlled_vtr_pct": volume.vtr_requested_volume_pct,
            "controlled_vfb_pct": volume.vfb_requested_volume_pct,
            "controlled_vob_pct": volume.vob_requested_volume_pct,
            "controlled_voa_count_pct": volume.voa_request_count_pct,
            "controlled_gross_revenue": ledger.gross_revenue,
            "controlled_net_revenue": ledger.net_value,
            "controlled_st_seconds": record.runtime_seconds,
            "afr_delta_pp": delta(
                fill.mean_arc_actual_pct,
                published["afr"],
            ),
            "vtr_delta_pp": delta(
                volume.vtr_requested_volume_pct,
                published["vtr"],
            ),
            "vfb_delta_pp": delta(
                volume.vfb_requested_volume_pct,
                published["vfb"],
            ),
            "vob_delta_pp": delta(
                volume.vob_requested_volume_pct,
                published["vob"],
            ),
            "voa_count_delta_pp": delta(
                volume.voa_request_count_pct,
                published["voa"],
            ),
            "gross_revenue_minus_paper_tr": ledger.gross_revenue - float(published["tr"]),
            "net_revenue_minus_paper_tr": ledger.net_value - float(published["tr"]),
            "runtime_minus_paper_st_seconds": record.runtime_seconds - float(published["st"]),
        }
    )

assert len(policy_rows) == 24
assert len(comparison_rows) == 24
assert len(PUBLISHED_TABLE5) == 24

write_csv(
    POLICY_RUNS_PATH,
    policy_rows,
)

write_csv(
    COMPARISON_PATH,
    comparison_rows,
)

run_plan_payload = {
    "experiment": "phase11_table5",
    "reproduction_class": "controlled_substitute_input",
    "service_families": [
        "service_family_1",
        "service_family_2",
    ],
    "capacities_teu": [
        10,
        20,
        30,
        40,
    ],
    "policy_keys": [
        "dca",
        "pr",
        "fr",
    ],
    "structural_cell_count": 8,
    "policy_run_count": 24,
    "run_plan": [
        {
            "run_key": run.run_key,
            "cell_key": run.cell_key,
            "service_family": run.service_family,
            "capacity_teu": run.capacity_teu,
            "policy_key": run.policy_key,
            "reproduction_class": run.reproduction_class,
        }
        for run in run_plan
    ],
}

RUN_PLAN_PATH.write_text(
    json.dumps(
        run_plan_payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

runtime_by_policy: dict[str, float] = defaultdict(float)
ordinary_by_policy: dict[str, int] = defaultdict(int)
a036_by_policy: dict[str, int] = defaultdict(int)

solver_backends: dict[str, set[str]] = defaultdict(set)

for record in records:
    runtime_by_policy[record.policy_key] += record.runtime_seconds

    ordinary_by_policy[record.policy_key] += record.ordinary_rejection_count

    a036_by_policy[record.policy_key] += record.feasibility_rejection_count

    solver_backends[record.policy_key].add(record.solver_backend)

prevalidation_keys = {path.stem for path in PREVALIDATION.glob("*.json")}

expected_keys = {run.run_key for run in run_plan}

missing_prevalidation = expected_keys - prevalidation_keys

assert missing_prevalidation == LEGACY_WITHOUT_PREVALIDATION

source_commit = subprocess.check_output(
    [
        "git",
        "rev-parse",
        "HEAD",
    ],
    text=True,
).strip()

manifest = {
    "experiment": "phase11_table5_campaign",
    "classification": "controlled_substitute_input",
    "all_runs_completed": all(record.completed for record in records),
    "expected_policy_run_count": 24,
    "recorded_policy_run_count": len(records),
    "completed_policy_run_count": sum(record.completed for record in records),
    "structural_cell_count": len(cell_metadata),
    "cell_metadata": cell_metadata,
    "source_commit": source_commit,
    "checkpoint_sha256": sha256(CHECKPOINT),
    "prevalidation_artifact_count": len(prevalidation_keys),
    "legacy_runs_without_prevalidation": sorted(LEGACY_WITHOUT_PREVALIDATION),
    "solver_backends_by_policy": {
        policy: sorted(backends) for policy, backends in sorted(solver_backends.items())
    },
    "ordinary_rejection_count_by_policy": dict(sorted(ordinary_by_policy.items())),
    "a036_feasibility_rejection_count_by_policy": dict(sorted(a036_by_policy.items())),
    "runtime_seconds_by_policy": {
        policy: runtime for policy, runtime in sorted(runtime_by_policy.items())
    },
    "runtime_hours_by_policy": {
        policy: runtime / 3600.0 for policy, runtime in sorted(runtime_by_policy.items())
    },
    "demand_fingerprints": sorted({record.demand_fingerprint for record in records}),
    "configuration_fingerprints": sorted({record.configuration_fingerprint for record in records}),
    "publication_table5_literal_afr_anomaly": {
        "service_family": "service_family_1",
        "capacity_teu": 40,
        "policy_key": "pr",
        "table5_printed_afr_pct": 855,
        "table6_standard_water_afr_pct": 85,
        "treatment": "retain Table 5 value literally; do not silently correct",
    },
    "global_audit": "results/phase11/table5/campaign/audit/global_campaign_audit.txt",
    "evidence_sha256_manifest": "results/phase11/table5/campaign/audit/evidence_sha256.txt",
}

MANIFEST_PATH.write_text(
    json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)

print(f"Wrote {POLICY_RUNS_PATH}")
print(f"Wrote {COMPARISON_PATH}")
print(f"Wrote {RUN_PLAN_PATH}")
print(f"Wrote {MANIFEST_PATH}")

print()
print(
    "Policy rows:",
    len(policy_rows),
)
print(
    "Published comparison rows:",
    len(comparison_rows),
)
print(
    "Prevalidation:",
    len(prevalidation_keys),
    "/ 24",
)
print(
    "Checkpoint SHA-256:",
    sha256(CHECKPOINT),
)
