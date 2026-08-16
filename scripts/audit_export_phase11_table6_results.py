"""Audit and export the completed Phase-11C Table-6 campaign."""

from __future__ import annotations

import csv
import hashlib
import json
from math import fsum, isclose
from pathlib import Path
from statistics import fmean
from typing import Any

BASE = Path("results/phase11/table6/campaign")
RECORDS = BASE / "records"
PREVALIDATION = BASE / "prevalidation"
AUDIT = BASE / "audit"

TABLE5_BASE = Path("results/phase11/table5/campaign")
TABLE5_POLICY_RUNS = TABLE5_BASE / "table5_policy_runs.csv"
TABLE5_MANIFEST = TABLE5_BASE / "campaign_manifest.json"

CONTROLLED_PATH = BASE / "table6_policy_rows.csv"
COMPARISON_PATH = BASE / "table6_published_comparison.csv"
WATER_EFFECTS_PATH = BASE / "table6_water_effects.csv"
RUN_PLAN_PATH = BASE / "run_plan.json"
MANIFEST_PATH = BASE / "campaign_manifest.json"

AUDIT_PATH = AUDIT / "global_campaign_audit.txt"
HASH_PATH = AUDIT / "evidence_sha256.txt"

DEMAND_FINGERPRINT = "9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944"

VOLUME_TOLERANCE = 1.0e-6
REPORTING_TOLERANCE = 1.0e-6
CAPACITY_TOLERANCE = 1.0e-5
PREVALIDATION_TOLERANCE = 1.0e-9


# Literal transcription of the paper's Table 6.
#
# Columns:
# service, capacity, water, AFR, NFR, VT, VFB, VOB
#
# IMPORTANT:
# Service 1 / capacity 40 / water 0.9 prints NFR = 8.
# That value is intentionally preserved rather than corrected.
PUBLISHED_ROWS = (
    (1, 10, 1.0, 98, 98, 2, 35, 37),
    (1, 10, 0.9, 99, 89, 7, 31, 37),
    (1, 10, 0.8, 100, 80, 11, 26, 37),
    (1, 10, 0.7, 99, 69, 16, 22, 38),
    (1, 20, 1.0, 96, 96, 3, 56, 59),
    (1, 20, 0.9, 97, 87, 9, 49, 59),
    (1, 20, 0.8, 98, 79, 16, 43, 59),
    (1, 20, 0.7, 98, 69, 22, 37, 59),
    (1, 30, 1.0, 90, 90, 1, 70, 71),
    (1, 30, 0.9, 94, 84, 7, 62, 69),
    (1, 30, 0.8, 96, 76, 15, 54, 69),
    (1, 30, 0.7, 96, 67, 22, 47, 69),
    (1, 40, 1.0, 85, 85, 1, 78, 79),
    (1, 40, 0.9, 89, 8, 7, 71, 78),
    (1, 40, 0.8, 93, 75, 13, 64, 77),
    (1, 40, 0.7, 95, 67, 22, 54, 77),
    (2, 10, 1.0, 98, 98, 9, 52, 61),
    (2, 10, 0.9, 99, 90, 10, 48, 58),
    (2, 10, 0.8, 100, 80, 15, 42, 57),
    (2, 10, 0.7, 99, 69, 20, 38, 58),
    (2, 20, 1.0, 93, 93, 6, 76, 83),
    (2, 20, 0.9, 96, 87, 9, 72, 81),
    (2, 20, 0.8, 99, 79, 14, 64, 79),
    (2, 20, 0.7, 99, 69, 24, 55, 79),
    (2, 30, 1.0, 84, 84, 2, 91, 93),
    (2, 30, 0.9, 91, 82, 5, 87, 92),
    (2, 30, 0.8, 94, 75, 13, 78, 91),
    (2, 30, 0.7, 97, 68, 20, 70, 90),
    (2, 40, 1.0, 75, 75, 1, 97, 98),
    (2, 40, 0.9, 82, 73, 2, 95, 97),
    (2, 40, 0.8, 87, 70, 7, 89, 96),
    (2, 40, 0.7, 92, 65, 16, 79, 95),
)

PUBLISHED = {
    (
        f"service_family_{service}",
        capacity,
        water,
    ): {
        "afr": afr,
        "nfr": nfr,
        "vt": vt,
        "vfb": vfb,
        "vob": vob,
    }
    for (
        service,
        capacity,
        water,
        afr,
        nfr,
        vt,
        vfb,
        vob,
    ) in PUBLISHED_ROWS
}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object in {path}.")

    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _assert_close(
    actual: float,
    expected: float,
    *,
    tolerance: float = REPORTING_TOLERANCE,
    message: str,
) -> None:
    if not isclose(
        float(actual),
        float(expected),
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise RuntimeError(f"{message}: actual={actual}, expected={expected}.")


def _pct(
    numerator: float,
    denominator: float,
) -> float:
    if denominator == 0.0:
        return 0.0

    return float(100.0 * numerator / denominator)


def _write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise RuntimeError(f"Cannot write empty CSV: {path}.")

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


def _audit_prevalidation(
    path: Path,
    *,
    expected_run_key: str,
) -> None:
    payload = _read_json(path)

    if payload.get("status") != "validated":
        raise RuntimeError(f"Prevalidation not validated: {path}.")

    if payload.get("completed") is not True:
        raise RuntimeError(f"Prevalidation not completed: {path}.")

    if payload.get("run_key") != expected_run_key:
        raise RuntimeError(f"Prevalidation run key disagrees: {path}.")

    residuals = payload.get("cross_validation_residuals")

    if not isinstance(residuals, dict):
        raise RuntimeError(f"Missing prevalidation residuals: {path}.")

    required = {
        "accepted_volume",
        "final_barge_volume",
        "requested_booking_count",
        "requested_volume",
        "truck_penalty",
        "truck_volume",
    }

    if set(residuals) != required:
        raise RuntimeError(
            "Unexpected prevalidation residual contract "
            f"for {expected_run_key}: {sorted(residuals)}."
        )

    for name, value in residuals.items():
        if abs(float(value)) > PREVALIDATION_TOLERANCE:
            raise RuntimeError(
                f"Prevalidation residual failed for {expected_run_key}: {name}={value}."
            )


def _audit_reduced_record(
    wrapper: dict[str, Any],
) -> dict[str, Any]:
    run_key = str(wrapper["run_key"])

    if wrapper["completed"] is not True:
        raise RuntimeError(f"Incomplete Table-6 run: {run_key}.")

    if wrapper["experiment"] != ("phase11_table6_campaign"):
        raise RuntimeError(f"Foreign experiment record: {run_key}.")

    if wrapper["policy_key"] != "pr":
        raise RuntimeError(f"Non-PR Table-6 record: {run_key}.")

    water_factor = float(wrapper["water_factor"])

    if water_factor not in {
        0.9,
        0.8,
        0.7,
    }:
        raise RuntimeError(f"Unexpected reduced-water factor: {run_key}.")

    if wrapper["demand_fingerprint"] != (DEMAND_FINGERPRINT):
        raise RuntimeError(f"Demand fingerprint changed: {run_key}.")

    record = wrapper["record"]

    if not isinstance(record, dict):
        raise RuntimeError(f"Missing rich record: {run_key}.")

    if record["run_key"] != run_key:
        raise RuntimeError(f"Nested run key changed: {run_key}.")

    if record["cell_key"] != wrapper["cell_key"]:
        raise RuntimeError(f"Nested cell key changed: {run_key}.")

    if record["service_family"] != (wrapper["service_family"]):
        raise RuntimeError(f"Nested service family changed: {run_key}.")

    if int(record["capacity_teu"]) != int(wrapper["capacity_teu"]):
        raise RuntimeError(f"Nested capacity changed: {run_key}.")

    if record["configuration_fingerprint"] != (wrapper["scenario_fingerprint"]):
        raise RuntimeError(f"Scenario fingerprint changed: {run_key}.")

    if record["demand_fingerprint"] != (DEMAND_FINGERPRINT):
        raise RuntimeError(f"Nested demand fingerprint changed: {run_key}.")

    if record["completed"] is not True:
        raise RuntimeError(f"Nested record incomplete: {run_key}.")

    if record["policy_key"] != "pr":
        raise RuntimeError(f"Nested policy changed: {run_key}.")

    if int(record["requested_booking_count"]) != 800:
        raise RuntimeError(f"Requested booking count changed: {run_key}.")

    if int(record["processed_booking_count"]) != 800:
        raise RuntimeError(f"Not all bookings processed: {run_key}.")

    if int(record["processed_status_count"]) != 20:
        raise RuntimeError(f"Not all status updates processed: {run_key}.")

    if int(record["solver_failure_count"]) != 0:
        raise RuntimeError(f"Solver failure recorded: {run_key}.")

    ledger = record["volume_ledger"]

    requested_count = int(ledger["requested_request_count"])
    accepted_count = int(ledger["accepted_request_count"])

    requested_volume = float(ledger["requested_volume"])
    accepted_volume = float(ledger["accepted_volume"])
    final_barge_volume = float(ledger["final_barge_volume"])
    truck_volume = float(ledger["truck_volume"])

    gross_revenue = float(ledger["gross_revenue"])
    truck_penalty = float(ledger["truck_penalty"])
    net_value = float(ledger["net_value"])

    if requested_count != 800:
        raise RuntimeError(f"Ledger request count changed: {run_key}.")

    _assert_close(
        requested_volume,
        1076.0,
        message=(f"Requested volume changed for {run_key}"),
    )

    _assert_close(
        accepted_volume,
        final_barge_volume + truck_volume,
        tolerance=VOLUME_TOLERANCE,
        message=(f"Accepted-volume conservation failed for {run_key}"),
    )

    _assert_close(
        net_value,
        gross_revenue - truck_penalty,
        tolerance=VOLUME_TOLERANCE,
        message=(f"Economic conservation failed for {run_key}"),
    )

    capacity = record["service_capacity_snapshot"]

    if capacity["instance_fingerprint"] != (DEMAND_FINGERPRINT):
        raise RuntimeError(f"Capacity fingerprint changed: {run_key}.")

    arcs = capacity["arcs"]

    if not isinstance(arcs, list) or not arcs:
        raise RuntimeError(f"Missing capacity arcs: {run_key}.")

    max_capacity_violation = 0.0

    actual_ratios: list[float] = []
    nominal_ratios: list[float] = []

    actual_capacity_total = 0.0
    nominal_capacity_total = 0.0
    final_load_total = 0.0

    for arc in arcs:
        nominal = float(arc["nominal_capacity"])
        actual = float(arc["actual_capacity"])
        final_load = float(arc["final_load"])

        _assert_close(
            actual,
            water_factor * nominal,
            tolerance=REPORTING_TOLERANCE,
            message=(f"Historical actual capacity failed for {run_key}"),
        )

        violation = max(
            0.0,
            final_load - actual,
        )

        max_capacity_violation = max(
            max_capacity_violation,
            violation,
        )

        if violation > CAPACITY_TOLERANCE:
            raise RuntimeError(f"Actual-capacity overload for {run_key}: {violation}.")

        if actual > 0.0:
            actual_ratios.append(final_load / actual)

        if nominal > 0.0:
            nominal_ratios.append(final_load / nominal)

        actual_capacity_total += actual
        nominal_capacity_total += nominal
        final_load_total += final_load

    recomputed_afr_arc = 100.0 * fmean(actual_ratios) if actual_ratios else 0.0

    recomputed_nfr_arc = 100.0 * fmean(nominal_ratios) if nominal_ratios else 0.0

    recomputed_afr_weighted = _pct(
        final_load_total,
        actual_capacity_total,
    )

    recomputed_nfr_weighted = _pct(
        final_load_total,
        nominal_capacity_total,
    )

    indicators = record["indicator_snapshot"]

    if indicators["standard_water"] is not False:
        raise RuntimeError(f"Reduced-water run marked standard: {run_key}.")

    fill = indicators["fill_rate_candidates"]

    afr_arc = float(fill["mean_arc_actual_pct"])
    nfr_arc = float(fill["mean_arc_nominal_pct"])

    afr_weighted = float(fill["capacity_weighted_actual_pct"])
    nfr_weighted = float(fill["capacity_weighted_nominal_pct"])

    afr_sailing = float(fill["mean_sailing_peak_actual_pct"])
    nfr_sailing = float(fill["mean_sailing_peak_nominal_pct"])

    _assert_close(
        afr_arc,
        recomputed_afr_arc,
        message=(f"Independent AFR reconstruction failed for {run_key}"),
    )

    _assert_close(
        nfr_arc,
        recomputed_nfr_arc,
        message=(f"Independent NFR reconstruction failed for {run_key}"),
    )

    _assert_close(
        afr_weighted,
        recomputed_afr_weighted,
        message=(f"Independent weighted AFR failed for {run_key}"),
    )

    _assert_close(
        nfr_weighted,
        recomputed_nfr_weighted,
        message=(f"Independent weighted NFR failed for {run_key}"),
    )

    for name, afr, nfr in (
        (
            "mean-arc",
            afr_arc,
            nfr_arc,
        ),
        (
            "capacity-weighted",
            afr_weighted,
            nfr_weighted,
        ),
        (
            "sailing-peak",
            afr_sailing,
            nfr_sailing,
        ),
    ):
        _assert_close(
            nfr,
            water_factor * afr,
            message=(f"NFR = water_factor * AFR failed for {run_key} ({name})"),
        )

    vtr = _pct(
        truck_volume,
        requested_volume,
    )

    vfb = _pct(
        final_barge_volume,
        requested_volume,
    )

    vob = _pct(
        accepted_volume,
        requested_volume,
    )

    _assert_close(
        vob,
        vfb + vtr,
        message=(f"VOB = VFB + VTR failed for {run_key}"),
    )

    return {
        "service_family": wrapper["service_family"],
        "capacity_teu": int(wrapper["capacity_teu"]),
        "water_factor": water_factor,
        "policy_key": "pr",
        "source_kind": "table6_new_reduced_water",
        "source_run_key": run_key,
        "source_commit": wrapper["source_commit"],
        "demand_fingerprint": wrapper["demand_fingerprint"],
        "solver_backend": record["solver_backend"],
        "completed": True,
        "requested_request_count": requested_count,
        "accepted_request_count": accepted_count,
        "processed_booking_count": int(record["processed_booking_count"]),
        "processed_status_count": int(record["processed_status_count"]),
        "ordinary_rejection_count": int(record["ordinary_rejection_count"]),
        "feasibility_rejection_count": int(record["feasibility_rejection_count"]),
        "solver_failure_count": int(record["solver_failure_count"]),
        "requested_volume_teu": requested_volume,
        "accepted_volume_teu": accepted_volume,
        "final_barge_volume_teu": final_barge_volume,
        "truck_volume_teu": truck_volume,
        "gross_revenue": gross_revenue,
        "truck_penalty": truck_penalty,
        "net_revenue": net_value,
        "afr_arc_pct": afr_arc,
        "nfr_arc_pct": nfr_arc,
        "afr_weighted_pct": afr_weighted,
        "nfr_weighted_pct": nfr_weighted,
        "afr_sailing_peak_pct": afr_sailing,
        "nfr_sailing_peak_pct": nfr_sailing,
        "vtr_pct": vtr,
        "vfb_pct": vfb,
        "vob_pct": vob,
        "runtime_seconds": float(record["runtime_seconds"]),
        "max_actual_capacity_violation": max_capacity_violation,
    }


def _load_table5_standard_rows() -> list[dict[str, Any]]:
    manifest = _read_json(TABLE5_MANIFEST)

    table5_source_commit = str(manifest["source_commit"])

    rows: list[dict[str, Any]] = []

    with TABLE5_POLICY_RUNS.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        for row in csv.DictReader(handle):
            if row["policy_key"] != "pr":
                continue

            if row["demand_fingerprint"] != (DEMAND_FINGERPRINT):
                raise RuntimeError("Table-5 PR demand fingerprint does not match Table 6.")

            rows.append(
                {
                    "service_family": row["service_family"],
                    "capacity_teu": int(row["capacity_teu"]),
                    "water_factor": 1.0,
                    "policy_key": "pr",
                    "source_kind": "table5_reused_standard_water",
                    "source_run_key": row["run_key"],
                    "source_commit": table5_source_commit,
                    "demand_fingerprint": row["demand_fingerprint"],
                    "solver_backend": row["solver_backend"],
                    "completed": row["completed"] == "True",
                    "requested_request_count": int(row["requested_request_count"]),
                    "accepted_request_count": int(row["accepted_request_count"]),
                    "processed_booking_count": int(row["processed_booking_count"]),
                    "processed_status_count": int(row["processed_status_count"]),
                    "ordinary_rejection_count": int(row["ordinary_rejection_count"]),
                    "feasibility_rejection_count": int(row["feasibility_rejection_count"]),
                    "solver_failure_count": int(row["solver_failure_count"]),
                    "requested_volume_teu": float(row["requested_volume_teu"]),
                    "accepted_volume_teu": float(row["accepted_volume_teu"]),
                    "final_barge_volume_teu": float(row["final_barge_volume_teu"]),
                    "truck_volume_teu": float(row["truck_volume_teu"]),
                    "gross_revenue": float(row["gross_revenue"]),
                    "truck_penalty": float(row["truck_penalty"]),
                    "net_revenue": float(row["net_revenue"]),
                    "afr_arc_pct": float(row["afr_arc_pct"]),
                    "nfr_arc_pct": float(row["nfr_arc_pct"]),
                    "afr_weighted_pct": float(row["afr_weighted_pct"]),
                    "nfr_weighted_pct": float(row["nfr_weighted_pct"]),
                    "afr_sailing_peak_pct": float(row["afr_sailing_peak_pct"]),
                    "nfr_sailing_peak_pct": float(row["nfr_sailing_peak_pct"]),
                    "vtr_pct": float(row["vtr_pct"]),
                    "vfb_pct": float(row["vfb_pct"]),
                    "vob_pct": float(row["vob_pct"]),
                    "runtime_seconds": float(row["solving_time_seconds"]),
                    "max_actual_capacity_violation": 0.0,
                }
            )

    if len(rows) != 8:
        raise RuntimeError("Expected exactly eight reusable standard-water Table-5 PR rows.")

    return rows


def main() -> None:
    AUDIT.mkdir(
        parents=True,
        exist_ok=True,
    )

    record_paths = sorted(RECORDS.glob("*.json"))

    prevalidation_paths = sorted(PREVALIDATION.glob("*.json"))

    if len(record_paths) != 24:
        raise RuntimeError("Expected exactly 24 Table-6 rich records.")

    if len(prevalidation_paths) != 24:
        raise RuntimeError("Expected exactly 24 Table-6 prevalidations.")

    reduced_rows: list[dict[str, Any]] = []

    source_commits: set[str] = set()
    demand_fingerprints: set[str] = set()
    run_keys: set[str] = set()

    expected_reduced = {
        (
            f"service_family_{service}",
            capacity,
            water,
        )
        for service in (1, 2)
        for capacity in (
            10,
            20,
            30,
            40,
        )
        for water in (
            0.9,
            0.8,
            0.7,
        )
    }

    actual_reduced: set[tuple[str, int, float]] = set()

    for path in record_paths:
        wrapper = _read_json(path)

        run_key = str(wrapper["run_key"])

        if run_key in run_keys:
            raise RuntimeError(f"Duplicate Table-6 run: {run_key}.")

        run_keys.add(run_key)

        expected_prevalidation = PREVALIDATION / f"{run_key}.json"

        if not expected_prevalidation.exists():
            raise RuntimeError(f"Missing matching prevalidation for {run_key}.")

        _audit_prevalidation(
            expected_prevalidation,
            expected_run_key=run_key,
        )

        row = _audit_reduced_record(wrapper)

        reduced_rows.append(row)

        source_commits.add(str(wrapper["source_commit"]))

        demand_fingerprints.add(str(wrapper["demand_fingerprint"]))

        actual_reduced.add(
            (
                str(wrapper["service_family"]),
                int(wrapper["capacity_teu"]),
                float(wrapper["water_factor"]),
            )
        )

    if len(source_commits) != 1:
        raise RuntimeError("Table-6 production rows use multiple source commits.")

    if demand_fingerprints != {DEMAND_FINGERPRINT}:
        raise RuntimeError("Table-6 demand fingerprint changed.")

    if actual_reduced != expected_reduced:
        missing = expected_reduced - actual_reduced

        unexpected = actual_reduced - expected_reduced

        raise RuntimeError(
            "Table-6 reduced-water coverage changed. "
            f"Missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}."
        )

    standard_rows = _load_table5_standard_rows()

    controlled_rows = standard_rows + reduced_rows

    controlled_rows.sort(
        key=lambda row: (
            row["service_family"],
            row["capacity_teu"],
            -row["water_factor"],
        )
    )

    if len(controlled_rows) != 32:
        raise RuntimeError("Complete controlled Table 6 must contain 32 rows.")

    complete_keys = {
        (
            row["service_family"],
            row["capacity_teu"],
            row["water_factor"],
        )
        for row in controlled_rows
    }

    if complete_keys != set(PUBLISHED):
        raise RuntimeError(
            "Controlled and published Table-6 matrices do not have identical coverage."
        )

    comparison_rows: list[dict[str, Any]] = []

    for row in controlled_rows:
        key = (
            row["service_family"],
            row["capacity_teu"],
            row["water_factor"],
        )

        paper = PUBLISHED[key]

        anomaly = ""

        if key == (
            "service_family_1",
            40,
            0.9,
        ):
            anomaly = "Publication prints NFR=8. Value retained literally; not silently corrected."

        comparison_rows.append(
            {
                "service_family": row["service_family"],
                "capacity_teu": row["capacity_teu"],
                "water_factor": row["water_factor"],
                "paper_afr_pct": paper["afr"],
                "paper_nfr_pct": paper["nfr"],
                "paper_vt_pct": paper["vt"],
                "paper_vfb_pct": paper["vfb"],
                "paper_vob_pct": paper["vob"],
                "paper_note": anomaly,
                "controlled_afr_pct": row["afr_arc_pct"],
                "controlled_nfr_pct": row["nfr_arc_pct"],
                "controlled_vtr_pct": row["vtr_pct"],
                "controlled_vfb_pct": row["vfb_pct"],
                "controlled_vob_pct": row["vob_pct"],
                "afr_delta_pp": row["afr_arc_pct"] - float(paper["afr"]),
                "nfr_delta_pp": row["nfr_arc_pct"] - float(paper["nfr"]),
                "vtr_minus_paper_vt_pp": row["vtr_pct"] - float(paper["vt"]),
                "vfb_delta_pp": row["vfb_pct"] - float(paper["vfb"]),
                "vob_delta_pp": row["vob_pct"] - float(paper["vob"]),
            }
        )

    row_by_key = {
        (
            row["service_family"],
            row["capacity_teu"],
            row["water_factor"],
        ): row
        for row in controlled_rows
    }

    water_effect_rows: list[dict[str, Any]] = []

    for row in controlled_rows:
        baseline = row_by_key[
            (
                row["service_family"],
                row["capacity_teu"],
                1.0,
            )
        ]

        paper = PUBLISHED[
            (
                row["service_family"],
                row["capacity_teu"],
                row["water_factor"],
            )
        ]

        paper_baseline = PUBLISHED[
            (
                row["service_family"],
                row["capacity_teu"],
                1.0,
            )
        ]

        water_effect_rows.append(
            {
                "service_family": row["service_family"],
                "capacity_teu": row["capacity_teu"],
                "water_factor": row["water_factor"],
                "controlled_afr_change_from_water1_pp": row["afr_arc_pct"]
                - baseline["afr_arc_pct"],
                "controlled_nfr_change_from_water1_pp": row["nfr_arc_pct"]
                - baseline["nfr_arc_pct"],
                "controlled_vtr_change_from_water1_pp": row["vtr_pct"] - baseline["vtr_pct"],
                "controlled_vfb_change_from_water1_pp": row["vfb_pct"] - baseline["vfb_pct"],
                "controlled_vob_change_from_water1_pp": row["vob_pct"] - baseline["vob_pct"],
                "controlled_accepted_volume_change_teu": row["accepted_volume_teu"]
                - baseline["accepted_volume_teu"],
                "controlled_truck_volume_change_teu": row["truck_volume_teu"]
                - baseline["truck_volume_teu"],
                "paper_afr_change_from_water1_pp": float(paper["afr"])
                - float(paper_baseline["afr"]),
                "paper_nfr_change_from_water1_pp": float(paper["nfr"])
                - float(paper_baseline["nfr"]),
                "paper_vt_change_from_water1_pp": float(paper["vt"]) - float(paper_baseline["vt"]),
                "paper_vfb_change_from_water1_pp": float(paper["vfb"])
                - float(paper_baseline["vfb"]),
                "paper_vob_change_from_water1_pp": float(paper["vob"])
                - float(paper_baseline["vob"]),
            }
        )

    _write_csv(
        CONTROLLED_PATH,
        controlled_rows,
    )

    _write_csv(
        COMPARISON_PATH,
        comparison_rows,
    )

    _write_csv(
        WATER_EFFECTS_PATH,
        water_effect_rows,
    )

    run_plan = [
        {
            "position": position,
            "service_family": row["service_family"],
            "capacity_teu": row["capacity_teu"],
            "water_factor": row["water_factor"],
            "policy_key": "pr",
            "source_kind": row["source_kind"],
            "source_run_key": row["source_run_key"],
        }
        for position, row in enumerate(
            controlled_rows,
            start=1,
        )
    ]

    RUN_PLAN_PATH.write_text(
        json.dumps(
            {
                "schema_version": "table6-run-plan-v1",
                "row_count": len(run_plan),
                "rows": run_plan,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    evidence_paths = record_paths + prevalidation_paths + [TABLE5_POLICY_RUNS]

    hash_lines = []

    for path in evidence_paths:
        hash_lines.append(f"{_sha256(path)}  {path.as_posix()}")

    HASH_PATH.write_text(
        "\n".join(hash_lines) + "\n",
        encoding="utf-8",
    )

    runtime_seconds = fsum(float(row["runtime_seconds"]) for row in reduced_rows)

    runtime_by_water = {
        water: fsum(
            float(row["runtime_seconds"]) for row in reduced_rows if row["water_factor"] == water
        )
        for water in (
            0.9,
            0.8,
            0.7,
        )
    }

    runtime_by_service = {
        service: fsum(
            float(row["runtime_seconds"])
            for row in reduced_rows
            if row["service_family"] == service
        )
        for service in (
            "service_family_1",
            "service_family_2",
        )
    }

    table5_manifest = _read_json(TABLE5_MANIFEST)

    manifest = {
        "schema_version": "table6-campaign-manifest-v1",
        "classification": "controlled_substitute_input",
        "all_required_runs_completed": True,
        "published_table6_row_count": 32,
        "controlled_table6_row_count": len(controlled_rows),
        "reused_standard_water_row_count": len(standard_rows),
        "new_reduced_water_row_count": len(reduced_rows),
        "new_prevalidation_artifact_count": len(prevalidation_paths),
        "campaign_source_commit": next(iter(source_commits)),
        "table5_reused_source_commit": table5_manifest["source_commit"],
        "demand_fingerprint": DEMAND_FINGERPRINT,
        "requested_booking_count": 800,
        "requested_volume_teu": 1076.0,
        "water_factors": [
            1.0,
            0.9,
            0.8,
            0.7,
        ],
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
        "policy_key": "pr",
        "new_campaign_runtime_seconds": runtime_seconds,
        "new_campaign_runtime_hours": runtime_seconds / 3600.0,
        "runtime_hours_by_water": {
            str(water): seconds / 3600.0 for water, seconds in runtime_by_water.items()
        },
        "runtime_hours_by_service": {
            service: seconds / 3600.0 for service, seconds in runtime_by_service.items()
        },
        "evidence_sha256_entry_count": len(hash_lines),
        "table6_printed_anomaly": {
            "service_family": "service_family_1",
            "capacity_teu": 40,
            "water_factor": 0.9,
            "indicator": "NFR",
            "printed_value": 8,
            "note": ("Retained literally. No silent correction."),
        },
        "indicator_contract": {
            "primary_afr": "mean transport-arc actual utilisation",
            "primary_nfr": "mean transport-arc nominal utilisation",
            "vtr": "truck volume / requested volume",
            "vfb": "final barge volume / requested volume",
            "vob": "accepted volume / requested volume",
            "reduced_water_identity": "NFR = water_factor * AFR",
        },
        "outputs": {
            "controlled_rows": CONTROLLED_PATH.as_posix(),
            "published_comparison": COMPARISON_PATH.as_posix(),
            "water_effects": WATER_EFFECTS_PATH.as_posix(),
            "run_plan": RUN_PLAN_PATH.as_posix(),
            "global_audit": AUDIT_PATH.as_posix(),
            "evidence_sha256": HASH_PATH.as_posix(),
        },
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

    audit_lines = [
        "=" * 110,
        "TABLE 6 — GLOBAL CAMPAIGN AUDIT",
        "=" * 110,
        "",
        "Reduced-water rich records: 24",
        "Reduced-water prevalidations: 24",
        "Standard-water rows reused from Table 5: 8",
        "Complete controlled Table-6 rows: 32",
        "Coverage: PASS",
        "Unique reduced-water run keys: PASS",
        "Single campaign source commit: PASS",
        "Single frozen demand fingerprint: PASS",
        "All prevalidations validated: PASS",
        "800 booking events per reduced run: PASS",
        "20 status updates per reduced run: PASS",
        "Zero solver failures: PASS",
        "Accepted = final barge + truck: PASS",
        "Gross revenue - truck penalty = net revenue: PASS",
        "Historical actual capacity = water factor * nominal capacity: PASS",
        "No material actual-capacity violations: PASS",
        "Independent mean-arc AFR/NFR reconstruction: PASS",
        "Independent weighted AFR/NFR reconstruction: PASS",
        "NFR = water factor * AFR for all three retained candidates: PASS",
        "",
        "=" * 110,
        "CANONICAL CONTROLLED TABLE 6",
        "=" * 110,
        (
            "SF  Cap Water   AccTEU    Barge    Truck "
            "    AFR%     NFR%     VTR%     VFB%     VOB%     Time(s) Source"
        ),
        "-" * 140,
    ]

    for row in controlled_rows:
        service_number = 1 if row["service_family"] == "service_family_1" else 2

        audit_lines.append(
            f"{service_number:>2} "
            f"{row['capacity_teu']:>4} "
            f"{row['water_factor']:>5.1f} "
            f"{row['accepted_volume_teu']:>9.3f} "
            f"{row['final_barge_volume_teu']:>8.3f} "
            f"{row['truck_volume_teu']:>8.3f} "
            f"{row['afr_arc_pct']:>8.3f} "
            f"{row['nfr_arc_pct']:>8.3f} "
            f"{row['vtr_pct']:>8.3f} "
            f"{row['vfb_pct']:>8.3f} "
            f"{row['vob_pct']:>8.3f} "
            f"{row['runtime_seconds']:>11.3f} "
            f"{row['source_kind']}"
        )

    audit_lines.extend(
        [
            "",
            "=" * 110,
            "RUNTIME SUMMARY — NEW REDUCED-WATER RUNS",
            "=" * 110,
            (f"Total: {runtime_seconds:.3f}s = {runtime_seconds / 3600.0:.3f}h"),
        ]
    )

    for water in (
        0.9,
        0.8,
        0.7,
    ):
        seconds = runtime_by_water[water]

        audit_lines.append(f"Water {water:.1f}: {seconds:.3f}s = {seconds / 3600.0:.3f}h")

    for service, seconds in runtime_by_service.items():
        audit_lines.append(f"{service}: {seconds:.3f}s = {seconds / 3600.0:.3f}h")

    audit_lines.extend(
        [
            "",
            "=" * 110,
            "PUBLICATION ANOMALY",
            "=" * 110,
            (
                "Service 1 / capacity 40 / "
                "water 0.9: Table 6 prints "
                "NFR = 8. This value is retained "
                "literally in comparison output."
            ),
            "",
            "=" * 110,
            "TABLE 6 GLOBAL CAMPAIGN AUDIT: PASS",
            "=" * 110,
        ]
    )

    audit_text = "\n".join(audit_lines) + "\n"

    AUDIT_PATH.write_text(
        audit_text,
        encoding="utf-8",
    )

    print(audit_text)

    print(f"Wrote {CONTROLLED_PATH}")
    print(f"Wrote {COMPARISON_PATH}")
    print(f"Wrote {WATER_EFFECTS_PATH}")
    print(f"Wrote {RUN_PLAN_PATH}")
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Wrote {AUDIT_PATH}")
    print(f"Wrote {HASH_PATH}")

    print()
    print(
        "Evidence SHA-256 entries:",
        len(hash_lines),
    )
    print(
        "Complete controlled rows:",
        len(controlled_rows),
    )
    print(
        "New campaign runtime hours:",
        round(
            runtime_seconds / 3600.0,
            3,
        ),
    )


if __name__ == "__main__":
    main()
