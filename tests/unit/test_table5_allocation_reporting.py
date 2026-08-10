"""Tests for rich per-demand Table-5 reporting records."""

import pytest

from barge_rerouting.reporting.table5_allocations import (
    Table5AllocationSnapshot,
    Table5DemandAllocation,
    Table5OriginalArcAllocation,
)


def _demand(
    *,
    demand_id: str = "K0001",
    accepted: float = 2.0,
    truck: float = 0.5,
) -> Table5DemandAllocation:
    return Table5DemandAllocation(
        demand_id=demand_id,
        requested_volume=2.0,
        acceptance_fraction=(accepted / 2.0),
        accepted_volume=accepted,
        decision_sequence=1,
        decision_time=0,
        original_arc_allocations=(
            Table5OriginalArcAllocation(
                arc_id="transport::a",
                volume=accepted,
            ),
            Table5OriginalArcAllocation(
                arc_id="transport::b",
                volume=accepted,
            ),
        ),
        truck_volume=truck,
        truck_penalty=(100.0 * truck),
        final_barge_volume=(accepted - truck),
    )


def test_arc_flow_sum_is_not_used_as_cargo_volume() -> None:
    """Multiple transport legs must not multiply accepted cargo."""
    demand = _demand(
        accepted=2.0,
        truck=0.0,
    )

    arc_flow_sum = sum(flow.volume for flow in demand.original_arc_allocations)

    assert arc_flow_sum == pytest.approx(4.0)

    assert demand.accepted_volume == pytest.approx(2.0)


def test_per_demand_terminal_allocation_conserves_volume() -> None:
    demand = _demand()

    assert (demand.final_barge_volume + demand.truck_volume) == pytest.approx(
        demand.accepted_volume
    )


def test_snapshot_aggregates_terminal_modal_split() -> None:
    first = _demand(
        demand_id="K0001",
        accepted=2.0,
        truck=0.5,
    )

    second = _demand(
        demand_id="K0002",
        accepted=1.0,
        truck=0.25,
    )

    snapshot = Table5AllocationSnapshot(
        demands=(
            first,
            second,
        )
    )

    assert snapshot.accepted_request_count == 2

    assert snapshot.accepted_volume == pytest.approx(3.0)

    assert snapshot.truck_volume == pytest.approx(0.75)

    assert snapshot.final_barge_volume == pytest.approx(2.25)

    assert (snapshot.final_barge_volume + snapshot.truck_volume) == pytest.approx(
        snapshot.accepted_volume
    )


def test_material_mass_loss_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="terminal allocation is inconsistent",
    ):
        Table5DemandAllocation(
            demand_id="K0001",
            requested_volume=2.0,
            acceptance_fraction=1.0,
            accepted_volume=2.0,
            decision_sequence=1,
            decision_time=0,
            original_arc_allocations=(),
            truck_volume=0.5,
            truck_penalty=50.0,
            final_barge_volume=1.0,
        )


def test_duplicate_demand_ids_are_rejected() -> None:
    first = _demand()
    second = _demand()

    with pytest.raises(
        ValueError,
        match="Demand identifiers must be unique",
    ):
        Table5AllocationSnapshot(
            demands=(
                first,
                second,
            )
        )
