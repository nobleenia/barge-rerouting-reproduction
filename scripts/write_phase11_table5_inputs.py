"""Materialize the frozen Phase 11 Table 5 controlled demand input."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from barge_rerouting.experiments.phase11_table5_demands import (
    build_frozen_table5_controlled_demand_set,
)

OUTPUT_DIRECTORY = Path("results/phase11/table5/inputs")


def main() -> None:
    demand_set = build_frozen_table5_controlled_demand_set()

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = OUTPUT_DIRECTORY / "table5_demands.csv"

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(
            handle,
            lineterminator="\n",
        )

        writer.writerow(
            (
                "demand_id",
                "volume",
                "origin",
                "destination",
                "reservation_time",
                "availability_time",
                "due_time",
                "category",
                "fare_per_teu",
            )
        )

        for demand in demand_set.demands:
            writer.writerow(
                (
                    demand.demand_id,
                    demand.volume,
                    demand.origin,
                    demand.destination,
                    demand.reservation_time,
                    demand.availability_time,
                    demand.due_time,
                    demand.category.value,
                    demand.fare_per_teu,
                )
            )

    manifest = {
        "reproduction_class": ("controlled_substitute_input"),
        "seed": demand_set.seed,
        "economic_seed": (demand_set.economic_seed),
        "request_count": (demand_set.request_count),
        "total_requested_teu": float(sum(demand.volume for demand in demand_set.demands)),
        "structural_fingerprint": (demand_set.structural_fingerprint),
        "economic_fingerprint": (demand_set.economic_fingerprint),
        "demand_fingerprint": (demand_set.demand_fingerprint),
        "source_file": ("table5_demands.csv"),
    }

    manifest_path = OUTPUT_DIRECTORY / "table5_demands_manifest.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Wrote:", csv_path)
    print("Wrote:", manifest_path)
    print(
        "Demand fingerprint:",
        demand_set.demand_fingerprint,
    )


if __name__ == "__main__":
    main()
