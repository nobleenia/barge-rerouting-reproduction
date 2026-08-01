"""Construct and visualise the five-terminal physical corridor."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from barge_rerouting.network.physical import build_bidirectional_corridor


def main() -> None:
    """Generate the physical-corridor figure."""
    terminals = ("A", "B", "C", "D", "E")
    graph = build_bidirectional_corridor(terminals)

    positions = {terminal: (index, 0.0) for index, terminal in enumerate(terminals)}

    figure, axis = plt.subplots(figsize=(10, 3))

    nx.draw_networkx(
        graph,
        pos=positions,
        ax=axis,
        with_labels=True,
        arrows=True,
        connectionstyle="arc3,rad=0.12",
        node_size=1_800,
        font_size=12,
    )

    axis.set_title("Bidirectional physical barge corridor")
    axis.set_axis_off()
    figure.tight_layout()

    output_path = Path("results/figures/physical_corridor.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(figure)

    print("Physical network created successfully")
    print(f"Nodes: {list(graph.nodes)}")
    print(f"Arcs:  {list(graph.edges)}")
    print(f"Number of nodes: {graph.number_of_nodes()}")
    print(f"Number of arcs:  {graph.number_of_edges()}")
    print(f"Directed:        {graph.is_directed()}")
    print(f"Path A to E:     {nx.has_path(graph, 'A', 'E')}")
    print(f"Figure:          {output_path}")


if __name__ == "__main__":
    main()
