"""Regression tests for mass-preserving Table-5 reporting."""

import pytest

from barge_rerouting.reporting.table5_allocations import (
    Table5AllocationSnapshot,
    Table5DemandAllocation,
)
from barge_rerouting.reporting.table5_ledger import (
    LEDGER_TOLERANCE,
    Table5VolumeLedger,
)


def _tiny_barge_demand(
    demand_id: str,
) -> Table5DemandAllocation:
    """Return one demand with legitimate sub-tolerance barge mass."""
    return Table5DemandAllocation(
        demand_id=demand_id,
        requested_volume=1.0,
        acceptance_fraction=1.0,
        accepted_volume=1.0,
        decision_sequence=1,
        decision_time=0,
        original_arc_allocations=(),
        truck_volume=0.999994,
        truck_penalty=0.0,
        final_barge_volume=0.000006,
    )


def test_positive_sub_tolerance_mass_is_not_deleted() -> None:
    """Positive physical mass must survive reporting normalization."""
    demand = _tiny_barge_demand("K0001")

    assert demand.final_barge_volume == pytest.approx(
        0.000006,
    )

    assert (demand.truck_volume + demand.final_barge_volume) == pytest.approx(
        demand.accepted_volume,
    )


def test_sub_tolerance_mass_aggregates_consistently() -> None:
    """Per-demand evidence and aggregate ledger must retain same mass."""
    snapshot = Table5AllocationSnapshot(
        demands=(
            _tiny_barge_demand("K0001"),
            _tiny_barge_demand("K0002"),
        )
    )

    ledger = Table5VolumeLedger(
        requested_request_count=2,
        accepted_request_count=2,
        requested_volume=2.0,
        accepted_volume=2.0,
        truck_volume=1.999988,
        final_barge_volume=0.000012,
        gross_revenue=100.0,
        truck_penalty=0.0,
        net_value=100.0,
    )

    assert snapshot.final_barge_volume == pytest.approx(
        0.000012,
    )

    assert ledger.final_barge_volume == pytest.approx(
        0.000012,
    )

    assert abs(snapshot.final_barge_volume - ledger.final_barge_volume) <= LEDGER_TOLERANCE


def test_tiny_negative_numerical_noise_is_still_clamped() -> None:
    """The tolerance remains available for harmless negative noise."""
    ledger = Table5VolumeLedger(
        requested_request_count=0,
        accepted_request_count=0,
        requested_volume=0.0,
        accepted_volume=0.0,
        truck_volume=0.0,
        final_barge_volume=-0.000006,
        gross_revenue=0.0,
        truck_penalty=0.0,
        net_value=0.0,
    )

    assert ledger.final_barge_volume == 0.0
