"""Tests for Table-5 campaign policy dispatch without optimisation."""

from types import SimpleNamespace

import pytest

from barge_rerouting.experiments import (
    phase11_table5_campaign_execution as execution,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignRunSpec,
)


def _inputs():
    return SimpleNamespace(
        cell=SimpleNamespace(cell_key=("service_family_1__capacity_10")),
        spec=SimpleNamespace(
            reproduction_class=("controlled_substitute_input"),
            policy_keys=(
                "dca",
                "pr",
                "fr",
            ),
            horizon_end=98,
        ),
        instance=object(),
        booking_timeline=object(),
        pr_timeline=object(),
        pr_updates=("update",),
        truck_penalty_per_teu_by_demand={"K0001": 100.0},
        configuration_fingerprint="config",
        demand_fingerprint="demand",
        requested_booking_count=800,
        requested_volume=1076.0,
    )


def _run_spec(
    policy_key: str,
) -> Table5CampaignRunSpec:
    return Table5CampaignRunSpec(
        service_family="service_family_1",
        capacity_teu=10,
        policy_key=policy_key,
        reproduction_class=("controlled_substitute_input"),
    )


def _capture_record_builder(
    monkeypatch,
):
    captured = {}

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return "campaign-record"

    monkeypatch.setattr(
        execution,
        "build_table5_campaign_policy_record",
        fake_builder,
    )

    return captured


def _capture_service_builder(
    monkeypatch,
):
    captured = {}
    sentinel = object()

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        execution,
        "build_table5_service_capacity_snapshot",
        fake_builder,
    )

    return captured, sentinel


def test_dca_uses_booking_timeline(
    monkeypatch,
) -> None:
    inputs = _inputs()

    run_result = SimpleNamespace(final_state=object())

    def fake_dca(
        instance,
        *,
        timeline=None,
    ):
        assert instance is inputs.instance
        assert timeline is inputs.booking_timeline

        return run_result

    monkeypatch.setattr(
        execution,
        "run_phase11_dca",
        fake_dca,
    )

    record_capture = _capture_record_builder(monkeypatch)

    service_capture, service_sentinel = _capture_service_builder(monkeypatch)

    result = execution.execute_table5_campaign_policy(
        inputs,
        _run_spec("dca"),
    )

    assert result == "campaign-record"

    assert record_capture["run"] is run_result

    assert record_capture["service_capacity_snapshot"] is service_sentinel

    assert service_capture["status_updates"] == ()

    assert service_capture["reporting_time"] == 98


def test_pr_uses_periodic_updates_and_pr_timeline(
    monkeypatch,
) -> None:
    inputs = _inputs()

    run_result = SimpleNamespace(final_state=object())

    def fake_pr(
        instance,
        *,
        status_updates,
        truck_penalty_per_teu_by_demand,
        timeline=None,
    ):
        assert instance is inputs.instance

        assert status_updates is inputs.pr_updates

        assert truck_penalty_per_teu_by_demand is inputs.truck_penalty_per_teu_by_demand

        assert timeline is inputs.pr_timeline

        return run_result

    monkeypatch.setattr(
        execution,
        "run_phase11_table5_pr",
        fake_pr,
    )

    record_capture = _capture_record_builder(monkeypatch)

    service_capture, service_sentinel = _capture_service_builder(monkeypatch)

    result = execution.execute_table5_campaign_policy(
        inputs,
        _run_spec("pr"),
    )

    assert result == "campaign-record"

    assert record_capture["service_capacity_snapshot"] is service_sentinel

    assert service_capture["status_updates"] is inputs.pr_updates


def test_fr_does_not_receive_pr_status_updates(
    monkeypatch,
) -> None:
    inputs = _inputs()

    run_result = SimpleNamespace(final_state=object())

    def fake_fr(
        instance,
        *,
        truck_penalty_per_teu_by_demand,
        status_updates=(),
        timeline=None,
    ):
        assert instance is inputs.instance

        assert truck_penalty_per_teu_by_demand is inputs.truck_penalty_per_teu_by_demand

        assert status_updates == ()

        assert timeline is None

        return run_result

    monkeypatch.setattr(
        execution,
        "run_phase11_table5_fr",
        fake_fr,
    )

    record_capture = _capture_record_builder(monkeypatch)

    service_capture, service_sentinel = _capture_service_builder(monkeypatch)

    result = execution.execute_table5_campaign_policy(
        inputs,
        _run_spec("fr"),
    )

    assert result == "campaign-record"

    assert record_capture["service_capacity_snapshot"] is service_sentinel

    assert service_capture["status_updates"] == ()


def test_foreign_cell_is_rejected_before_execution(
    monkeypatch,
) -> None:
    inputs = _inputs()

    foreign = Table5CampaignRunSpec(
        service_family="service_family_2",
        capacity_teu=10,
        policy_key="dca",
        reproduction_class=("controlled_substitute_input"),
    )

    called = False

    def fake_dca(*args, **kwargs):
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        execution,
        "run_phase11_dca",
        fake_dca,
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        execution.execute_table5_campaign_policy(
            inputs,
            foreign,
        )

    assert not called


def test_foreign_reproduction_class_is_rejected(
    monkeypatch,
) -> None:
    inputs = _inputs()

    run_spec = Table5CampaignRunSpec(
        service_family="service_family_1",
        capacity_teu=10,
        policy_key="dca",
        reproduction_class="foreign",
    )

    called = False

    def fake_dca(*args, **kwargs):
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        execution,
        "run_phase11_dca",
        fake_dca,
    )

    with pytest.raises(
        ValueError,
        match="reproduction class",
    ):
        execution.execute_table5_campaign_policy(
            inputs,
            run_spec,
        )

    assert not called


def test_unknown_policy_is_rejected_before_execution(
    monkeypatch,
) -> None:
    inputs = _inputs()

    run_spec = Table5CampaignRunSpec(
        service_family="service_family_1",
        capacity_teu=10,
        policy_key="unknown",
        reproduction_class=("controlled_substitute_input"),
    )

    called = False

    def fake_dca(*args, **kwargs):
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(
        execution,
        "run_phase11_dca",
        fake_dca,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Table-5 policy",
    ):
        execution.execute_table5_campaign_policy(
            inputs,
            run_spec,
        )

    assert not called


def test_prevalidation_artifact_survives_strict_validation_failure(
    tmp_path,
    monkeypatch,
) -> None:
    """Completed expensive evidence must survive later record rejection."""
    import json

    inputs = _inputs()

    run_result = SimpleNamespace(
        final_state=object(),
    )

    def fake_dca(
        instance,
        *,
        timeline=None,
    ):
        assert instance is inputs.instance
        return run_result

    monkeypatch.setattr(
        execution,
        "run_phase11_dca",
        fake_dca,
    )

    service_sentinel = object()

    monkeypatch.setattr(
        execution,
        "build_table5_service_capacity_snapshot",
        lambda **kwargs: service_sentinel,
    )

    payload = {
        "prevalidation_schema_version": ("table5-prevalidation-v1"),
        "status": ("completed_pending_validation"),
        "run_key": ("service_family_1__capacity_10__dca"),
        "cross_validation_residuals": {
            "final_barge_volume": 1.2e-5,
        },
    }

    monkeypatch.setattr(
        execution,
        "build_table5_campaign_prevalidation_payload",
        lambda **kwargs: dict(payload),
    )

    def fail_strict_builder(**kwargs):
        raise ValueError("synthetic strict validation failure")

    monkeypatch.setattr(
        execution,
        "build_table5_campaign_policy_record",
        fail_strict_builder,
    )

    artifact = tmp_path / "prevalidation" / "service_family_1__capacity_10__dca.json"

    with pytest.raises(
        ValueError,
        match="synthetic strict validation failure",
    ):
        execution.execute_table5_campaign_policy(
            inputs,
            _run_spec("dca"),
            prevalidation_path=artifact,
        )

    assert artifact.exists()

    persisted = json.loads(artifact.read_text(encoding="utf-8"))

    assert persisted["status"] == "completed_pending_validation"

    assert persisted["run_key"] == "service_family_1__capacity_10__dca"

    assert persisted["cross_validation_residuals"]["final_barge_volume"] == pytest.approx(1.2e-5)
