"""Paired experimental infrastructure for Phase 11 Table 4.

This module defines experiment identity, traceability, paired
DCA-relative comparison, aggregation, and raw-result schemas.

It deliberately does not define the unpublished Table 4 demand
generation or future-demand forecast parameters. Those remain explicit
controlled substitute inputs until separately documented.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Final

from barge_rerouting.config import ExperimentConfig

TABLE4_TOLERANCE: Final = 1e-9

TABLE4_SERVICE_FAMILIES: Final[tuple[str, ...]] = (
    "service_family_1",
    "service_family_2",
)

TABLE4_CAPACITIES_TEU: Final[tuple[int, ...]] = (
    10,
    15,
    20,
)

TABLE4_POLICY_KEYS: Final[tuple[str, ...]] = (
    "dca",
    "dca_rm",
    "dca_r",
    "dca_rrm",
)

# These are controlled substitute seeds, not claimed paper seeds.
DEFAULT_TABLE4_DEMAND_SEEDS: Final[tuple[int, ...]] = (
    11001,
    11002,
    11003,
    11004,
    11005,
)

CONTROLLED_SUBSTITUTE_INPUT: Final = "controlled_substitute_input"

VALID_REPRODUCTION_CLASSES: Final[tuple[str, ...]] = (
    "strict_publication_structure",
    CONTROLLED_SUBSTITUTE_INPUT,
    "sensitivity",
    "extension",
)


def _normalise_nonempty_string(
    name: str,
    value: object,
) -> str:
    """Validate and normalise a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    normalised = value.strip()

    if not normalised:
        raise ValueError(f"{name} must be non-empty.")

    return normalised


def _validate_seed(value: object) -> int:
    """Validate one deterministic non-negative seed."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("seed must be an integer.")

    if value < 0:
        raise ValueError("seed must be non-negative.")

    return value


def _validate_capacity(value: object) -> int:
    """Validate one published Table 4 nominal capacity."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("capacity_teu must be an integer.")

    if value not in TABLE4_CAPACITIES_TEU:
        raise ValueError(f"capacity_teu must be one of {TABLE4_CAPACITIES_TEU}.")

    return value


def _validate_service_family(value: object) -> str:
    """Validate one Table 4 service-family key."""
    family = _normalise_nonempty_string(
        "service_family",
        value,
    )

    if family not in TABLE4_SERVICE_FAMILIES:
        raise ValueError(f"service_family must be one of {TABLE4_SERVICE_FAMILIES}.")

    return family


def _validate_policy(value: object) -> str:
    """Validate one Table 4 policy key."""
    policy = _normalise_nonempty_string(
        "policy_key",
        value,
    )

    if policy not in TABLE4_POLICY_KEYS:
        raise ValueError(f"policy_key must be one of {TABLE4_POLICY_KEYS}.")

    return policy


def _validate_reproduction_class(value: object) -> str:
    """Validate experiment-classification metadata."""
    classification = _normalise_nonempty_string(
        "reproduction_class",
        value,
    )

    if classification not in VALID_REPRODUCTION_CLASSES:
        raise ValueError(f"Unsupported reproduction_class: {classification}.")

    return classification


def _validate_fingerprint(
    name: str,
    value: object,
) -> str:
    """Validate one SHA-256 hexadecimal fingerprint."""
    fingerprint = _normalise_nonempty_string(
        name,
        value,
    ).lower()

    if len(fingerprint) != 64:
        raise ValueError(f"{name} must contain 64 hexadecimal characters.")

    if any(character not in "0123456789abcdef" for character in fingerprint):
        raise ValueError(f"{name} must be hexadecimal.")

    return fingerprint


def _validate_nonnegative_float(
    name: str,
    value: object,
) -> float:
    """Validate one finite non-negative reporting value."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric < 0.0:
        raise ValueError(f"{name} must be non-negative.")

    return numeric


def _validate_optional_nonnegative_float(
    name: str,
    value: object | None,
) -> float | None:
    """Validate optional non-negative reporting metadata."""
    if value is None:
        return None

    return _validate_nonnegative_float(name, value)


def _validate_optional_nonnegative_int(
    name: str,
    value: object | None,
) -> int | None:
    """Validate optional non-negative integer metadata."""
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer or None.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def experiment_config_fingerprint(
    config: ExperimentConfig,
) -> str:
    """Return deterministic SHA-256 of one experiment config."""
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig.")

    payload = json.dumps(
        asdict(config),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Table4DemandSetSpec:
    """One controlled demand-set identity."""

    demand_set_id: str
    seed: int
    reproduction_class: str = CONTROLLED_SUBSTITUTE_INPUT

    def __post_init__(self) -> None:
        """Validate demand-set identity."""
        object.__setattr__(
            self,
            "demand_set_id",
            _normalise_nonempty_string(
                "demand_set_id",
                self.demand_set_id,
            ),
        )
        object.__setattr__(
            self,
            "seed",
            _validate_seed(self.seed),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )


@dataclass(frozen=True, slots=True)
class Table4CellSpec:
    """One paired service/capacity/demand-set block."""

    service_family: str
    capacity_teu: int
    demand_set_id: str
    seed: int
    reproduction_class: str

    def __post_init__(self) -> None:
        """Validate the paired experimental cell."""
        object.__setattr__(
            self,
            "service_family",
            _validate_service_family(self.service_family),
        )
        object.__setattr__(
            self,
            "capacity_teu",
            _validate_capacity(self.capacity_teu),
        )
        object.__setattr__(
            self,
            "demand_set_id",
            _normalise_nonempty_string(
                "demand_set_id",
                self.demand_set_id,
            ),
        )
        object.__setattr__(
            self,
            "seed",
            _validate_seed(self.seed),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )

    @property
    def cell_key(self) -> tuple[str, int, str, int]:
        """Return deterministic paired-cell identity."""
        return (
            self.service_family,
            self.capacity_teu,
            self.demand_set_id,
            self.seed,
        )


@dataclass(frozen=True, slots=True)
class Table4RunSpec:
    """One policy run inside a paired Table 4 cell."""

    service_family: str
    capacity_teu: int
    demand_set_id: str
    seed: int
    policy_key: str
    reproduction_class: str

    def __post_init__(self) -> None:
        """Validate one planned policy run."""
        object.__setattr__(
            self,
            "service_family",
            _validate_service_family(self.service_family),
        )
        object.__setattr__(
            self,
            "capacity_teu",
            _validate_capacity(self.capacity_teu),
        )
        object.__setattr__(
            self,
            "demand_set_id",
            _normalise_nonempty_string(
                "demand_set_id",
                self.demand_set_id,
            ),
        )
        object.__setattr__(
            self,
            "seed",
            _validate_seed(self.seed),
        )
        object.__setattr__(
            self,
            "policy_key",
            _validate_policy(self.policy_key),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )

    @property
    def cell_key(self) -> tuple[str, int, str, int]:
        """Return paired-cell identity."""
        return (
            self.service_family,
            self.capacity_teu,
            self.demand_set_id,
            self.seed,
        )


@dataclass(frozen=True, slots=True)
class Table4PolicyRunRecord:
    """Raw traceable result of one Table 4 policy run."""

    service_family: str
    capacity_teu: int
    demand_set_id: str
    seed: int
    policy_key: str
    reproduction_class: str

    configuration_fingerprint: str
    demand_fingerprint: str

    completed: bool
    total_revenue: float
    transported_volume: float
    accepted_volume: float
    solver_status: str

    solve_time_seconds: float | None = None
    mip_gap: float | None = None
    variable_count: int | None = None
    constraint_count: int | None = None
    solver_node_count: int | None = None

    revenue_per_accepted_teu: float | None = field(init=False)

    def __post_init__(self) -> None:
        """Validate one raw run record."""
        object.__setattr__(
            self,
            "service_family",
            _validate_service_family(self.service_family),
        )
        object.__setattr__(
            self,
            "capacity_teu",
            _validate_capacity(self.capacity_teu),
        )
        object.__setattr__(
            self,
            "demand_set_id",
            _normalise_nonempty_string(
                "demand_set_id",
                self.demand_set_id,
            ),
        )
        object.__setattr__(
            self,
            "seed",
            _validate_seed(self.seed),
        )
        object.__setattr__(
            self,
            "policy_key",
            _validate_policy(self.policy_key),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )

        object.__setattr__(
            self,
            "configuration_fingerprint",
            _validate_fingerprint(
                "configuration_fingerprint",
                self.configuration_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "demand_fingerprint",
            _validate_fingerprint(
                "demand_fingerprint",
                self.demand_fingerprint,
            ),
        )

        if not isinstance(self.completed, bool):
            raise TypeError("completed must be a boolean.")

        revenue = _validate_nonnegative_float(
            "total_revenue",
            self.total_revenue,
        )
        transported = _validate_nonnegative_float(
            "transported_volume",
            self.transported_volume,
        )
        accepted = _validate_nonnegative_float(
            "accepted_volume",
            self.accepted_volume,
        )

        if transported > accepted + TABLE4_TOLERANCE:
            raise ValueError("transported_volume cannot exceed accepted_volume.")

        object.__setattr__(
            self,
            "total_revenue",
            revenue,
        )
        object.__setattr__(
            self,
            "transported_volume",
            transported,
        )
        object.__setattr__(
            self,
            "accepted_volume",
            accepted,
        )
        object.__setattr__(
            self,
            "solver_status",
            _normalise_nonempty_string(
                "solver_status",
                self.solver_status,
            ),
        )

        object.__setattr__(
            self,
            "solve_time_seconds",
            _validate_optional_nonnegative_float(
                "solve_time_seconds",
                self.solve_time_seconds,
            ),
        )
        object.__setattr__(
            self,
            "mip_gap",
            _validate_optional_nonnegative_float(
                "mip_gap",
                self.mip_gap,
            ),
        )
        object.__setattr__(
            self,
            "variable_count",
            _validate_optional_nonnegative_int(
                "variable_count",
                self.variable_count,
            ),
        )
        object.__setattr__(
            self,
            "constraint_count",
            _validate_optional_nonnegative_int(
                "constraint_count",
                self.constraint_count,
            ),
        )
        object.__setattr__(
            self,
            "solver_node_count",
            _validate_optional_nonnegative_int(
                "solver_node_count",
                self.solver_node_count,
            ),
        )

        if accepted <= TABLE4_TOLERANCE:
            if revenue > TABLE4_TOLERANCE:
                raise ValueError("Positive revenue requires positive accepted volume.")

            revenue_per_teu = None
        else:
            revenue_per_teu = revenue / accepted

        object.__setattr__(
            self,
            "revenue_per_accepted_teu",
            revenue_per_teu,
        )

    @property
    def cell_key(self) -> tuple[str, int, str, int]:
        """Return paired-cell identity."""
        return (
            self.service_family,
            self.capacity_teu,
            self.demand_set_id,
            self.seed,
        )


@dataclass(frozen=True, slots=True)
class Table4PairedComparison:
    """One policy compared with DCA on the same demand set."""

    service_family: str
    capacity_teu: int
    demand_set_id: str
    seed: int
    policy_key: str
    reproduction_class: str
    configuration_fingerprint: str
    demand_fingerprint: str
    revenue_ir_percent: float
    volume_ir_percent: float

    def __post_init__(self) -> None:
        """Validate paired comparison identity and values."""
        object.__setattr__(
            self,
            "service_family",
            _validate_service_family(self.service_family),
        )
        object.__setattr__(
            self,
            "capacity_teu",
            _validate_capacity(self.capacity_teu),
        )
        object.__setattr__(
            self,
            "demand_set_id",
            _normalise_nonempty_string(
                "demand_set_id",
                self.demand_set_id,
            ),
        )
        object.__setattr__(
            self,
            "seed",
            _validate_seed(self.seed),
        )
        object.__setattr__(
            self,
            "policy_key",
            _validate_policy(self.policy_key),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )
        object.__setattr__(
            self,
            "configuration_fingerprint",
            _validate_fingerprint(
                "configuration_fingerprint",
                self.configuration_fingerprint,
            ),
        )
        object.__setattr__(
            self,
            "demand_fingerprint",
            _validate_fingerprint(
                "demand_fingerprint",
                self.demand_fingerprint,
            ),
        )

        for name in (
            "revenue_ir_percent",
            "volume_ir_percent",
        ):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(
                value,
                (int, float),
            ):
                raise TypeError(f"{name} must be a real number.")

            numeric = float(value)

            if not isfinite(numeric):
                raise ValueError(f"{name} must be finite.")

            object.__setattr__(
                self,
                name,
                numeric,
            )


@dataclass(frozen=True, slots=True)
class Table4Aggregate:
    """Avg/min/max Table 4 IR over five paired demand sets."""

    service_family: str
    capacity_teu: int
    policy_key: str
    reproduction_class: str
    demand_set_count: int

    revenue_ir_avg: float
    revenue_ir_min: float
    revenue_ir_max: float

    volume_ir_avg: float
    volume_ir_min: float
    volume_ir_max: float

    def __post_init__(self) -> None:
        """Validate aggregate reporting values."""
        object.__setattr__(
            self,
            "service_family",
            _validate_service_family(self.service_family),
        )
        object.__setattr__(
            self,
            "capacity_teu",
            _validate_capacity(self.capacity_teu),
        )
        object.__setattr__(
            self,
            "policy_key",
            _validate_policy(self.policy_key),
        )
        object.__setattr__(
            self,
            "reproduction_class",
            _validate_reproduction_class(self.reproduction_class),
        )

        if isinstance(self.demand_set_count, bool) or not isinstance(self.demand_set_count, int):
            raise TypeError("demand_set_count must be an integer.")

        if self.demand_set_count != 5:
            raise ValueError("Table 4 aggregates require exactly five paired demand sets.")

        for name in (
            "revenue_ir_avg",
            "revenue_ir_min",
            "revenue_ir_max",
            "volume_ir_avg",
            "volume_ir_min",
            "volume_ir_max",
        ):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(
                value,
                (int, float),
            ):
                raise TypeError(f"{name} must be a real number.")

            numeric = float(value)

            if not isfinite(numeric):
                raise ValueError(f"{name} must be finite.")

            object.__setattr__(
                self,
                name,
                numeric,
            )


def default_table4_demand_sets() -> tuple[Table4DemandSetSpec, ...]:
    """Return five explicit controlled substitute demand seeds."""
    return tuple(
        Table4DemandSetSpec(
            demand_set_id=f"demand_set_{index:02d}",
            seed=seed,
        )
        for index, seed in enumerate(
            DEFAULT_TABLE4_DEMAND_SEEDS,
            start=1,
        )
    )


def build_default_table4_cells() -> tuple[Table4CellSpec, ...]:
    """Build the 30 paired Table 4 experimental cells."""
    cells: list[Table4CellSpec] = []

    for service_family in TABLE4_SERVICE_FAMILIES:
        for capacity in TABLE4_CAPACITIES_TEU:
            for demand_set in default_table4_demand_sets():
                cells.append(
                    Table4CellSpec(
                        service_family=service_family,
                        capacity_teu=capacity,
                        demand_set_id=(demand_set.demand_set_id),
                        seed=demand_set.seed,
                        reproduction_class=(demand_set.reproduction_class),
                    )
                )

    return tuple(cells)


def build_default_table4_run_plan() -> tuple[Table4RunSpec, ...]:
    """Build the publication-structure 120-run plan."""
    runs: list[Table4RunSpec] = []

    for cell in build_default_table4_cells():
        for policy_key in TABLE4_POLICY_KEYS:
            runs.append(
                Table4RunSpec(
                    service_family=cell.service_family,
                    capacity_teu=cell.capacity_teu,
                    demand_set_id=cell.demand_set_id,
                    seed=cell.seed,
                    policy_key=policy_key,
                    reproduction_class=(cell.reproduction_class),
                )
            )

    return tuple(runs)


def _improvement_rate(
    value: float,
    baseline: float,
    *,
    metric_name: str,
) -> float:
    """Return percentage improvement relative to DCA."""
    if baseline <= TABLE4_TOLERANCE:
        raise ValueError(
            f"DCA baseline {metric_name} must be strictly positive for IR calculation."
        )

    return 100.0 * (value - baseline) / baseline


def build_table4_paired_comparisons(
    records: Iterable[Table4PolicyRunRecord],
    *,
    require_completed: bool = True,
) -> tuple[Table4PairedComparison, ...]:
    """Build policy-vs-DCA IR using strictly paired inputs."""
    if not isinstance(require_completed, bool):
        raise TypeError("require_completed must be a boolean.")

    selected = tuple(records)

    for record in selected:
        if not isinstance(
            record,
            Table4PolicyRunRecord,
        ):
            raise TypeError("Every record must be a Table4PolicyRunRecord.")

    grouped: dict[
        tuple[str, int, str, int],
        list[Table4PolicyRunRecord],
    ] = defaultdict(list)

    for record in selected:
        grouped[record.cell_key].append(record)

    comparisons: list[Table4PairedComparison] = []

    for cell_key in sorted(grouped):
        cell_records = grouped[cell_key]

        by_policy: dict[str, Table4PolicyRunRecord] = {}

        for record in cell_records:
            if record.policy_key in by_policy:
                raise ValueError(
                    f"Duplicate policy inside paired cell {cell_key}: {record.policy_key}."
                )

            by_policy[record.policy_key] = record

        if set(by_policy) != set(TABLE4_POLICY_KEYS):
            raise ValueError(
                "Every paired Table 4 cell requires exactly "
                f"{TABLE4_POLICY_KEYS}; received "
                f"{tuple(sorted(by_policy))}."
            )

        reproduction_classes = {record.reproduction_class for record in cell_records}
        config_fingerprints = {record.configuration_fingerprint for record in cell_records}
        demand_fingerprints = {record.demand_fingerprint for record in cell_records}

        if len(reproduction_classes) != 1:
            raise ValueError("Paired policies must share the same reproduction class.")

        if len(config_fingerprints) != 1:
            raise ValueError("Paired policies must share the same configuration fingerprint.")

        if len(demand_fingerprints) != 1:
            raise ValueError("Paired policies must use the exact same demand fingerprint.")

        if require_completed and any(not record.completed for record in cell_records):
            raise ValueError(f"Paper-facing IR requires completed policy runs in cell {cell_key}.")

        baseline = by_policy["dca"]

        for policy_key in TABLE4_POLICY_KEYS:
            record = by_policy[policy_key]

            if policy_key == "dca":
                revenue_ir = 0.0
                volume_ir = 0.0
            else:
                revenue_ir = _improvement_rate(
                    record.total_revenue,
                    baseline.total_revenue,
                    metric_name="revenue",
                )
                volume_ir = _improvement_rate(
                    record.transported_volume,
                    baseline.transported_volume,
                    metric_name="transported volume",
                )

            comparisons.append(
                Table4PairedComparison(
                    service_family=record.service_family,
                    capacity_teu=record.capacity_teu,
                    demand_set_id=record.demand_set_id,
                    seed=record.seed,
                    policy_key=policy_key,
                    reproduction_class=(record.reproduction_class),
                    configuration_fingerprint=(record.configuration_fingerprint),
                    demand_fingerprint=(record.demand_fingerprint),
                    revenue_ir_percent=revenue_ir,
                    volume_ir_percent=volume_ir,
                )
            )

    return tuple(comparisons)


def aggregate_table4_comparisons(
    comparisons: Iterable[Table4PairedComparison],
) -> tuple[Table4Aggregate, ...]:
    """Aggregate five paired demand sets to Table 4 Avg/Min/Max."""
    selected = tuple(comparisons)

    for comparison in selected:
        if not isinstance(
            comparison,
            Table4PairedComparison,
        ):
            raise TypeError("Every comparison must be a Table4PairedComparison.")

    grouped: dict[
        tuple[str, int, str, str],
        list[Table4PairedComparison],
    ] = defaultdict(list)

    for comparison in selected:
        grouped[
            (
                comparison.service_family,
                comparison.capacity_teu,
                comparison.policy_key,
                comparison.reproduction_class,
            )
        ].append(comparison)

    aggregates: list[Table4Aggregate] = []

    for group_key in sorted(grouped):
        rows = grouped[group_key]

        demand_set_ids = {row.demand_set_id for row in rows}

        if len(rows) != 5 or len(demand_set_ids) != 5:
            raise ValueError("Every Table 4 aggregate requires five unique paired demand sets.")

        revenue_values = tuple(row.revenue_ir_percent for row in rows)
        volume_values = tuple(row.volume_ir_percent for row in rows)

        service_family, capacity, policy_key, classification = group_key

        aggregates.append(
            Table4Aggregate(
                service_family=service_family,
                capacity_teu=capacity,
                policy_key=policy_key,
                reproduction_class=classification,
                demand_set_count=5,
                revenue_ir_avg=mean(revenue_values),
                revenue_ir_min=min(revenue_values),
                revenue_ir_max=max(revenue_values),
                volume_ir_avg=mean(volume_values),
                volume_ir_min=min(volume_values),
                volume_ir_max=max(volume_values),
            )
        )

    return tuple(aggregates)


def _normalise_csv_row(
    row: dict[str, object],
) -> dict[str, object]:
    """Convert optional values to stable CSV representation."""
    return {key: "" if value is None else value for key, value in row.items()}


def write_table4_run_records_csv(
    records: Iterable[Table4PolicyRunRecord],
    output_path: str | Path,
) -> Path:
    """Write traceable raw policy-run records."""
    selected = tuple(records)

    for record in selected:
        if not isinstance(
            record,
            Table4PolicyRunRecord,
        ):
            raise TypeError("Every record must be a Table4PolicyRunRecord.")

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = tuple(Table4PolicyRunRecord.__dataclass_fields__)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for record in selected:
            writer.writerow(_normalise_csv_row(asdict(record)))

    return path


def write_table4_comparisons_csv(
    comparisons: Iterable[Table4PairedComparison],
    output_path: str | Path,
) -> Path:
    """Write paired policy-versus-DCA comparison rows."""
    selected = tuple(comparisons)

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = tuple(Table4PairedComparison.__dataclass_fields__)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for comparison in selected:
            if not isinstance(
                comparison,
                Table4PairedComparison,
            ):
                raise TypeError("Every comparison must be a Table4PairedComparison.")

            writer.writerow(asdict(comparison))

    return path


def write_table4_aggregates_csv(
    aggregates: Iterable[Table4Aggregate],
    output_path: str | Path,
) -> Path:
    """Write Table 4 Avg/Min/Max aggregate rows."""
    selected = tuple(aggregates)

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = tuple(Table4Aggregate.__dataclass_fields__)

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for aggregate in selected:
            if not isinstance(
                aggregate,
                Table4Aggregate,
            ):
                raise TypeError("Every aggregate must be a Table4Aggregate.")

            writer.writerow(asdict(aggregate))

    return path


def write_table4_run_plan_json(
    output_path: str | Path,
) -> Path:
    """Write deterministic unsolved 120-run experiment manifest."""
    demand_sets = default_table4_demand_sets()
    run_plan = build_default_table4_run_plan()

    payload = {
        "experiment": "phase11_table4",
        "reproduction_class": (CONTROLLED_SUBSTITUTE_INPUT),
        "service_families": list(TABLE4_SERVICE_FAMILIES),
        "capacities_teu": list(TABLE4_CAPACITIES_TEU),
        "policy_keys": list(TABLE4_POLICY_KEYS),
        "demand_sets": [asdict(demand_set) for demand_set in demand_sets],
        "paired_cell_count": 30,
        "policy_run_count": len(run_plan),
        "run_plan": [asdict(run) for run in run_plan],
    }

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return path
