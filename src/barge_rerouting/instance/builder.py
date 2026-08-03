"""Assembly of canonical optimisation experiment instances."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import networkx as nx

from barge_rerouting.config import ExperimentConfig
from barge_rerouting.domain import (
    Demand,
    TimeSpaceNode,
)
from barge_rerouting.generation import (
    demand_fingerprint,
    generate_demands,
)
from barge_rerouting.instance.model import (
    DemandNetworkIndex,
    ExperimentInstance,
    NodeFlowIndex,
)
from barge_rerouting.network.arcs import extract_time_space_arcs
from barge_rerouting.network.feasibility import (
    extract_demand_feasible_network,
)
from barge_rerouting.network.time_space import build_time_space_network


def _build_node_flow_indexes(
    graph: nx.MultiDiGraph,
) -> tuple[NodeFlowIndex, ...]:
    """Build incoming and outgoing arc-ID indexes for a feasible graph."""
    arcs = extract_time_space_arcs(graph)

    raw_nodes = tuple(graph.nodes)
    nodes = tuple(
        sorted(
            (cast(TimeSpaceNode, raw_node) for raw_node in raw_nodes),
            key=lambda node: (node[1], node[0]),
        )
    )

    incoming_by_node: dict[TimeSpaceNode, list[str]] = {node: [] for node in nodes}
    outgoing_by_node: dict[TimeSpaceNode, list[str]] = {node: [] for node in nodes}

    for arc in arcs:
        outgoing_by_node[arc.tail].append(arc.arc_id)
        incoming_by_node[arc.head].append(arc.arc_id)

    return tuple(
        NodeFlowIndex(
            node=node,
            incoming_arc_ids=tuple(incoming_by_node[node]),
            outgoing_arc_ids=tuple(outgoing_by_node[node]),
        )
        for node in nodes
    )


def assemble_experiment_instance(
    config: ExperimentConfig,
    *,
    demands: Sequence[Demand] | None = None,
    random_seed: int | None = None,
) -> ExperimentInstance:
    """Assemble one canonical experiment instance.

    Args:
        config:
            Complete validated experiment configuration.
        demands:
            Optional explicit realised demands. When omitted, deterministic
            demands are generated from the configuration.
        random_seed:
            Optional generation-seed override. This cannot be combined with
            explicit demands.

    Returns:
        A validated instance ready for optimisation-model construction.

    Raises:
        ValueError:
            If explicit demands are infeasible or arguments conflict.
    """
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig.")

    if demands is not None and random_seed is not None:
        raise ValueError("random_seed cannot be supplied together with explicit demands.")

    if demands is None:
        selected_demands = generate_demands(
            config,
            random_seed=random_seed,
        )
    else:
        selected_demands = tuple(demands)

        for demand in selected_demands:
            if not isinstance(demand, Demand):
                raise TypeError("Every explicit demand must be a Demand object.")

    selected_demands = tuple(
        sorted(
            selected_demands,
            key=lambda demand: demand.demand_id,
        )
    )

    demand_ids = [demand.demand_id for demand in selected_demands]

    if len(set(demand_ids)) != len(demand_ids):
        raise ValueError("Explicit demand identifiers must be unique.")

    graph = build_time_space_network(
        terminals=config.network.terminals,
        time_periods=config.network.time_periods,
        transport_legs=config.network.transport_legs,
        add_holding_arcs=config.network.add_holding_arcs,
    )

    global_arcs = extract_time_space_arcs(graph)
    global_arc_ids = {arc.arc_id for arc in global_arcs}

    demand_network_indexes: list[DemandNetworkIndex] = []

    for demand in selected_demands:
        feasible_result = extract_demand_feasible_network(
            graph,
            origin=demand.origin,
            destination=demand.destination,
            availability_time=demand.availability_time,
            due_time=demand.due_time,
        )

        if not feasible_result.is_feasible:
            raise ValueError(
                f"Demand {demand.demand_id} has no feasible path from "
                f"{feasible_result.source} to {demand.destination} by "
                f"time {demand.due_time}."
            )

        feasible_arcs = extract_time_space_arcs(feasible_result.graph)
        feasible_arc_ids = tuple(arc.arc_id for arc in feasible_arcs)

        unknown_arc_ids = set(feasible_arc_ids).difference(global_arc_ids)

        if unknown_arc_ids:
            raise ValueError(
                f"Demand {demand.demand_id} contains arcs outside the global time-space network."
            )

        demand_network_indexes.append(
            DemandNetworkIndex(
                demand=demand,
                source=feasible_result.source,
                destination_nodes=feasible_result.destination_nodes,
                feasible_arc_ids=feasible_arc_ids,
                node_flow_indexes=_build_node_flow_indexes(feasible_result.graph),
                original_node_count=feasible_result.original_node_count,
                original_arc_count=feasible_result.original_arc_count,
            )
        )

    nx.freeze(graph)

    return ExperimentInstance(
        config=config,
        graph=graph,
        arcs=global_arcs,
        demands=selected_demands,
        demand_fingerprint=demand_fingerprint(selected_demands),
        demand_network_indexes=tuple(demand_network_indexes),
    )
