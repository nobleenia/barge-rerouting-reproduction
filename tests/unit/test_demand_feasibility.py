"""Tests for demand-specific time-space-network pruning."""

import pytest

from barge_rerouting.network.feasibility import (
    extract_demand_feasible_network,
)
from barge_rerouting.network.time_space import (
    ScheduledTransportLeg,
    build_time_space_network,
)


def build_toy_graph():
    """Build the standard three-terminal toy graph."""
    return build_time_space_network(
        terminals=("A", "B", "C"),
        time_periods=(0, 1, 2, 3),
        transport_legs=(
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
        ),
    )


def test_pruning_retains_only_paths_reaching_destination_by_deadline() -> None:
    """Only A0-B1-C2 is useful when the C deadline is time 2."""
    full_graph = build_toy_graph()

    result = extract_demand_feasible_network(
        full_graph,
        origin="A",
        destination="C",
        availability_time=0,
        due_time=2,
    )

    assert result.is_feasible
    assert result.source == ("A", 0)
    assert result.destination_nodes == (("C", 2),)

    assert set(result.graph.nodes) == {
        ("A", 0),
        ("B", 1),
        ("C", 2),
    }

    assert result.graph.number_of_edges() == 2
    assert result.removed_node_count == 9
    assert result.removed_arc_count == 11


def test_later_deadline_preserves_multiple_feasible_paths() -> None:
    """A deadline of 3 permits both immediate and delayed options."""
    full_graph = build_toy_graph()

    result = extract_demand_feasible_network(
        full_graph,
        origin="A",
        destination="C",
        availability_time=0,
        due_time=3,
    )

    assert result.is_feasible
    assert ("C", 2) in result.destination_nodes
    assert ("C", 3) in result.destination_nodes
    assert result.graph.number_of_nodes() > 3


def test_infeasible_demand_returns_source_only_subgraph() -> None:
    """A demand unavailable at A1 cannot reach C by time 2."""
    full_graph = build_toy_graph()

    result = extract_demand_feasible_network(
        full_graph,
        origin="A",
        destination="C",
        availability_time=1,
        due_time=2,
    )

    assert not result.is_feasible
    assert result.destination_nodes == ()
    assert set(result.graph.nodes) == {("A", 1)}
    assert result.graph.number_of_edges() == 0


def test_reject_due_time_before_availability() -> None:
    """A deadline cannot occur before cargo becomes available."""
    full_graph = build_toy_graph()

    with pytest.raises(ValueError, match="earlier"):
        extract_demand_feasible_network(
            full_graph,
            origin="A",
            destination="C",
            availability_time=2,
            due_time=1,
        )


def test_reject_unknown_origin() -> None:
    """The demand origin must exist in the physical network."""
    full_graph = build_toy_graph()

    with pytest.raises(ValueError, match="Unknown demand origin"):
        extract_demand_feasible_network(
            full_graph,
            origin="Z",
            destination="C",
            availability_time=0,
            due_time=3,
        )
