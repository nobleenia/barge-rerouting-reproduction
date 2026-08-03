"""Serialisation utilities for generated demand instances."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path

from barge_rerouting.domain import Demand

type DemandRecordValue = str | int | float
type DemandRecord = dict[str, DemandRecordValue]

DEMAND_FIELDNAMES = (
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


def demand_records(
    demands: Iterable[Demand],
) -> tuple[DemandRecord, ...]:
    """Convert demands into deterministic serialisable records."""
    records: list[DemandRecord] = []

    for demand in demands:
        records.append(
            {
                "demand_id": demand.demand_id,
                "volume": float(demand.volume),
                "origin": demand.origin,
                "destination": demand.destination,
                "reservation_time": int(demand.reservation_time),
                "availability_time": int(demand.availability_time),
                "due_time": int(demand.due_time),
                "category": demand.category.value,
                "fare_per_teu": float(demand.fare_per_teu),
            }
        )

    return tuple(records)


def demand_fingerprint(
    demands: Iterable[Demand],
) -> str:
    """Return a SHA-256 fingerprint for a generated demand instance."""
    records = demand_records(demands)
    payload = json.dumps(
        records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return sha256(payload.encode("utf-8")).hexdigest()


def write_demands_csv(
    demands: Iterable[Demand],
    output_path: str | Path,
) -> Path:
    """Write generated demands to a deterministic CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    records = demand_records(demands)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=DEMAND_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(records)

    return path
