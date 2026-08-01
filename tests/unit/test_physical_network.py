"""Tests for the physical transportation network."""

import networkx as nx
import pytest

from barge_rerouting.network.physical import build_bidirectional_corridor


def test_five_terminal_corridor_has_expected_structure() -> None:
    """The A-E corridor must contain five nodes and eight directed arcs."""
    graph = build_bidirectional_corridor(("A", "B", "C", "D", "E"))

    assert isinstance(graph, nx.DiGraph)
    assert graph.number_of_nodes() == 5
    assert graph.number_of_edges() == 8

    assert graph.has_edge("A", "B")
    assert graph.has_edge("B", "A")
    assert graph.has_edge("D", "E")
    assert graph.has_edge("E", "D")

    assert not graph.has_edge("A", "C")
    assert not graph.has_edge("A", "A")

    assert nx.has_path(graph, "A", "E")
    assert nx.has_path(graph, "E", "A")


def test_corridor_rejects_fewer_than_two_terminals() -> None:
    """A corridor cannot be constructed with fewer than two terminals."""
    with pytest.raises(ValueError, match="at least two"):
        build_bidirectional_corridor(("A",))


def test_corridor_rejects_duplicate_terminals() -> None:
    """Physical terminal identifiers must be unique."""
    with pytest.raises(ValueError, match="unique"):
        build_bidirectional_corridor(("A", "B", "A"))


def test_corridor_rejects_empty_terminal_name() -> None:
    """Every terminal requires a non-empty identifier."""
    with pytest.raises(ValueError, match="non-empty"):
        build_bidirectional_corridor(("A", "", "C"))
