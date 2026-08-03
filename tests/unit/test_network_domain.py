"""Tests for service-leg and solver-ready arc domain objects."""

import networkx as nx
import pytest

from barge_rerouting.domain import (
    ArcType,
    ScheduledTransportLeg,
    TimeSpaceArc,
)
from barge_rerouting.network.arcs import (
    extract_time_space_arcs,
    index_arcs_by_id,
)
from barge_rerouting.network.time_space import build_time_space_network


def test_scheduled_leg_exposes_tail_head_and_duration() -> None:
    """A scheduled leg must identify its time-space endpoints."""
    leg = ScheduledTransportLeg(
        service_id="S1",
        origin="A",
        destination="B",
        departure_time=2,
        arrival_time=5,
        capacity=10,
        direction="forward",
    )

    assert leg.tail == ("A", 2)
    assert leg.head == ("B", 5)
    assert leg.duration == 3
    assert leg.capacity == pytest.approx(10.0)


def test_holding_arc_requires_same_terminal_and_no_capacity() -> None:
    """A valid holding arc waits at one physical terminal."""
    arc = TimeSpaceArc(
        arc_id="holding::A::0->1",
        tail=("A", 0),
        head=("A", 1),
        arc_type=ArcType.HOLDING,
        nominal_capacity=None,
    )

    assert arc.is_holding
    assert not arc.is_transport
    assert arc.duration == 1

    with pytest.raises(ValueError, match="same physical terminal"):
        TimeSpaceArc(
            arc_id="bad-holding",
            tail=("A", 0),
            head=("B", 1),
            arc_type=ArcType.HOLDING,
            nominal_capacity=None,
        )


def test_transport_arc_requires_distinct_terminals_capacity_and_service() -> None:
    """A valid transport arc must represent a scheduled movement."""
    arc = TimeSpaceArc(
        arc_id="transport::0::S1",
        tail=("A", 0),
        head=("B", 1),
        arc_type=ArcType.TRANSPORT,
        nominal_capacity=10.0,
        service_id="S1",
        direction="forward",
    )

    assert arc.is_transport
    assert not arc.is_holding
    assert arc.nominal_capacity == pytest.approx(10.0)

    with pytest.raises(ValueError, match="different physical terminals"):
        TimeSpaceArc(
            arc_id="bad-transport",
            tail=("A", 0),
            head=("A", 1),
            arc_type=ArcType.TRANSPORT,
            nominal_capacity=10.0,
            service_id="S1",
        )

    with pytest.raises(ValueError, match="requires nominal capacity"):
        TimeSpaceArc(
            arc_id="bad-capacity",
            tail=("A", 0),
            head=("B", 1),
            arc_type=ArcType.TRANSPORT,
            nominal_capacity=None,
            service_id="S1",
        )


def test_arcs_must_move_forward_in_time() -> None:
    """No time-space arc may return to the same or an earlier time."""
    with pytest.raises(ValueError, match="strictly forward"):
        TimeSpaceArc(
            arc_id="bad-time",
            tail=("A", 2),
            head=("B", 2),
            arc_type=ArcType.TRANSPORT,
            nominal_capacity=10.0,
            service_id="S1",
        )


def test_graph_edges_are_extracted_as_solver_ready_arcs() -> None:
    """The standard toy graph must yield thirteen typed arc objects."""
    graph = build_time_space_network(
        terminals=("A", "B", "C"),
        time_periods=(0, 1, 2, 3),
        transport_legs=(
            ScheduledTransportLeg("S1", "A", "B", 0, 1, 10.0),
            ScheduledTransportLeg("S2", "B", "C", 1, 2, 10.0),
            ScheduledTransportLeg("S3", "A", "B", 1, 2, 15.0),
            ScheduledTransportLeg("S4", "B", "C", 2, 3, 15.0),
        ),
    )

    arcs = extract_time_space_arcs(graph)
    arc_index = index_arcs_by_id(arcs)

    assert len(arcs) == 13
    assert len(arc_index) == 13

    holding_arcs = [arc for arc in arcs if arc.is_holding]
    transport_arcs = [arc for arc in arcs if arc.is_transport]

    assert len(holding_arcs) == 9
    assert len(transport_arcs) == 4
    assert all(arc.nominal_capacity is None for arc in holding_arcs)
    assert all(arc.nominal_capacity is not None for arc in transport_arcs)


def test_parallel_services_remain_distinct_solver_arcs() -> None:
    """Parallel NetworkX edges must retain separate arc identifiers."""
    graph = build_time_space_network(
        terminals=("A", "B"),
        time_periods=(0, 1),
        transport_legs=(
            ScheduledTransportLeg("S1", "A", "B", 0, 1, 10.0),
            ScheduledTransportLeg("S2", "A", "B", 0, 1, 15.0),
        ),
    )

    arcs = extract_time_space_arcs(graph)
    transport_arcs = [arc for arc in arcs if arc.is_transport]

    assert isinstance(graph, nx.MultiDiGraph)
    assert len(transport_arcs) == 2
    assert {arc.service_id for arc in transport_arcs} == {"S1", "S2"}
    assert {arc.nominal_capacity for arc in transport_arcs} == {10.0, 15.0}


def test_arc_index_rejects_duplicate_identifiers() -> None:
    """CPLEX indexing requires globally unique arc identifiers."""
    arc = TimeSpaceArc(
        arc_id="transport::0::S1",
        tail=("A", 0),
        head=("B", 1),
        arc_type=ArcType.TRANSPORT,
        nominal_capacity=10.0,
        service_id="S1",
    )

    with pytest.raises(ValueError, match="Duplicate arc identifier"):
        index_arcs_by_id((arc, arc))
