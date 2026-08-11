"""Tests for the complete Table-5 candidate indicator snapshot."""

import pytest

from barge_rerouting.reporting.table5_indicators import (
    TABLE5_INDICATOR_SCHEMA_VERSION,
    Table5IndicatorSnapshot,
    build_table5_indicator_snapshot,
)
from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
)


def _ledger() -> Table5VolumeLedger:
    return Table5VolumeLedger(
        requested_request_count=10,
        accepted_request_count=6,
        requested_volume=20.0,
        accepted_volume=15.0,
        truck_volume=5.0,
        final_barge_volume=10.0,
        gross_revenue=1000.0,
        truck_penalty=250.0,
        net_value=750.0,
    )


def _capacity_snapshot(
    *,
    actual_capacity: float = 10.0,
) -> Table5ServiceCapacitySnapshot:
    terminals = (
        ("A", "B"),
        ("B", "C"),
        ("C", "D"),
        ("D", "E"),
    )

    return Table5ServiceCapacitySnapshot(
        reporting_time=98,
        instance_fingerprint="a" * 64,
        arcs=tuple(
            Table5TransportArcEvidence(
                arc_id=f"transport::{index}",
                service_id="service::slot01",
                origin=origin,
                destination=destination,
                departure_time=index,
                arrival_time=index + 1,
                nominal_capacity=10.0,
                actual_capacity=actual_capacity,
                original_load=5.0,
                final_load=5.0,
            )
            for index, (
                origin,
                destination,
            ) in enumerate(terminals)
        ),
    )


def test_complete_standard_water_snapshot() -> None:
    result = build_table5_indicator_snapshot(
        volume_ledger=_ledger(),
        service_capacity_snapshot=(_capacity_snapshot()),
        solving_time_seconds=12.5,
    )

    assert result.indicator_schema_version == TABLE5_INDICATOR_SCHEMA_VERSION

    assert result.standard_water

    assert result.gross_revenue == pytest.approx(1000.0)

    assert result.truck_penalty == pytest.approx(250.0)

    assert result.net_realised_value == pytest.approx(750.0)

    assert result.solving_time_seconds == pytest.approx(12.5)

    assert result.fill_rate_candidates.mean_arc_actual_pct == pytest.approx(50.0)

    assert result.fill_rate_candidates.mean_arc_nominal_pct == pytest.approx(50.0)

    assert result.volume_indicator_candidates.vob_requested_volume_pct == pytest.approx(75.0)

    assert result.volume_indicator_candidates.vfb_requested_volume_pct == pytest.approx(50.0)

    assert result.volume_indicator_candidates.vtr_requested_volume_pct == pytest.approx(25.0)


def test_reduced_water_snapshot_is_explicit() -> None:
    result = build_table5_indicator_snapshot(
        volume_ledger=_ledger(),
        service_capacity_snapshot=(_capacity_snapshot(actual_capacity=8.0)),
        solving_time_seconds=5.0,
    )

    assert not result.standard_water

    assert result.fill_rate_candidates.mean_arc_actual_pct == pytest.approx(62.5)

    assert result.fill_rate_candidates.mean_arc_nominal_pct == pytest.approx(50.0)


def test_negative_runtime_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="solving_time_seconds",
    ):
        build_table5_indicator_snapshot(
            volume_ledger=_ledger(),
            service_capacity_snapshot=(_capacity_snapshot()),
            solving_time_seconds=-1.0,
        )


def test_unknown_indicator_schema_is_rejected() -> None:
    valid = build_table5_indicator_snapshot(
        volume_ledger=_ledger(),
        service_capacity_snapshot=(_capacity_snapshot()),
        solving_time_seconds=1.0,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Table-5 indicator schema",
    ):
        Table5IndicatorSnapshot(
            indicator_schema_version="unknown",
            fill_rate_candidates=(valid.fill_rate_candidates),
            volume_indicator_candidates=(valid.volume_indicator_candidates),
            gross_revenue=valid.gross_revenue,
            truck_penalty=valid.truck_penalty,
            net_realised_value=(valid.net_realised_value),
            solving_time_seconds=(valid.solving_time_seconds),
            standard_water=valid.standard_water,
        )
