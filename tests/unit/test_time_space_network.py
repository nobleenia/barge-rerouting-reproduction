"""Tests for time-space transportation networks."""

import networkx as nx
import pytest

from barge_rerouting.network.time_space import (
    ScheduledTransportLeg,
    build_time_space_network,
)


def build_toy_graph() -> nx.MultiDiGraph:
    """Construct a reusable toy time-space graph."""
    terminals = ("A", "B", "C")
    time_periods = (0, 1, 2, 3)

    transport_legs = (
        ScheduledTransportLeg(
            service_id="S1",
            origin="A",
            destination="B",
            departure_time=0,
            arrival_time=1,
            capacity=10.0,
        ),
        ScheduledTransportLeg(
            service_id="S2",
            origin="B",
            destination="C",
            departure_time=1,
            arrival_time=2,
            capacity=10.0,
        ),
        ScheduledTransportLeg(
            service_id="S3",
            origin="A",
            destination="B",
            departure_time=1,
            arrival_time=2,
            capacity=10.0,
        ),
        ScheduledTransportLeg(
            service_id="S4",
            origin="B",
            destination="C",
            departure_time=2,
            arrival_time=3,
            capacity=10.0,
        ),
    )

    return build_time_space_network(
        terminals=terminals,
        time_periods=time_periods,
        transport_legs=transport_legs,
    )


def test_toy_time_space_graph_has_expected_node_and_arc_counts() -> None:
    """The toy graph must contain the expected nodes and arcs."""
    graph = build_toy_graph()

    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_nodes() == 12
    assert graph.number_of_edges() == 13


def test_toy_graph_contains_holding_and_transport_arcs() -> None:
    """The graph must contain both holding and scheduled transport arcs."""
    graph = build_toy_graph()

    holding_data = graph.get_edge_data(("A", 0), ("A", 1))
    transport_data = graph.get_edge_data(("A", 0), ("B", 1))

    assert holding_data is not None
    assert transport_data is not None

    assert any(attributes["arc_type"] == "holding" for attributes in holding_data.values())
    assert any(attributes["arc_type"] == "transport" for attributes in transport_data.values())


def test_toy_graph_has_time_feasible_path_to_c2() -> None:
    """A path from (A,0) to (C,2) should exist."""
    graph = build_toy_graph()

    assert nx.has_path(graph, ("A", 0), ("C", 2))


def test_toy_graph_has_no_path_to_c1() -> None:
    """A path from (A,0) to (C,1) should not exist."""
    graph = build_toy_graph()

    assert not nx.has_path(graph, ("A", 0), ("C", 1))


def test_time_space_graph_is_acyclic() -> None:
    """All arcs move forward in time, so the graph must be acyclic."""
    graph = build_toy_graph()

    assert nx.is_directed_acyclic_graph(graph)


def test_parallel_transport_services_are_preserved() -> None:
    """Two services with identical endpoints must remain separate arcs."""
    parallel_legs = (
        ScheduledTransportLeg(
            service_id="S1",
            origin="A",
            destination="B",
            departure_time=0,
            arrival_time=1,
            capacity=10.0,
        ),
        ScheduledTransportLeg(
            service_id="S2",
            origin="A",
            destination="B",
            departure_time=0,
            arrival_time=1,
            capacity=15.0,
        ),
    )

    graph = build_time_space_network(
        terminals=("A", "B"),
        time_periods=(0, 1),
        transport_legs=parallel_legs,
    )

    edge_data = graph.get_edge_data(("A", 0), ("B", 1))

    assert edge_data is not None
    assert len(edge_data) == 2
    assert {attributes["service_id"] for attributes in edge_data.values()} == {"S1", "S2"}


def test_reject_unsorted_time_periods() -> None:
    """Time periods must be sorted in ascending order."""
    with pytest.raises(ValueError, match="sorted"):
        build_time_space_network(
            terminals=("A", "B"),
            time_periods=(1, 0, 2),
            transport_legs=(),
        )


def test_reject_leg_with_nonforward_time() -> None:
    """A transport leg must arrive strictly after it departs."""
    with pytest.raises(ValueError, match="strictly greater"):
        ScheduledTransportLeg(
            service_id="S_bad",
            origin="A",
            destination="B",
            departure_time=2,
            arrival_time=2,
            capacity=10.0,
        )


def test_reject_leg_with_unknown_terminal() -> None:
    """Transport-leg terminals must belong to the time-space network."""
    bad_leg = ScheduledTransportLeg(
        service_id="S_bad",
        origin="A",
        destination="Z",
        departure_time=0,
        arrival_time=1,
        capacity=10.0,
    )

    with pytest.raises(ValueError, match="Unknown transport-leg destination"):
        build_time_space_network(
            terminals=("A", "B", "C"),
            time_periods=(0, 1, 2),
            transport_legs=(bad_leg,),
        )
