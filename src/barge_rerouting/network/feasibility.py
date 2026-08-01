"""Demand-specific reachability and time-space-network pruning."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from barge_rerouting.network.time_space import TimeSpaceNode


@dataclass(frozen=True, slots=True)
class DemandFeasibleNetwork:
    """Time-space subgraph containing only potentially useful demand paths."""

    graph: nx.MultiDiGraph
    source: TimeSpaceNode
    destination_nodes: tuple[TimeSpaceNode, ...]
    original_node_count: int
    original_arc_count: int

    @property
    def is_feasible(self) -> bool:
        """Return whether at least one destination can be reached."""
        return bool(self.destination_nodes)

    @property
    def removed_node_count(self) -> int:
        """Return the number of nodes removed by pruning."""
        return self.original_node_count - int(self.graph.number_of_nodes())

    @property
    def removed_arc_count(self) -> int:
        """Return the number of arcs removed by pruning."""
        return self.original_arc_count - int(self.graph.number_of_edges())


def extract_demand_feasible_network(
    graph: nx.MultiDiGraph,
    *,
    origin: str,
    destination: str,
    availability_time: int,
    due_time: int,
) -> DemandFeasibleNetwork:
    """Extract nodes and arcs belonging to a feasible source-destination path.

    A node is retained only when it:

    1. is reachable from the demand source; and
    2. can reach at least one eligible destination-time node by the deadline.

    Args:
        graph:
            Full time-space network.
        origin:
            Physical origin terminal.
        destination:
            Physical destination terminal.
        availability_time:
            Earliest time at which cargo is available at the origin.
        due_time:
            Latest permitted destination arrival time.

    Returns:
        A demand-specific pruned time-space network.

    Raises:
        ValueError:
            If demand data or terminal identifiers are invalid.
    """
    if availability_time < 0:
        raise ValueError("availability_time must be non-negative.")
    if due_time < availability_time:
        raise ValueError("due_time must not be earlier than availability_time.")
    if origin == destination:
        raise ValueError("origin and destination must be different.")

    terminals = {node[0] for node in graph.nodes}

    if origin not in terminals:
        raise ValueError(f"Unknown demand origin: {origin}")
    if destination not in terminals:
        raise ValueError(f"Unknown demand destination: {destination}")

    source: TimeSpaceNode = (origin, availability_time)

    if source not in graph:
        raise ValueError(f"The demand source terminal-time node does not exist: {source}")

    eligible_destinations = tuple(
        sorted(
            (
                node
                for node in graph.nodes
                if node[0] == destination and availability_time <= node[1] <= due_time
            ),
            key=lambda node: node[1],
        )
    )

    reachable_from_source = {
        source,
        *nx.descendants(graph, source),
    }

    reachable_destinations = tuple(
        node for node in eligible_destinations if node in reachable_from_source
    )

    if not reachable_destinations:
        source_only_graph = graph.subgraph({source}).copy()

        return DemandFeasibleNetwork(
            graph=source_only_graph,
            source=source,
            destination_nodes=(),
            original_node_count=graph.number_of_nodes(),
            original_arc_count=graph.number_of_edges(),
        )

    can_reach_destination: set[TimeSpaceNode] = set()

    for destination_node in reachable_destinations:
        can_reach_destination.add(destination_node)
        can_reach_destination.update(nx.ancestors(graph, destination_node))

    retained_nodes = reachable_from_source.intersection(can_reach_destination)
    pruned_graph = graph.subgraph(retained_nodes).copy()

    return DemandFeasibleNetwork(
        graph=pruned_graph,
        source=source,
        destination_nodes=reachable_destinations,
        original_node_count=graph.number_of_nodes(),
        original_arc_count=graph.number_of_edges(),
    )
