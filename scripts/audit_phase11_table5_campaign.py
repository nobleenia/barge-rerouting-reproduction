from pathlib import Path

from barge_rerouting.experiments.phase11_table5_checkpoint import (
    load_table5_campaign_checkpoint,
)

BASE = Path("results/phase11/table5/campaign")
CHECKPOINT = BASE / "campaign_checkpoint.json"
PREVALIDATION = BASE / "prevalidation"

FAMILIES = (1, 2)
CAPACITIES = (10, 20, 30, 40)
POLICIES = ("dca", "pr", "fr")

EXPECTED_KEYS = [
    f"service_family_{sf}__capacity_{cap}__{policy}"
    for sf in FAMILIES
    for cap in CAPACITIES
    for policy in POLICIES
]

LEGACY_WITHOUT_PREVALIDATION = {
    "service_family_1__capacity_10__dca",
    "service_family_1__capacity_10__pr",
}

records, metadata = load_table5_campaign_checkpoint(CHECKPOINT)

print("=" * 100)
print("TABLE 5 — GLOBAL 24-RUN CAMPAIGN AUDIT")
print("=" * 100)

print("checkpoint records:", len(records))
print("metadata cells:", len(metadata))

assert len(records) == 24
assert len(metadata) == 8

run_keys = [record.run_key for record in records]

assert len(run_keys) == len(set(run_keys))
assert set(run_keys) == set(EXPECTED_KEYS)

print("unique run keys: PASS")
print("8 structural cells x 3 policies: PASS")

# ------------------------------------------------------------------
# Prevalidation coverage
# ------------------------------------------------------------------

prevalidation_keys = {path.stem for path in PREVALIDATION.glob("*.json")}

missing_prevalidation = set(EXPECTED_KEYS) - prevalidation_keys
unexpected_prevalidation = prevalidation_keys - set(EXPECTED_KEYS)

print()
print("=" * 100)
print("PREVALIDATION COVERAGE")
print("=" * 100)

print("artifact count:", len(prevalidation_keys))
print("missing:", sorted(missing_prevalidation))
print("unexpected:", sorted(unexpected_prevalidation))

assert len(prevalidation_keys) == 22
assert missing_prevalidation == LEGACY_WITHOUT_PREVALIDATION
assert not unexpected_prevalidation

print("coverage: PASS (22 current-schema artifacts + 2 documented legacy runs)")

# ------------------------------------------------------------------
# Record-level validation
# ------------------------------------------------------------------

rows = []

for record in records:
    ledger = record.volume_ledger
    allocation = record.allocation_snapshot
    service = record.service_capacity_snapshot
    indicators = record.indicator_snapshot

    fill = indicators.fill_rate_candidates
    volume = indicators.volume_indicator_candidates

    policy = record.run_key.rsplit("__", 1)[-1]

    accepted_residual = allocation.accepted_volume - ledger.accepted_volume

    truck_residual = allocation.truck_volume - ledger.truck_volume

    barge_residual = allocation.final_barge_volume - ledger.final_barge_volume

    mass_residual = ledger.accepted_volume - ledger.truck_volume - ledger.final_barge_volume

    economic_residual = ledger.gross_revenue - ledger.truck_penalty - ledger.net_value

    assert record.completed
    assert record.solver_failure_count == 0
    assert record.processed_booking_count == 800

    assert ledger.requested_request_count == 800
    assert abs(ledger.requested_volume - 1076.0) <= 1.0e-9

    assert abs(accepted_residual) <= 1.0e-5
    assert abs(truck_residual) <= 1.0e-5
    assert abs(barge_residual) <= 1.0e-5
    assert abs(mass_residual) <= 1.0e-5
    assert abs(economic_residual) <= 1.0e-5

    assert service.standard_water
    assert service.max_final_actual_capacity_violation <= 1.0e-5

    # Standard water: actual and nominal fill coincide.
    assert abs(fill.mean_arc_actual_pct - fill.mean_arc_nominal_pct) <= 1.0e-9

    assert abs(fill.capacity_weighted_actual_pct - fill.capacity_weighted_nominal_pct) <= 1.0e-9

    assert abs(fill.mean_sailing_peak_actual_pct - fill.mean_sailing_peak_nominal_pct) <= 1.0e-9

    # VOB = VFB + VTR
    assert abs(volume.vob_conservation_residual_pct) <= 1.0e-9

    # PR gets the frozen 20 status updates.
    if policy == "pr":
        assert record.processed_status_count == 20
    else:
        assert record.processed_status_count == 0

    # DCA and PR have no truck recourse here.
    if policy in {"dca", "pr"}:
        assert abs(ledger.truck_volume) <= 1.0e-5
        assert abs(ledger.truck_penalty) <= 1.0e-5

        assert abs(ledger.accepted_volume - ledger.final_barge_volume) <= 1.0e-5

        assert abs(volume.vtr_requested_volume_pct) <= 1.0e-9

        assert abs(volume.vob_requested_volume_pct - volume.vfb_requested_volume_pct) <= 1.0e-9

    # Controlled FR convention.
    if policy == "fr":
        assert record.feasibility_rejection_count == 0

    # Every request resolves exactly once.
    assert (
        ledger.accepted_request_count
        + record.feasibility_rejection_count
        + record.ordinary_rejection_count
        == 800
    )

    pieces = record.run_key.split("__")

    sf = int(pieces[0].removeprefix("service_family_"))

    cap = int(pieces[1].removeprefix("capacity_"))

    rows.append(
        {
            "sf": sf,
            "cap": cap,
            "policy": policy.upper(),
            "accepted_requests": ledger.accepted_request_count,
            "accepted_teu": ledger.accepted_volume,
            "barge_teu": ledger.final_barge_volume,
            "truck_teu": ledger.truck_volume,
            "net": ledger.net_value,
            "afr": fill.mean_arc_actual_pct,
            "vob": volume.vob_requested_volume_pct,
            "vfb": volume.vfb_requested_volume_pct,
            "vtr": volume.vtr_requested_volume_pct,
            "voa": volume.voa_request_count_pct,
            "runtime": record.runtime_seconds,
        }
    )

print()
print("record-level contracts: PASS")

# ------------------------------------------------------------------
# Canonical results table
# ------------------------------------------------------------------

rows.sort(
    key=lambda row: (
        row["sf"],
        row["cap"],
        {
            "DCA": 0,
            "PR": 1,
            "FR": 2,
        }[row["policy"]],
    )
)

print()
print("=" * 100)
print("CANONICAL 24-RUN RESULTS")
print("=" * 100)

header = (
    f"{'SF':>2} "
    f"{'Cap':>4} "
    f"{'Pol':<4} "
    f"{'AccReq':>7} "
    f"{'AccTEU':>10} "
    f"{'Barge':>10} "
    f"{'Truck':>10} "
    f"{'Net':>13} "
    f"{'AFR%':>9} "
    f"{'VOB%':>9} "
    f"{'VFB%':>9} "
    f"{'VTR%':>9} "
    f"{'VOA%':>9} "
    f"{'Time(s)':>11}"
)

print(header)
print("-" * len(header))

for row in rows:
    print(
        f"{row['sf']:>2} "
        f"{row['cap']:>4} "
        f"{row['policy']:<4} "
        f"{row['accepted_requests']:>7} "
        f"{row['accepted_teu']:>10.3f} "
        f"{row['barge_teu']:>10.3f} "
        f"{row['truck_teu']:>10.3f} "
        f"{row['net']:>13.2f} "
        f"{row['afr']:>9.3f} "
        f"{row['vob']:>9.3f} "
        f"{row['vfb']:>9.3f} "
        f"{row['vtr']:>9.3f} "
        f"{row['voa']:>9.3f} "
        f"{row['runtime']:>11.3f}"
    )

# ------------------------------------------------------------------
# Runtime summary
# ------------------------------------------------------------------

print()
print("=" * 100)
print("RUNTIME SUMMARY")
print("=" * 100)

for policy in ("DCA", "PR", "FR"):
    subset = [row for row in rows if row["policy"] == policy]

    total = sum(row["runtime"] for row in subset)

    mean = total / len(subset)

    print(
        f"{policy}: "
        f"runs={len(subset)}, "
        f"total={total:.3f}s, "
        f"mean={mean:.3f}s, "
        f"total_hours={total / 3600:.3f}h"
    )

print()
print("=" * 100)
print("TABLE 5 GLOBAL CAMPAIGN AUDIT: PASS")
print("=" * 100)
