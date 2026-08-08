"""Tests for the resumable Phase 11 Table 4 campaign."""

from __future__ import annotations

from pathlib import Path

from barge_rerouting.experiments.phase11_pilot import (
    build_table4_pilot_inputs,
)
from barge_rerouting.experiments.phase11_table4 import (
    TABLE4_POLICY_KEYS,
    Table4PolicyRunRecord,
    build_default_table4_cells,
    build_default_table4_run_plan,
)
from barge_rerouting.experiments.phase11_table4_campaign import (
    build_table4_cell_inputs,
    load_table4_campaign_checkpoint,
    write_table4_campaign_checkpoint,
)


def test_campaign_plan_contains_30_cells_and_120_runs() -> None:
    cells = build_default_table4_cells()
    runs = build_default_table4_run_plan()

    assert len(cells) == 30
    assert len(runs) == 120
    assert len(TABLE4_POLICY_KEYS) == 4


def test_first_campaign_cell_reuses_frozen_pilot_inputs() -> None:
    cells = build_default_table4_cells()

    pilot_cell = next(
        cell
        for cell in cells
        if (
            cell.service_family == "service_family_1"
            and cell.capacity_teu == 10
            and cell.demand_set_id == "demand_set_01"
            and cell.seed == 11001
        )
    )

    campaign = build_table4_cell_inputs(pilot_cell)
    pilot = build_table4_pilot_inputs()

    assert campaign.demand_fingerprint == pilot.demand_fingerprint
    assert campaign.forecast_fingerprint == pilot.forecast_fingerprint

    assert campaign.config.random_seed == pilot.config.random_seed
    assert campaign.config.network == pilot.config.network
    assert campaign.config.demand_generation == pilot.config.demand_generation
    assert campaign.config.solver == pilot.config.solver

    assert campaign.timeline.events == pilot.timeline.events


def test_campaign_checkpoint_round_trip(
    tmp_path: Path,
) -> None:
    record = Table4PolicyRunRecord(
        service_family="service_family_1",
        capacity_teu=10,
        demand_set_id="demand_set_01",
        seed=11001,
        policy_key="dca",
        reproduction_class=("controlled_substitute_input"),
        configuration_fingerprint="a" * 64,
        demand_fingerprint="b" * 64,
        completed=True,
        total_revenue=100.0,
        transported_volume=5.0,
        accepted_volume=5.0,
        solver_status=("all_events_processed"),
        ordinary_rejection_count=2,
        feasibility_rejection_count=1,
        feasibility_rejected_demand_ids=("K0001",),
        solver_failure_count=0,
        solve_time_seconds=1.5,
    )

    metadata = {"cell": {"forecast_fingerprint": ("c" * 64)}}

    path = tmp_path / "checkpoint.json"

    write_table4_campaign_checkpoint(
        [record],
        metadata,
        path,
    )

    records, restored_metadata = load_table4_campaign_checkpoint(path)

    assert records == [record]
    assert restored_metadata == metadata


def test_missing_checkpoint_loads_empty_state(
    tmp_path: Path,
) -> None:
    records, metadata = load_table4_campaign_checkpoint(tmp_path / "missing.json")

    assert records == []
    assert metadata == {}


def test_campaign_imports_in_clean_python_process() -> None:
    """Campaign imports must not depend on prior module import order."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from "
                "barge_rerouting.experiments."
                "phase11_table4_campaign "
                "import run_table4_campaign; "
                "assert callable(run_table4_campaign)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
