from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

BASE = Path("results/phase11/table5/campaign")

INPUT = BASE / "table5_published_comparison.csv"
OUTPUT = BASE / "table5_policy_comparisons.csv"


def as_float(value: str) -> float:
    return float(value)


def improvement(value: float, baseline: float) -> float:
    if baseline == 0.0:
        raise ValueError("Cannot calculate improvement relative to zero.")
    return 100.0 * (value - baseline) / baseline


with INPUT.open(
    newline="",
    encoding="utf-8",
) as handle:
    rows = list(csv.DictReader(handle))

assert len(rows) == 24

by_cell: dict[
    tuple[str, int],
    dict[str, dict[str, str]],
] = {}

for row in rows:
    key = (
        row["service_family"],
        int(row["capacity_teu"]),
    )

    by_cell.setdefault(
        key,
        {},
    )[row["policy_key"]] = row

assert len(by_cell) == 8

output_rows: list[dict[str, Any]] = []

for (service_family, capacity), policies in sorted(by_cell.items()):
    assert set(policies) == {
        "dca",
        "pr",
        "fr",
    }

    dca = policies["dca"]

    paper_dca_tr = as_float(dca["paper_tr"])
    controlled_dca_gross = as_float(dca["controlled_gross_revenue"])
    controlled_dca_net = as_float(dca["controlled_net_revenue"])

    paper_dca_afr = as_float(dca["paper_afr_pct"])
    controlled_dca_afr = as_float(dca["controlled_afr_arc_pct"])

    paper_dca_vob = as_float(dca["paper_vob_pct"])
    controlled_dca_vob = as_float(dca["controlled_vob_pct"])

    paper_dca_voa = as_float(dca["paper_voa_pct"])
    controlled_dca_voa = as_float(dca["controlled_voa_count_pct"])

    paper_dca_st = as_float(dca["paper_st_seconds"])
    controlled_dca_st = as_float(dca["controlled_st_seconds"])

    for policy in (
        "dca",
        "pr",
        "fr",
    ):
        row = policies[policy]

        paper_tr = as_float(row["paper_tr"])
        controlled_gross = as_float(row["controlled_gross_revenue"])
        controlled_net = as_float(row["controlled_net_revenue"])

        paper_afr = as_float(row["paper_afr_pct"])
        controlled_afr = as_float(row["controlled_afr_arc_pct"])

        paper_vob = as_float(row["paper_vob_pct"])
        controlled_vob = as_float(row["controlled_vob_pct"])

        paper_voa = as_float(row["paper_voa_pct"])
        controlled_voa = as_float(row["controlled_voa_count_pct"])

        paper_st = as_float(row["paper_st_seconds"])
        controlled_st = as_float(row["controlled_st_seconds"])

        output_rows.append(
            {
                "service_family": service_family,
                "capacity_teu": capacity,
                "policy_key": policy,
                "paper_tr_ir_vs_dca_pct": improvement(
                    paper_tr,
                    paper_dca_tr,
                ),
                "controlled_gross_ir_vs_dca_pct": improvement(
                    controlled_gross,
                    controlled_dca_gross,
                ),
                "controlled_net_ir_vs_dca_pct": improvement(
                    controlled_net,
                    controlled_dca_net,
                ),
                "paper_afr_change_vs_dca_pp": paper_afr - paper_dca_afr,
                "controlled_afr_change_vs_dca_pp": controlled_afr - controlled_dca_afr,
                "paper_vob_change_vs_dca_pp": paper_vob - paper_dca_vob,
                "controlled_vob_change_vs_dca_pp": controlled_vob - controlled_dca_vob,
                "paper_voa_change_vs_dca_pp": paper_voa - paper_dca_voa,
                "controlled_voa_change_vs_dca_pp": controlled_voa - controlled_dca_voa,
                "paper_vtr_pct": row["paper_vtr_pct"],
                "controlled_vtr_pct": row["controlled_vtr_pct"],
                "paper_st_multiplier_vs_dca": paper_st / paper_dca_st,
                "controlled_st_multiplier_vs_dca": controlled_st / controlled_dca_st,
            }
        )

with OUTPUT.open(
    "w",
    newline="",
    encoding="utf-8",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(output_rows[0]),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(output_rows)

print(f"Wrote {OUTPUT}")
print(
    "Comparison rows:",
    len(output_rows),
)
