"""Construction and validation of physical transportation networks."""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx


def build_bidirectional_corridor(terminals: Sequence[str]) -> nx.DiGraph:
    """Build a directed corridor with arcs in both directions.

    For terminals A, B, C, the function creates:

        A -> B
        B -> A
        B -> C
        C -> B

    It does not create direct arcs A -> C or C -> A.

    Args:
        terminals:
            Ordered physical terminals along the corridor.

    Returns:
        A directed NetworkX graph.

    Raises:
        ValueError:
            If fewer than two terminals are supplied, terminal names are empty,
            or terminal names are duplicated.
    """
    ordered_terminals = tuple(terminals)

    if len(ordered_terminals) < 2:
        raise ValueError("A corridor requires at least two terminals.")

    if any(not terminal.strip() for terminal in ordered_terminals):
        raise ValueError("Terminal names must be non-empty strings.")

    if len(set(ordered_terminals)) != len(ordered_terminals):
        raise ValueError("Terminal names must be unique.")

    graph = nx.DiGraph(name="bidirectional_physical_corridor")
    graph.add_nodes_from(ordered_terminals)

    consecutive_pairs = zip(
        ordered_terminals[:-1],
        ordered_terminals[1:],
        strict=True,
    )

    for left_terminal, right_terminal in consecutive_pairs:
        graph.add_edge(
            left_terminal,
            right_terminal,
            direction="forward",
        )
        graph.add_edge(
            right_terminal,
            left_terminal,
            direction="reverse",
        )

    return graph
