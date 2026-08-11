"""Tests for explicit Table-5 volume-indicator candidates."""

import pytest

from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_volume_indicators import (
    build_table5_volume_indicator_candidates,
)


def test_dca_candidate_rates() -> None:
    ledger = Table5VolumeLedger(
        requested_request_count=800,
        accepted_request_count=351,
        requested_volume=1076.0,
        accepted_volume=447.0,
        truck_volume=0.0,
        final_barge_volume=447.0,
        gross_revenue=103237.5,
        truck_penalty=0.0,
        net_value=103237.5,
    )

    result = build_table5_volume_indicator_candidates(ledger)

    assert result.vtr_requested_volume_pct == pytest.approx(0.0)

    assert result.vfb_requested_volume_pct == pytest.approx(100.0 * 447.0 / 1076.0)

    assert result.vob_requested_volume_pct == pytest.approx(100.0 * 447.0 / 1076.0)

    assert result.voa_request_count_pct == pytest.approx(100.0 * 351.0 / 800.0)

    assert result.voa_requested_volume_pct == pytest.approx(result.vob_requested_volume_pct)


def test_fr_candidate_modal_split_conserves_vob() -> None:
    ledger = Table5VolumeLedger(
        requested_request_count=800,
        accepted_request_count=641,
        requested_volume=1076.0,
        accepted_volume=818.980183372508,
        truck_volume=439.957580864561,
        final_barge_volume=379.022602507947,
        gross_revenue=206987.1893525987,
        truck_penalty=89093.23185979806,
        net_value=117893.95749280065,
    )

    result = build_table5_volume_indicator_candidates(ledger)

    assert result.vob_requested_volume_pct == pytest.approx(76.113399941683)

    assert result.vtr_requested_volume_pct == pytest.approx(40.888250080353)

    assert result.vfb_requested_volume_pct == pytest.approx(35.225149861333)

    assert result.voa_request_count_pct == pytest.approx(80.125)

    assert (result.vfb_requested_volume_pct + result.vtr_requested_volume_pct) == pytest.approx(
        result.vob_requested_volume_pct
    )

    assert result.vob_conservation_residual_pct == pytest.approx(
        0.0,
        abs=1.0e-9,
    )


def test_request_and_volume_acceptance_candidates_are_distinct() -> None:
    ledger = Table5VolumeLedger(
        requested_request_count=10,
        accepted_request_count=5,
        requested_volume=20.0,
        accepted_volume=15.0,
        truck_volume=0.0,
        final_barge_volume=15.0,
        gross_revenue=100.0,
        truck_penalty=0.0,
        net_value=100.0,
    )

    result = build_table5_volume_indicator_candidates(ledger)

    assert result.voa_request_count_pct == pytest.approx(50.0)

    assert result.voa_requested_volume_pct == pytest.approx(75.0)

    assert result.voa_request_count_pct != result.voa_requested_volume_pct


def test_zero_population_returns_zero_rates() -> None:
    ledger = Table5VolumeLedger(
        requested_request_count=0,
        accepted_request_count=0,
        requested_volume=0.0,
        accepted_volume=0.0,
        truck_volume=0.0,
        final_barge_volume=0.0,
        gross_revenue=0.0,
        truck_penalty=0.0,
        net_value=0.0,
    )

    result = build_table5_volume_indicator_candidates(ledger)

    assert result.vtr_requested_volume_pct == pytest.approx(0.0)
    assert result.vfb_requested_volume_pct == pytest.approx(0.0)
    assert result.vob_requested_volume_pct == pytest.approx(0.0)
    assert result.voa_request_count_pct == pytest.approx(0.0)
