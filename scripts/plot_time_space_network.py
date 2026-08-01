"""Construct and visualise a toy time-space transportation network."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from barge_rerouting.network.time_space import (
    ScheduledTransportLeg,
    build_time_space_network,
)


def main() -> None:
    """Generate and plot a toy time-space network."""
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
            direction="forward",
        ),
        ScheduledTransportLeg(
            service_id="S2",
            origin="B",
            destination="C",
            departure_time=1,
            arrival_time=2,
            capacity=10.0,
            direction="forward",
        ),
        ScheduledTransportLeg(
            service_id="S3",
            origin="A",
            destination="B",
            departure_time=1,
            arrival_time=2,
            capacity=10.0,
            direction="forward",
        ),
        ScheduledTransportLeg(
            service_id="S4",
            origin="B",
            destination="C",
            departure_time=2,
            arrival_time=3,
            capacity=10.0,
            direction="forward",
        ),
    )

    graph = build_time_space_network(
        terminals=terminals,
        time_periods=time_periods,
        transport_legs=transport_legs,
    )

    positions = {
        (terminal, time_period): (time_period, -terminal_index)
        for terminal_index, terminal in enumerate(terminals)
        for time_period in time_periods
    }

    labels = {node: f"{node[0]},{node[1]}" for node in graph.nodes}

    transport_edges = [
        (tail, head)
        for tail, head, _, data in graph.edges(keys=True, data=True)
        if data["arc_type"] == "transport"
    ]

    holding_edges = [
        (tail, head)
        for tail, head, _, data in graph.edges(keys=True, data=True)
        if data["arc_type"] == "holding"
    ]

    figure, axis = plt.subplots(figsize=(10, 5))

    nx.draw_networkx_nodes(
        graph,
        pos=positions,
        ax=axis,
        node_size=1400,
    )
    nx.draw_networkx_labels(
        graph,
        pos=positions,
        labels=labels,
        ax=axis,
        font_size=10,
    )
    nx.draw_networkx_edges(
        graph,
        pos=positions,
        edgelist=holding_edges,
        ax=axis,
        arrows=True,
        width=1.5,
        connectionstyle="arc3,rad=0.0",
    )
    nx.draw_networkx_edges(
        graph,
        pos=positions,
        edgelist=transport_edges,
        ax=axis,
        arrows=True,
        width=2.0,
        connectionstyle="arc3,rad=0.15",
    )

    axis.set_title("Toy time-space network")
    axis.set_axis_off()
    figure.tight_layout()

    output_path = Path("results/figures/time_space_network_toy.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)

    print("Toy time-space network created successfully")
    print(f"Number of nodes: {graph.number_of_nodes()}")
    print(f"Number of arcs:  {graph.number_of_edges()}")
    print(f"Holding arcs:    {len(holding_edges)}")
    print(f"Transport arcs:  {len(transport_edges)}")
    print(f"Directed:        {graph.is_directed()}")
    print(f"Multigraph:      {graph.is_multigraph()}")
    print(f"Acyclic:         {nx.is_directed_acyclic_graph(graph)}")
    print(f"Path (A,0) to (C,2): {nx.has_path(graph, ('A', 0), ('C', 2))}")
    print(f"Path (A,0) to (C,1): {nx.has_path(graph, ('A', 0), ('C', 1))}")
    print(f"Figure:          {output_path}")


if __name__ == "__main__":
    main()
