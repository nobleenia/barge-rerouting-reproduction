"""Tests for explicit Table-5 fill-rate candidates."""

import pytest

from barge_rerouting.experiments.phase11_table5 import (
    default_table5_experiment_spec,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCell,
    build_table5_campaign_cell_inputs,
)
from barge_rerouting.reporting.table5_fill_rates import (
    build_table5_fill_rate_candidates,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
    build_table5_service_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def _arc(
    *,
    index: int,
    origin: str,
    destination: str,
    departure: int,
    final_load: float,
    nominal: float = 10.0,
    actual: float = 10.0,
) -> Table5TransportArcEvidence:
    return Table5TransportArcEvidence(
        arc_id=f"transport::{index}",
        service_id="service::slot01",
        origin=origin,
        destination=destination,
        departure_time=departure,
        arrival_time=departure + 1,
        nominal_capacity=nominal,
        actual_capacity=actual,
        original_load=final_load,
        final_load=final_load,
    )


def _one_sailing(
    *,
    actual: float = 10.0,
) -> Table5ServiceCapacitySnapshot:
    return Table5ServiceCapacitySnapshot(
        reporting_time=10,
        instance_fingerprint="a" * 64,
        arcs=(
            _arc(
                index=1,
                origin="A",
                destination="B",
                departure=0,
                final_load=2.0,
                actual=actual,
            ),
            _arc(
                index=2,
                origin="B",
                destination="C",
                departure=1,
                final_load=4.0,
                actual=actual,
            ),
            _arc(
                index=3,
                origin="C",
                destination="D",
                departure=2,
                final_load=6.0,
                actual=actual,
            ),
            _arc(
                index=4,
                origin="D",
                destination="E",
                departure=3,
                final_load=8.0,
                actual=actual,
            ),
        ),
    )


def test_standard_water_candidates_have_afr_nfr_identity() -> None:
    result = build_table5_fill_rate_candidates(_one_sailing())

    assert result.transport_arc_count == 4
    assert result.sailing_occurrence_count == 1

    assert result.mean_arc_actual_pct == pytest.approx(50.0)

    assert result.mean_arc_nominal_pct == pytest.approx(50.0)

    assert result.capacity_weighted_actual_pct == pytest.approx(50.0)

    assert result.capacity_weighted_nominal_pct == pytest.approx(50.0)

    assert result.mean_sailing_peak_actual_pct == pytest.approx(80.0)

    assert result.mean_sailing_peak_nominal_pct == pytest.approx(80.0)


def test_reduced_actual_capacity_separates_actual_and_nominal_rates() -> None:
    result = build_table5_fill_rate_candidates(_one_sailing(actual=8.0))

    assert result.mean_arc_actual_pct == pytest.approx(62.5)

    assert result.mean_arc_nominal_pct == pytest.approx(50.0)

    assert result.capacity_weighted_actual_pct == pytest.approx(62.5)

    assert result.capacity_weighted_nominal_pct == pytest.approx(50.0)

    assert result.mean_sailing_peak_actual_pct == pytest.approx(100.0)

    assert result.mean_sailing_peak_nominal_pct == pytest.approx(80.0)


def test_empty_frozen_table5_network_returns_zero_fill_rates() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    state = RollingBookingState.empty(inputs.instance)

    snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=state,
        reporting_time=spec.horizon_end,
        status_updates=inputs.pr_updates,
    )

    result = build_table5_fill_rate_candidates(snapshot)

    assert result.transport_arc_count == 112
    assert result.sailing_occurrence_count == 28

    assert result.mean_arc_actual_pct == pytest.approx(0.0)

    assert result.mean_arc_nominal_pct == pytest.approx(0.0)

    assert result.capacity_weighted_actual_pct == pytest.approx(0.0)

    assert result.capacity_weighted_nominal_pct == pytest.approx(0.0)

    assert result.mean_sailing_peak_actual_pct == pytest.approx(0.0)

    assert result.mean_sailing_peak_nominal_pct == pytest.approx(0.0)
