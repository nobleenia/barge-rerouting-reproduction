"""Tests for Phase 11 Table 4 paired experiment infrastructure."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.experiments import (
    DEFAULT_TABLE4_DEMAND_SEEDS,
    TABLE4_POLICY_KEYS,
    Table4PairedComparison,
    Table4PolicyRunRecord,
    aggregate_table4_comparisons,
    build_default_table4_cells,
    build_default_table4_run_plan,
    build_table4_paired_comparisons,
    default_table4_demand_sets,
    experiment_config_fingerprint,
    write_table4_run_plan_json,
)


def _record(
    *,
    demand_set_id: str = "demand_set_01",
    seed: int = 11001,
    policy_key: str,
    revenue: float,
    volume: float,
    config_fingerprint: str = "a" * 64,
    demand_fingerprint: str = "b" * 64,
) -> Table4PolicyRunRecord:
    """Build one controlled raw run record."""
    return Table4PolicyRunRecord(
        service_family="service_family_1",
        capacity_teu=10,
        demand_set_id=demand_set_id,
        seed=seed,
        policy_key=policy_key,
        reproduction_class="controlled_substitute_input",
        configuration_fingerprint=config_fingerprint,
        demand_fingerprint=demand_fingerprint,
        completed=True,
        total_revenue=revenue,
        transported_volume=volume,
        accepted_volume=volume,
        solver_status="optimal",
        solve_time_seconds=1.0,
        mip_gap=0.0,
        variable_count=10,
        constraint_count=20,
        solver_node_count=0,
    )


def test_default_table4_demand_registry_has_five_fixed_seeds() -> None:
    """Table 4 uses five explicit controlled substitute seeds."""
    demand_sets = default_table4_demand_sets()

    assert len(demand_sets) == 5
    assert tuple(demand_set.seed for demand_set in demand_sets) == DEFAULT_TABLE4_DEMAND_SEEDS
    assert len(set(DEFAULT_TABLE4_DEMAND_SEEDS)) == 5


def test_default_table4_design_has_thirty_paired_cells() -> None:
    """2 families x 3 capacities x 5 demand sets = 30 cells."""
    cells = build_default_table4_cells()

    assert len(cells) == 30
    assert len({cell.cell_key for cell in cells}) == 30


def test_default_table4_plan_has_120_policy_runs() -> None:
    """Every paired cell contains exactly four policies."""
    run_plan = build_default_table4_run_plan()

    assert len(run_plan) == 120

    by_cell: dict[
        tuple[str, int, str, int],
        set[str],
    ] = {}

    for run in run_plan:
        by_cell.setdefault(
            run.cell_key,
            set(),
        ).add(run.policy_key)

    assert len(by_cell) == 30

    for policy_keys in by_cell.values():
        assert policy_keys == set(TABLE4_POLICY_KEYS)


def test_experiment_config_fingerprint_is_deterministic() -> None:
    """Configuration identity changes only when config changes."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    first = experiment_config_fingerprint(config)
    second = experiment_config_fingerprint(config)

    changed = replace(
        config,
        random_seed=config.random_seed + 1,
    )

    third = experiment_config_fingerprint(changed)

    assert len(first) == 64
    assert first == second
    assert third != first


def test_raw_record_derives_revenue_per_accepted_teu() -> None:
    """Revenue/TEU is derived rather than independently entered."""
    record = _record(
        policy_key="dca",
        revenue=125.0,
        volume=10.0,
    )

    assert record.revenue_per_accepted_teu == pytest.approx(12.5)


def test_paired_comparisons_use_dca_denominator() -> None:
    """IR is calculated only after the four paired runs exist."""
    records = (
        _record(
            policy_key="dca",
            revenue=100.0,
            volume=10.0,
        ),
        _record(
            policy_key="dca_rm",
            revenue=110.0,
            volume=11.0,
        ),
        _record(
            policy_key="dca_r",
            revenue=90.0,
            volume=9.0,
        ),
        _record(
            policy_key="dca_rrm",
            revenue=120.0,
            volume=12.0,
        ),
    )

    comparisons = build_table4_paired_comparisons(records)

    assert len(comparisons) == 4

    by_policy = {comparison.policy_key: comparison for comparison in comparisons}

    assert by_policy["dca"].revenue_ir_percent == pytest.approx(0.0)
    assert by_policy["dca_rm"].revenue_ir_percent == pytest.approx(10.0)
    assert by_policy["dca_rm"].volume_ir_percent == pytest.approx(10.0)
    assert by_policy["dca_r"].revenue_ir_percent == pytest.approx(-10.0)
    assert by_policy["dca_rrm"].revenue_ir_percent == pytest.approx(20.0)


def test_paired_comparison_rejects_demand_fingerprint_mismatch() -> None:
    """Policies cannot be compared on different realised demands."""
    records = (
        _record(
            policy_key="dca",
            revenue=100.0,
            volume=10.0,
        ),
        _record(
            policy_key="dca_rm",
            revenue=110.0,
            volume=11.0,
        ),
        _record(
            policy_key="dca_r",
            revenue=115.0,
            volume=11.0,
        ),
        _record(
            policy_key="dca_rrm",
            revenue=120.0,
            volume=12.0,
            demand_fingerprint="c" * 64,
        ),
    )

    with pytest.raises(
        ValueError,
        match="exact same demand fingerprint",
    ):
        build_table4_paired_comparisons(records)


def test_table4_aggregate_uses_exactly_five_paired_sets() -> None:
    """Avg/min/max are calculated over five paired demand sets."""
    revenue_values = (
        0.0,
        10.0,
        20.0,
        30.0,
        40.0,
    )
    volume_values = (
        -10.0,
        0.0,
        10.0,
        20.0,
        30.0,
    )

    comparisons = tuple(
        Table4PairedComparison(
            service_family="service_family_1",
            capacity_teu=10,
            demand_set_id=f"demand_set_{index:02d}",
            seed=11000 + index,
            policy_key="dca_rm",
            reproduction_class="controlled_substitute_input",
            configuration_fingerprint="a" * 64,
            demand_fingerprint=f"{index:x}" * 64,
            revenue_ir_percent=revenue,
            volume_ir_percent=volume,
        )
        for index, (revenue, volume) in enumerate(
            zip(
                revenue_values,
                volume_values,
                strict=True,
            ),
            start=1,
        )
    )

    aggregates = aggregate_table4_comparisons(comparisons)

    assert len(aggregates) == 1

    aggregate = aggregates[0]

    assert aggregate.demand_set_count == 5
    assert aggregate.revenue_ir_avg == pytest.approx(20.0)
    assert aggregate.revenue_ir_min == pytest.approx(0.0)
    assert aggregate.revenue_ir_max == pytest.approx(40.0)
    assert aggregate.volume_ir_avg == pytest.approx(10.0)
    assert aggregate.volume_ir_min == pytest.approx(-10.0)
    assert aggregate.volume_ir_max == pytest.approx(30.0)


def test_table4_plan_manifest_is_machine_readable(
    tmp_path: Path,
) -> None:
    """The unsolved 120-run plan has an automatic JSON manifest."""
    path = write_table4_run_plan_json(tmp_path / "plan.json")

    text = path.read_text(encoding="utf-8")

    assert '"paired_cell_count": 30' in text
    assert '"policy_run_count": 120' in text
    assert '"seed": 11001' in text
    assert '"seed": 11005' in text
