"""Construction of time-space transportation networks."""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from barge_rerouting.domain.network import ArcType, TimeSpaceNode
from barge_rerouting.domain.service import ScheduledTransportLeg


def build_time_space_network(
    terminals: Sequence[str],
    time_periods: Sequence[int],
    transport_legs: Sequence[ScheduledTransportLeg],
    *,
    add_holding_arcs: bool = True,
) -> nx.MultiDiGraph:
    """Build a directed time-space multigraph.

    A multigraph is used because several scheduled services may connect the
    same departure and arrival terminal-time nodes.

    Args:
        terminals:
            Ordered physical terminals.
        time_periods:
            Ordered discrete time points.
        transport_legs:
            Scheduled service legs.
        add_holding_arcs:
            Whether to add waiting arcs between consecutive listed periods.

    Returns:
        A directed NetworkX multigraph whose nodes are terminal-time pairs.

    Raises:
        ValueError:
            If any input is invalid.
    """
    ordered_terminals = tuple(terminals)
    ordered_times = tuple(time_periods)
    scheduled_legs = tuple(transport_legs)

    if not ordered_terminals:
        raise ValueError("At least one terminal is required.")
    if len(ordered_times) < 2:
        raise ValueError("At least two time periods are required.")
    if any(not terminal.strip() for terminal in ordered_terminals):
        raise ValueError("Terminal names must be non-empty strings.")
    if len(set(ordered_terminals)) != len(ordered_terminals):
        raise ValueError("Terminal names must be unique.")
    if len(set(ordered_times)) != len(ordered_times):
        raise ValueError("Time periods must be unique.")
    if any(time_period < 0 for time_period in ordered_times):
        raise ValueError("Time periods must be non-negative.")
    if tuple(sorted(ordered_times)) != ordered_times:
        raise ValueError("Time periods must be sorted in ascending order.")

    terminal_set = set(ordered_terminals)
    time_set = set(ordered_times)

    graph = nx.MultiDiGraph(name="time_space_network")

    for terminal in ordered_terminals:
        for time_period in ordered_times:
            node: TimeSpaceNode = (terminal, time_period)
            graph.add_node(
                node,
                terminal=terminal,
                time=time_period,
                node_type="terminal_time",
            )

    if add_holding_arcs:
        for terminal in ordered_terminals:
            for departure_time, arrival_time in zip(
                ordered_times[:-1],
                ordered_times[1:],
                strict=True,
            ):
                edge_key = f"holding::{terminal}::{departure_time}->{arrival_time}"

                graph.add_edge(
                    (terminal, departure_time),
                    (terminal, arrival_time),
                    key=edge_key,
                    arc_id=edge_key,
                    arc_type=ArcType.HOLDING.value,
                    duration=arrival_time - departure_time,
                    capacity=None,
                    service_id=None,
                    direction=None,
                )

    for leg_index, leg in enumerate(scheduled_legs):
        if leg.origin not in terminal_set:
            raise ValueError(f"Unknown transport-leg origin: {leg.origin}")
        if leg.destination not in terminal_set:
            raise ValueError(f"Unknown transport-leg destination: {leg.destination}")
        if leg.departure_time not in time_set:
            raise ValueError(f"Unknown departure time: {leg.departure_time}")
        if leg.arrival_time not in time_set:
            raise ValueError(f"Unknown arrival time: {leg.arrival_time}")

        edge_key = f"transport::{leg_index}::{leg.service_id}"

        graph.add_edge(
            leg.tail,
            leg.head,
            key=edge_key,
            arc_id=edge_key,
            arc_type=ArcType.TRANSPORT.value,
            duration=leg.duration,
            capacity=leg.capacity,
            service_id=leg.service_id,
            direction=leg.direction,
        )

    return graph
