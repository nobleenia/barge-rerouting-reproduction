"""Tests for persisted Table-5 reporting summaries."""

import pytest

from barge_rerouting.reporting.table5_persisted import (
    Table5PersistedSummary,
)


def _record(
    policy: str,
) -> dict[str, object]:
    base: dict[str, object] = {
        "completed": True,
        "pilot_policy": policy,
        "demand_fingerprint": "frozen-demand",
        "requested_booking_count": 800,
        "a036_feasibility_rejection_count": 100,
        "ordinary_rejection_count": 200,
        "solver_failure_count": 0,
        "accepted_volume_teu": 500.0,
        "total_revenue": 100000.0,
        "runtime_seconds": 123.0,
    }

    if policy != "dca":
        base.update(
            {
                "total_truck_volume_teu": 125.0,
                "total_truck_penalty": 25000.0,
                "net_realised_value": 75000.0,
            }
        )

    return base


def test_dca_summary_builds_zero_truck_ledger() -> None:
    summary = Table5PersistedSummary.from_mapping(_record("dca"))

    ledger = summary.build_volume_ledger(requested_volume=1076.0)

    assert summary.accepted_request_count == 500

    assert ledger.requested_volume == pytest.approx(1076.0)
    assert ledger.accepted_volume == pytest.approx(500.0)
    assert ledger.truck_volume == pytest.approx(0.0)
    assert ledger.final_barge_volume == pytest.approx(500.0)


def test_fr_summary_preserves_terminal_allocation() -> None:
    summary = Table5PersistedSummary.from_mapping(_record("fr"))

    ledger = summary.build_volume_ledger(requested_volume=1076.0)

    assert ledger.accepted_volume == pytest.approx(500.0)
    assert ledger.truck_volume == pytest.approx(125.0)
    assert ledger.final_barge_volume == pytest.approx(375.0)

    assert (ledger.final_barge_volume + ledger.truck_volume) == pytest.approx(
        ledger.accepted_volume
    )


def test_inconsistent_persisted_net_is_rejected() -> None:
    record = _record("pr")
    record["net_realised_value"] = 76000.0

    with pytest.raises(
        ValueError,
        match="Persisted net value disagrees",
    ):
        Table5PersistedSummary.from_mapping(record)


def test_solver_failure_summary_is_rejected() -> None:
    record = _record("fr")
    record["solver_failure_count"] = 1

    with pytest.raises(
        ValueError,
        match="zero solver failures",
    ):
        Table5PersistedSummary.from_mapping(record)


def test_rejection_counts_cannot_exceed_requests() -> None:
    record = _record("dca")
    record["a036_feasibility_rejection_count"] = 700
    record["ordinary_rejection_count"] = 200

    with pytest.raises(
        ValueError,
        match="rejection counts exceed",
    ):
        Table5PersistedSummary.from_mapping(record)
