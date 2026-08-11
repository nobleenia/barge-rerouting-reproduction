"""Tests for the resumable Phase-11 Table-5 campaign driver."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from barge_rerouting.experiments import (
    phase11_table5_campaign_runner as runner,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    TABLE5_REPORTING_SCHEMA_VERSION,
    Table5CampaignCell,
    build_default_table5_run_plan,
)
from barge_rerouting.experiments.phase11_table5_checkpoint import (
    load_table5_campaign_checkpoint,
)
from barge_rerouting.reporting.table5_allocations import (
    Table5AllocationSnapshot,
    Table5DemandAllocation,
    Table5OriginalArcAllocation,
)
from barge_rerouting.reporting.table5_campaign_record import (
    TABLE5_CAMPAIGN_RECORD_SCHEMA,
    Table5CampaignPolicyRecord,
)
from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
)

DEMAND_FINGERPRINT = "d" * 64


def _fake_inputs(
    cell: Table5CampaignCell,
    *,
    demand_fingerprint: str = DEMAND_FINGERPRINT,
):
    return SimpleNamespace(
        cell=cell,
        configuration_fingerprint=(f"config::{cell.cell_key}"),
        demand_fingerprint=(demand_fingerprint),
        requested_booking_count=1,
        requested_volume=1.0,
        reporting_schema_version=(TABLE5_CAMPAIGN_RECORD_SCHEMA),
    )


def _install_fake_input_builder(
    monkeypatch,
    *,
    demand_fingerprint: str = DEMAND_FINGERPRINT,
) -> None:
    def fake_builder(
        cell,
    ):
        return _fake_inputs(
            cell,
            demand_fingerprint=(demand_fingerprint),
        )

    monkeypatch.setattr(
        runner,
        "build_table5_campaign_cell_inputs",
        fake_builder,
    )


def _record_for(
    inputs,
    run_spec,
) -> Table5CampaignPolicyRecord:
    allocation = Table5AllocationSnapshot(
        demands=(
            Table5DemandAllocation(
                demand_id="K0001",
                requested_volume=1.0,
                acceptance_fraction=1.0,
                accepted_volume=1.0,
                decision_sequence=1,
                decision_time=0,
                original_arc_allocations=(
                    Table5OriginalArcAllocation(
                        arc_id="transport::a",
                        volume=1.0,
                    ),
                ),
                truck_volume=0.0,
                truck_penalty=0.0,
                final_barge_volume=1.0,
            ),
        )
    )

    ledger = Table5VolumeLedger(
        requested_request_count=1,
        accepted_request_count=1,
        requested_volume=1.0,
        accepted_volume=1.0,
        truck_volume=0.0,
        final_barge_volume=1.0,
        gross_revenue=100.0,
        truck_penalty=0.0,
        net_value=100.0,
    )

    legs = (
        ("a", "A", "B"),
        ("b", "B", "C"),
        ("c", "C", "D"),
        ("d", "D", "E"),
    )

    capacity = float(run_spec.capacity_teu)

    service_snapshot = Table5ServiceCapacitySnapshot(
        reporting_time=98,
        instance_fingerprint=(inputs.demand_fingerprint),
        arcs=tuple(
            Table5TransportArcEvidence(
                arc_id=(f"transport::{letter}"),
                service_id=("service::slot01"),
                origin=origin,
                destination=destination,
                departure_time=index,
                arrival_time=index + 1,
                nominal_capacity=capacity,
                actual_capacity=capacity,
                original_load=1.0,
                final_load=1.0,
            )
            for index, (
                letter,
                origin,
                destination,
            ) in enumerate(legs)
        ),
    )

    return Table5CampaignPolicyRecord(
        reporting_schema_version=(TABLE5_CAMPAIGN_RECORD_SCHEMA),
        run_key=run_spec.run_key,
        cell_key=run_spec.cell_key,
        service_family=(run_spec.service_family),
        capacity_teu=(run_spec.capacity_teu),
        policy_key=(run_spec.policy_key),
        configuration_fingerprint=(inputs.configuration_fingerprint),
        demand_fingerprint=(inputs.demand_fingerprint),
        solver_backend="fake",
        completed=True,
        requested_booking_count=1,
        processed_booking_count=1,
        processed_status_count=0,
        feasibility_rejection_count=0,
        ordinary_rejection_count=0,
        solver_failure_count=0,
        runtime_seconds=0.01,
        volume_ledger=ledger,
        allocation_snapshot=allocation,
        service_capacity_snapshot=(service_snapshot),
    )


def _install_fake_executor(
    monkeypatch,
    calls: list[str],
) -> None:
    def fake_execute(
        inputs,
        run_spec,
        *,
        prevalidation_path=None,
    ):
        calls.append(run_spec.run_key)

        return _record_for(
            inputs,
            run_spec,
        )

    monkeypatch.setattr(
        runner,
        "execute_table5_campaign_policy",
        fake_execute,
    )


def test_campaign_schema_alias_is_current() -> None:
    assert TABLE5_REPORTING_SCHEMA_VERSION == TABLE5_CAMPAIGN_RECORD_SCHEMA

    assert TABLE5_CAMPAIGN_RECORD_SCHEMA == "table5-rich-v2"


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        0,
        -1,
        1.5,
    ],
)
def test_max_new_runs_must_be_positive_integer_or_none(
    tmp_path,
    value,
) -> None:
    with pytest.raises(
        ValueError,
        match="max_new_runs",
    ):
        runner.run_table5_campaign(
            output_directory=tmp_path,
            max_new_runs=value,
        )


def test_campaign_checkpoints_after_every_successful_run(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    execution_calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        execution_calls,
    )

    write_lengths: list[int] = []

    real_write = runner.write_table5_campaign_checkpoint

    def recording_write(
        records,
        cell_metadata,
        checkpoint_path,
    ):
        write_lengths.append(len(records))

        return real_write(
            records,
            cell_metadata,
            checkpoint_path,
        )

    monkeypatch.setattr(
        runner,
        "write_table5_campaign_checkpoint",
        recording_write,
    )

    records = runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=3,
    )

    expected = [run.run_key for run in (build_default_table5_run_plan()[:3])]

    assert execution_calls == expected

    assert write_lengths == [
        1,
        2,
        3,
    ]

    assert len(records) == 3

    restored, _ = load_table5_campaign_checkpoint(tmp_path / "campaign_checkpoint.json")

    assert [record.run_key for record in restored] == expected


def test_campaign_resume_skips_completed_runs(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    first_calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        first_calls,
    )

    runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=2,
    )

    second_calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        second_calls,
    )

    records = runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=1,
    )

    run_plan = build_default_table5_run_plan()

    assert first_calls == [
        run_plan[0].run_key,
        run_plan[1].run_key,
    ]

    assert second_calls == [run_plan[2].run_key]

    assert len(records) == 3


def test_fake_campaign_executes_all_24_runs_and_checkpoints_each(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    execution_calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        execution_calls,
    )

    write_lengths: list[int] = []

    real_write = runner.write_table5_campaign_checkpoint

    def recording_write(
        records,
        cell_metadata,
        checkpoint_path,
    ):
        write_lengths.append(len(records))

        return real_write(
            records,
            cell_metadata,
            checkpoint_path,
        )

    monkeypatch.setattr(
        runner,
        "write_table5_campaign_checkpoint",
        recording_write,
    )

    records = runner.run_table5_campaign(output_directory=tmp_path)

    run_plan = build_default_table5_run_plan()

    assert len(run_plan) == 24

    assert execution_calls == [run.run_key for run in run_plan]

    assert write_lengths == list(
        range(
            1,
            25,
        )
    )

    assert len(records) == 24


def test_resume_rejects_rebuilt_demand_fingerprint_drift(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        calls,
    )

    runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=1,
    )

    _install_fake_input_builder(
        monkeypatch,
        demand_fingerprint=("e" * 64),
    )

    calls.clear()

    with pytest.raises(
        RuntimeError,
        match="demand_fingerprint",
    ):
        runner.run_table5_campaign(
            output_directory=tmp_path,
            max_new_runs=1,
        )

    assert calls == []


def test_resume_rejects_metadata_schema_drift(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        calls,
    )

    runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=1,
    )

    checkpoint_path = tmp_path / "campaign_checkpoint.json"

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    first_cell = build_default_table5_run_plan()[0].cell_key

    payload["cell_metadata"][first_cell]["reporting_schema_version"] = "table5-rich-v1"

    checkpoint_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    calls.clear()

    with pytest.raises(
        RuntimeError,
        match="metadata disagrees",
    ):
        runner.run_table5_campaign(
            output_directory=tmp_path,
            max_new_runs=1,
        )

    assert calls == []


def test_failed_next_run_preserves_previous_checkpoint(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_input_builder(monkeypatch)

    initial_calls: list[str] = []

    _install_fake_executor(
        monkeypatch,
        initial_calls,
    )

    runner.run_table5_campaign(
        output_directory=tmp_path,
        max_new_runs=1,
    )

    run_plan = build_default_table5_run_plan()

    def fail_next(
        inputs,
        run_spec,
        *,
        prevalidation_path=None,
    ):
        raise RuntimeError(f"synthetic failure: {run_spec.run_key}")

    monkeypatch.setattr(
        runner,
        "execute_table5_campaign_policy",
        fail_next,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic failure",
    ):
        runner.run_table5_campaign(output_directory=tmp_path)

    restored, _ = load_table5_campaign_checkpoint(tmp_path / "campaign_checkpoint.json")

    assert len(restored) == 1

    assert restored[0].run_key == run_plan[0].run_key


def test_campaign_runner_imports_in_clean_python_process() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from "
                "barge_rerouting.experiments."
                "phase11_table5_campaign_runner "
                "import run_table5_campaign; "
                "assert callable(run_table5_campaign)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
