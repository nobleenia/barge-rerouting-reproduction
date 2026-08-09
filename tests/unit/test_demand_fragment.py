"""Tests for accepted-demand states and unfinished cargo fragments."""

import pytest

from barge_rerouting.domain import (
    AcceptedDemandState,
    ArcType,
    CustomerCategory,
    Demand,
    DemandFragment,
    TimeSpaceArc,
)


def make_demand(
    *,
    category: CustomerCategory = CustomerCategory.PARTIALLY_SPOT,
) -> Demand:
    """Create a standard test demand."""
    return Demand(
        demand_id="K001",
        volume=10.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=1,
        due_time=5,
        category=category,
        fare_per_teu=20.0,
    )


def test_fragment_exposes_current_terminal_and_time() -> None:
    """A fragment must expose its current terminal-time location."""
    fragment = DemandFragment(
        fragment_id="K001::fragment::0",
        demand_id="K001",
        volume=6.0,
        current_node=("B", 3),
        executed_arc_ids=("transport::0::S1",),
    )

    assert fragment.current_terminal == "B"
    assert fragment.current_time == 3
    assert fragment.volume == pytest.approx(6.0)


def test_fragment_moves_immutably_along_matching_arc() -> None:
    """Executing an arc creates a new fragment without changing the original."""
    fragment = DemandFragment(
        fragment_id="K001::fragment::0",
        demand_id="K001",
        volume=6.0,
        current_node=("A", 1),
    )

    arc = TimeSpaceArc(
        arc_id="transport::0::S1",
        tail=("A", 1),
        head=("B", 2),
        arc_type=ArcType.TRANSPORT,
        nominal_capacity=10.0,
        service_id="S1",
    )

    moved_fragment = fragment.move_along(arc)

    assert fragment.current_node == ("A", 1)
    assert fragment.executed_arc_ids == ()

    assert moved_fragment.current_node == ("B", 2)
    assert moved_fragment.volume == pytest.approx(6.0)
    assert moved_fragment.executed_arc_ids == ("transport::0::S1",)


def test_fragment_rejects_arc_from_different_current_node() -> None:
    """Cargo cannot execute an arc whose tail is elsewhere."""
    fragment = DemandFragment(
        fragment_id="K001::fragment::0",
        demand_id="K001",
        volume=6.0,
        current_node=("A", 1),
    )

    arc = TimeSpaceArc(
        arc_id="transport::0::S1",
        tail=("B", 1),
        head=("C", 2),
        arc_type=ArcType.TRANSPORT,
        nominal_capacity=10.0,
        service_id="S1",
    )

    with pytest.raises(ValueError, match="current node"):
        fragment.move_along(arc)


@pytest.mark.parametrize(
    "invalid_volume",
    [0.0, -1.0, float("nan"), float("inf")],
)
def test_fragment_requires_positive_finite_volume(
    invalid_volume: float,
) -> None:
    """Every unfinished fragment must contain positive finite volume."""
    with pytest.raises(ValueError):
        DemandFragment(
            fragment_id="K001::fragment::0",
            demand_id="K001",
            volume=invalid_volume,
            current_node=("A", 1),
        )


def test_new_acceptance_creates_one_fragment_at_origin() -> None:
    """A newly accepted request begins at its origin and availability time."""
    demand = make_demand()

    state = AcceptedDemandState.at_origin(
        demand,
        acceptance_fraction=0.6,
    )

    assert state.accepted_volume == pytest.approx(6.0)
    assert state.remaining_volume == pytest.approx(6.0)
    assert state.delivered_volume == pytest.approx(0.0)
    assert not state.is_complete

    assert len(state.fragments) == 1
    assert state.fragments[0].current_node == ("A", 1)
    assert state.fragments[0].volume == pytest.approx(6.0)


def test_state_accepts_split_fragments_with_consistent_accounting() -> None:
    """One accepted demand may contain several unfinished fragments."""
    demand = make_demand()

    state = AcceptedDemandState(
        demand=demand,
        acceptance_fraction=1.0,
        fragments=(
            DemandFragment(
                fragment_id="K001::fragment::0",
                demand_id="K001",
                volume=4.0,
                current_node=("B", 2),
                executed_arc_ids=("transport::0::S1",),
            ),
            DemandFragment(
                fragment_id="K001::fragment::1",
                demand_id="K001",
                volume=3.0,
                current_node=("A", 2),
            ),
        ),
        delivered_barge_volume=2.0,
        delivered_truck_volume=1.0,
    )

    assert state.accepted_volume == pytest.approx(10.0)
    assert state.remaining_volume == pytest.approx(7.0)
    assert state.delivered_volume == pytest.approx(3.0)


def test_fully_delivered_state_has_no_fragments() -> None:
    """A completed accepted demand may have an empty fragment tuple."""
    demand = make_demand()

    state = AcceptedDemandState(
        demand=demand,
        acceptance_fraction=1.0,
        fragments=(),
        delivered_barge_volume=8.0,
        delivered_truck_volume=2.0,
    )

    assert state.is_complete
    assert state.remaining_volume == pytest.approx(0.0)
    assert state.delivered_volume == pytest.approx(10.0)


def test_state_rejects_inconsistent_volume_accounting() -> None:
    """Accepted volume must equal delivered plus remaining volume."""
    demand = make_demand()

    with pytest.raises(ValueError, match="accounting is inconsistent"):
        AcceptedDemandState(
            demand=demand,
            acceptance_fraction=1.0,
            fragments=(
                DemandFragment(
                    fragment_id="K001::fragment::0",
                    demand_id="K001",
                    volume=4.0,
                    current_node=("B", 2),
                ),
            ),
            delivered_barge_volume=2.0,
        )


def test_state_rejects_fragment_from_another_demand() -> None:
    """Every fragment must belong to the associated original demand."""
    demand = make_demand()

    with pytest.raises(ValueError, match="demand identifier"):
        AcceptedDemandState(
            demand=demand,
            acceptance_fraction=1.0,
            fragments=(
                DemandFragment(
                    fragment_id="OTHER::fragment::0",
                    demand_id="OTHER",
                    volume=10.0,
                    current_node=("A", 1),
                ),
            ),
        )


def test_state_rejects_duplicate_fragment_identifiers() -> None:
    """Every fragment requires a unique identifier."""
    demand = make_demand()

    with pytest.raises(ValueError, match="must be unique"):
        AcceptedDemandState(
            demand=demand,
            acceptance_fraction=1.0,
            fragments=(
                DemandFragment(
                    fragment_id="duplicate",
                    demand_id="K001",
                    volume=5.0,
                    current_node=("A", 1),
                ),
                DemandFragment(
                    fragment_id="duplicate",
                    demand_id="K001",
                    volume=5.0,
                    current_node=("B", 2),
                ),
            ),
        )


def test_fragment_cannot_precede_availability_time() -> None:
    """Historical cargo state cannot occur before cargo was available."""
    demand = make_demand()

    with pytest.raises(ValueError, match="availability time"):
        AcceptedDemandState(
            demand=demand,
            acceptance_fraction=1.0,
            fragments=(
                DemandFragment(
                    fragment_id="K001::fragment::0",
                    demand_id="K001",
                    volume=10.0,
                    current_node=("A", 0),
                ),
            ),
        )


def test_rejected_demand_does_not_create_accepted_state() -> None:
    """A zero-acceptance decision is recorded as rejection, not commitment."""
    demand = make_demand(category=CustomerCategory.FULLY_SPOT)

    with pytest.raises(ValueError, match="rejected demand"):
        AcceptedDemandState.at_origin(
            demand,
            acceptance_fraction=0.0,
        )


def test_pending_truck_volume_remains_undelivered() -> None:
    """Committed future truck transfer remains unfinished cargo."""
    demand = make_demand()

    state = AcceptedDemandState(
        demand=demand,
        acceptance_fraction=1.0,
        fragments=(
            DemandFragment(
                fragment_id="K001::barge::remaining",
                demand_id="K001",
                volume=6.0,
                current_node=("A", 1),
            ),
        ),
        pending_truck_volume=4.0,
    )

    assert state.accepted_volume == pytest.approx(10.0)
    assert state.pending_truck_volume == pytest.approx(4.0)
    assert state.remaining_volume == pytest.approx(10.0)
    assert state.delivered_volume == pytest.approx(0.0)
    assert not state.is_complete


def test_pending_only_truck_state_is_not_complete() -> None:
    """Cargo is incomplete until its truck-transfer time is reached."""
    demand = make_demand()

    state = AcceptedDemandState(
        demand=demand,
        acceptance_fraction=1.0,
        fragments=(),
        pending_truck_volume=10.0,
    )

    assert state.remaining_volume == pytest.approx(10.0)
    assert state.delivered_volume == pytest.approx(0.0)
    assert not state.is_complete


def test_state_accepts_solver_scale_volume_roundoff() -> None:
    """Solver-scale mass residuals must not invalidate a valid state."""
    demand = Demand(
        demand_id="KROUND",
        volume=2.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=1,
        due_time=5,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=20.0,
    )

    state = AcceptedDemandState(
        demand=demand,
        acceptance_fraction=1.0,
        fragments=(
            DemandFragment(
                fragment_id="KROUND::fragment::0",
                demand_id="KROUND",
                volume=1.9999986295589995,
                current_node=("A", 1),
            ),
        ),
    )

    assert state.accepted_volume == pytest.approx(2.0)
    assert state.remaining_volume == pytest.approx(1.9999986295589995)


def test_state_still_rejects_material_volume_error() -> None:
    """Scale-aware tolerance must not conceal genuine mass imbalance."""
    demand = Demand(
        demand_id="KMATERIAL",
        volume=2.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=1,
        due_time=5,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=20.0,
    )

    with pytest.raises(
        ValueError,
        match="accounting is inconsistent",
    ):
        AcceptedDemandState(
            demand=demand,
            acceptance_fraction=1.0,
            fragments=(
                DemandFragment(
                    fragment_id="KMATERIAL::fragment::0",
                    demand_id="KMATERIAL",
                    volume=1.99,
                    current_node=("A", 1),
                ),
            ),
        )
