"""Fragment-specific feasible networks for demand rerouting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import networkx as nx

from barge_rerouting.domain import (
    ArcType,
    Demand,
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.instance import (
    AuxiliarySinkArc,
    ExperimentInstance,
    NodeFlowIndex,
    auxiliary_sink_id_for,
    build_auxiliary_sink_arcs,
)
from barge_rerouting.network.arcs import extract_time_space_arcs
from barge_rerouting.rerouting.capacity import (
    ReroutingCapacitySnapshot,
)
from barge_rerouting.rerouting.in_transit import (
    ReroutingDecisionSnapshot,
    ReroutingFragmentDecisionState,
)


def _normalise_arc_ids(
    value: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate and deterministically sort unique arc identifiers."""
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    arc_ids: list[str] = []

    for arc_id in value:
        if not isinstance(arc_id, str):
            raise TypeError(f"Every identifier in {field_name} must be a string.")

        normalised_arc_id = arc_id.strip()

        if not normalised_arc_id:
            raise ValueError(f"Every identifier in {field_name} must be non-empty.")

        arc_ids.append(normalised_arc_id)

    if len(set(arc_ids)) != len(arc_ids):
        raise ValueError(f"{field_name} must not contain duplicates.")

    return tuple(sorted(arc_ids))


def _build_node_flow_indexes(
    graph: nx.MultiDiGraph,
) -> tuple[NodeFlowIndex, ...]:
    """Build physical incoming and outgoing indexes for a fragment graph."""
    arcs = extract_time_space_arcs(graph)

    nodes = tuple(
        sorted(
            (cast(TimeSpaceNode, raw_node) for raw_node in graph.nodes),
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


@dataclass(frozen=True, slots=True)
class FragmentNetworkIndex:
    """Solver-ready feasible network for one unfinished fragment."""

    fragment_state: ReroutingFragmentDecisionState
    demand: Demand
    source: TimeSpaceNode
    destination_nodes: tuple[TimeSpaceNode, ...]
    auxiliary_sink_id: str
    sink_arcs: tuple[AuxiliarySinkArc, ...]
    feasible_arc_ids: tuple[str, ...]
    node_flow_indexes: tuple[NodeFlowIndex, ...]
    original_node_count: int
    original_arc_count: int

    def __post_init__(self) -> None:
        """Validate fragment-network consistency."""
        if not isinstance(
            self.fragment_state,
            ReroutingFragmentDecisionState,
        ):
            raise TypeError("fragment_state must be a ReroutingFragmentDecisionState.")

        if not isinstance(self.demand, Demand):
            raise TypeError("demand must be a Demand object.")

        if self.demand.demand_id != self.fragment_state.demand_id:
            raise ValueError("Fragment network demand must match the fragment.")

        source = validate_time_space_node(
            self.source,
            field_name="source",
        )

        if source != self.fragment_state.rerouting_source:
            raise ValueError("Fragment-network source must equal the effective rerouting source.")

        if source[1] > self.demand.due_time:
            raise ValueError("Fragment rerouting source cannot occur after its due time.")

        if not isinstance(self.destination_nodes, tuple):
            raise TypeError("destination_nodes must be a tuple.")

        destination_nodes = tuple(
            sorted(
                (
                    validate_time_space_node(
                        node,
                        field_name="destination_node",
                    )
                    for node in self.destination_nodes
                ),
                key=lambda node: (node[1], node[0]),
            )
        )

        if not destination_nodes:
            raise ValueError("A fragment network requires a reachable destination.")

        if len(set(destination_nodes)) != len(destination_nodes):
            raise ValueError("destination_nodes must be unique.")

        for node in destination_nodes:
            if node[0] != self.demand.destination:
                raise ValueError(
                    "Every fragment destination node must use the original demand destination."
                )

            if node[1] < source[1]:
                raise ValueError("A destination node cannot precede the rerouting source.")

            if node[1] > self.demand.due_time:
                raise ValueError("A destination node cannot occur after the due time.")

        if not isinstance(self.auxiliary_sink_id, str):
            raise TypeError("auxiliary_sink_id must be a string.")

        auxiliary_sink_id = self.auxiliary_sink_id.strip()
        expected_sink_id = auxiliary_sink_id_for(self.fragment_state.fragment_id)

        if auxiliary_sink_id != expected_sink_id:
            raise ValueError("Fragment auxiliary sink must use the fragment identifier.")

        if not isinstance(self.sink_arcs, tuple):
            raise TypeError("sink_arcs must be a tuple.")

        sink_arcs = tuple(self.sink_arcs)

        if not sink_arcs:
            raise ValueError("A fragment network requires auxiliary sink arcs.")

        for sink_arc in sink_arcs:
            if not isinstance(sink_arc, AuxiliarySinkArc):
                raise TypeError("Every sink arc must be an AuxiliarySinkArc.")

            if sink_arc.demand_id != self.fragment_state.fragment_id:
                raise ValueError("Fragment sink arcs must reference the fragment ID.")

            if sink_arc.sink_id != auxiliary_sink_id:
                raise ValueError("Fragment sink arcs must terminate at the indexed sink.")

        sink_tails = tuple(sink_arc.tail for sink_arc in sink_arcs)

        if set(sink_tails) != set(destination_nodes):
            raise ValueError("Sink arcs must cover every destination node exactly once.")

        if len(set(sink_tails)) != len(sink_tails):
            raise ValueError("Each destination node requires one fragment sink arc.")

        feasible_arc_ids = _normalise_arc_ids(
            self.feasible_arc_ids,
            field_name="feasible_arc_ids",
        )

        if not isinstance(self.node_flow_indexes, tuple):
            raise TypeError("node_flow_indexes must be a tuple.")

        node_flow_indexes = tuple(self.node_flow_indexes)

        if not node_flow_indexes:
            raise ValueError("A fragment network requires node-flow indexes.")

        for node_index in node_flow_indexes:
            if not isinstance(node_index, NodeFlowIndex):
                raise TypeError("Every node-flow index must be a NodeFlowIndex.")

        indexed_nodes = tuple(node_index.node for node_index in node_flow_indexes)

        if len(set(indexed_nodes)) != len(indexed_nodes):
            raise ValueError("Fragment node-flow indexes must use unique nodes.")

        if source not in indexed_nodes:
            raise ValueError("The fragment source must be an indexed node.")

        if not set(destination_nodes).issubset(indexed_nodes):
            raise ValueError("Every fragment destination must be indexed.")

        incoming_occurrences: list[str] = []
        outgoing_occurrences: list[str] = []

        for node_index in node_flow_indexes:
            incoming_occurrences.extend(node_index.incoming_arc_ids)
            outgoing_occurrences.extend(node_index.outgoing_arc_ids)

        if len(incoming_occurrences) != len(set(incoming_occurrences)):
            raise ValueError("Each physical arc must enter exactly one indexed node.")

        if len(outgoing_occurrences) != len(set(outgoing_occurrences)):
            raise ValueError("Each physical arc must leave exactly one indexed node.")

        if set(incoming_occurrences) != set(feasible_arc_ids):
            raise ValueError("Incoming indexes do not match the fragment arc set.")

        if set(outgoing_occurrences) != set(feasible_arc_ids):
            raise ValueError("Outgoing indexes do not match the fragment arc set.")

        if isinstance(self.original_node_count, bool) or not isinstance(
            self.original_node_count,
            int,
        ):
            raise TypeError("original_node_count must be an integer.")

        if isinstance(self.original_arc_count, bool) or not isinstance(
            self.original_arc_count,
            int,
        ):
            raise TypeError("original_arc_count must be an integer.")

        if self.original_node_count < len(node_flow_indexes):
            raise ValueError("original_node_count cannot be below the feasible count.")

        if self.original_arc_count < len(feasible_arc_ids):
            raise ValueError("original_arc_count cannot be below the feasible count.")

        object.__setattr__(self, "source", source)
        object.__setattr__(
            self,
            "destination_nodes",
            destination_nodes,
        )
        object.__setattr__(
            self,
            "auxiliary_sink_id",
            auxiliary_sink_id,
        )
        object.__setattr__(
            self,
            "sink_arcs",
            tuple(
                sorted(
                    sink_arcs,
                    key=lambda arc: arc.arc_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "feasible_arc_ids",
            feasible_arc_ids,
        )
        object.__setattr__(
            self,
            "node_flow_indexes",
            tuple(
                sorted(
                    node_flow_indexes,
                    key=lambda item: (
                        item.node[1],
                        item.node[0],
                    ),
                )
            ),
        )

    @property
    def fragment_id(self) -> str:
        """Return the fragment identifier."""
        return str(self.fragment_state.fragment_id)

    @property
    def demand_id(self) -> str:
        """Return the original demand identifier."""
        return str(self.demand.demand_id)

    @property
    def volume(self) -> float:
        """Return fixed unfinished fragment volume."""
        return float(self.fragment_state.volume)

    @property
    def feasible_node_count(self) -> int:
        """Return the retained time-space node count."""
        return len(self.node_flow_indexes)

    @property
    def feasible_arc_count(self) -> int:
        """Return the retained physical arc count."""
        return len(self.feasible_arc_ids)

    @property
    def sink_arc_ids(self) -> tuple[str, ...]:
        """Return fragment-specific delivery arc IDs."""
        return tuple(str(sink_arc.arc_id) for sink_arc in self.sink_arcs)

    @property
    def all_flow_arc_ids(self) -> tuple[str, ...]:
        """Return physical and logical delivery arc IDs."""
        return tuple(
            sorted(
                (
                    *self.feasible_arc_ids,
                    *self.sink_arc_ids,
                )
            )
        )

    def flow_index_for(
        self,
        node: TimeSpaceNode,
    ) -> NodeFlowIndex:
        """Return the physical flow index for one node."""
        validated_node = validate_time_space_node(
            node,
            field_name="node",
        )

        for node_index in self.node_flow_indexes:
            if node_index.node == validated_node:
                return node_index

        raise KeyError(f"Node {validated_node} is not feasible for fragment {self.fragment_id}.")

    def incoming_flow_arc_ids(
        self,
        node: TimeSpaceNode,
    ) -> tuple[str, ...]:
        """Return physical arcs entering one fragment-network node."""
        return tuple(str(arc_id) for arc_id in self.flow_index_for(node).incoming_arc_ids)

    def outgoing_flow_arc_ids(
        self,
        node: TimeSpaceNode,
    ) -> tuple[str, ...]:
        """Return physical and delivery arcs leaving one node."""
        validated_node = validate_time_space_node(
            node,
            field_name="node",
        )
        physical_outgoing = self.flow_index_for(validated_node).outgoing_arc_ids
        delivery_outgoing = tuple(
            sink_arc.arc_id for sink_arc in self.sink_arcs if sink_arc.tail == validated_node
        )

        return tuple(
            sorted(
                (
                    *physical_outgoing,
                    *delivery_outgoing,
                )
            )
        )


@dataclass(frozen=True, slots=True)
class FragmentNetworkSnapshot:
    """Fragment networks available at one Full-Reroute event."""

    current_event_id: str
    physical_time: int
    instance_fingerprint: str
    indexes: tuple[FragmentNetworkIndex, ...]

    def __post_init__(self) -> None:
        """Validate fragment-network snapshot consistency."""
        if not isinstance(self.current_event_id, str):
            raise TypeError("current_event_id must be a string.")

        current_event_id = self.current_event_id.strip()

        if not current_event_id:
            raise ValueError("current_event_id must be non-empty.")

        if isinstance(self.physical_time, bool) or not isinstance(
            self.physical_time,
            int,
        ):
            raise TypeError("physical_time must be an integer.")

        if self.physical_time < 0:
            raise ValueError("physical_time must be non-negative.")

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.indexes, tuple):
            raise TypeError("indexes must be a tuple.")

        indexes = tuple(self.indexes)

        for index in indexes:
            if not isinstance(index, FragmentNetworkIndex):
                raise TypeError("Every index must be a FragmentNetworkIndex.")

            if index.fragment_state.physical_time != self.physical_time:
                raise ValueError("Every fragment index must use the snapshot time.")

        fragment_ids = tuple(index.fragment_id for index in indexes)

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Fragment-network identifiers must be unique.")

        object.__setattr__(
            self,
            "current_event_id",
            current_event_id,
        )
        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "indexes",
            tuple(
                sorted(
                    indexes,
                    key=lambda index: index.fragment_id,
                )
            ),
        )

    @property
    def fragment_ids(self) -> tuple[str, ...]:
        """Return indexed fragment identifiers."""
        return tuple(index.fragment_id for index in self.indexes)

    def index_for(
        self,
        fragment_id: str,
    ) -> FragmentNetworkIndex:
        """Return one fragment-specific network index."""
        if not isinstance(fragment_id, str):
            raise TypeError("fragment_id must be a string.")

        normalised_fragment_id = fragment_id.strip()

        for index in self.indexes:
            if index.fragment_id == normalised_fragment_id:
                return index

        raise KeyError(f"Unknown fragment network: {normalised_fragment_id}")


def _candidate_future_graph(
    instance: ExperimentInstance,
    *,
    source_time: int,
    due_time: int,
    available_transport_arc_ids: set[str],
) -> nx.MultiDiGraph:
    """Retain future holding arcs and available transport services."""
    candidate = nx.MultiDiGraph(name="fragment_rerouting_candidate")

    for raw_node, raw_attributes in instance.graph.nodes(data=True):
        node = cast(TimeSpaceNode, raw_node)

        if source_time <= node[1] <= due_time:
            attributes = cast(dict[str, Any], raw_attributes)
            candidate.add_node(node, **dict(attributes))

    for raw_tail, raw_head, raw_key, raw_attributes in instance.graph.edges(
        keys=True,
        data=True,
    ):
        tail = cast(TimeSpaceNode, raw_tail)
        head = cast(TimeSpaceNode, raw_head)

        if tail not in candidate or head not in candidate:
            continue

        attributes = cast(dict[str, Any], raw_attributes)
        arc_id = str(attributes.get("arc_id", raw_key))
        arc_type = ArcType(str(attributes["arc_type"]))

        if arc_type is ArcType.TRANSPORT and arc_id not in available_transport_arc_ids:
            continue

        candidate.add_edge(
            tail,
            head,
            key=raw_key,
            **dict(attributes),
        )

    return candidate


def _prune_fragment_graph(
    graph: nx.MultiDiGraph,
    *,
    source: TimeSpaceNode,
    destination: str,
    due_time: int,
) -> tuple[nx.MultiDiGraph, tuple[TimeSpaceNode, ...]]:
    """Retain nodes on a source-to-destination path by the deadline."""
    if source not in graph:
        raise ValueError(f"Fragment source node does not exist: {source}.")

    eligible_destinations = tuple(
        sorted(
            (
                cast(TimeSpaceNode, raw_node)
                for raw_node in graph.nodes
                if cast(TimeSpaceNode, raw_node)[0] == destination
                and source[1] <= cast(TimeSpaceNode, raw_node)[1] <= due_time
            ),
            key=lambda node: (node[1], node[0]),
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
        raise ValueError(f"Fragment at {source} cannot reach {destination} by time {due_time}.")

    can_reach_destination: set[TimeSpaceNode] = set()

    for destination_node in reachable_destinations:
        can_reach_destination.add(destination_node)
        can_reach_destination.update(
            cast(
                set[TimeSpaceNode],
                nx.ancestors(graph, destination_node),
            )
        )

    retained_nodes = reachable_from_source.intersection(can_reach_destination)
    pruned = graph.subgraph(retained_nodes).copy()

    return pruned, reachable_destinations


def build_fragment_network_index(
    instance: ExperimentInstance,
    fragment_state: ReroutingFragmentDecisionState,
    rerouting_capacity: ReroutingCapacitySnapshot,
) -> FragmentNetworkIndex:
    """Build one execution-aware fragment network."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        fragment_state,
        ReroutingFragmentDecisionState,
    ):
        raise TypeError("fragment_state must be a ReroutingFragmentDecisionState.")

    if not isinstance(
        rerouting_capacity,
        ReroutingCapacitySnapshot,
    ):
        raise TypeError("rerouting_capacity must be a ReroutingCapacitySnapshot.")

    if rerouting_capacity.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The rerouting-capacity snapshot belongs to another instance.")

    if fragment_state.physical_time != rerouting_capacity.physical_time:
        raise ValueError("Fragment and capacity snapshots must use the same time.")

    demand = instance.demand_by_id(fragment_state.demand_id)
    source = fragment_state.rerouting_source

    candidate = _candidate_future_graph(
        instance,
        source_time=source[1],
        due_time=demand.due_time,
        available_transport_arc_ids=set(rerouting_capacity.available_arc_ids),
    )
    pruned, destination_nodes = _prune_fragment_graph(
        candidate,
        source=source,
        destination=demand.destination,
        due_time=demand.due_time,
    )

    feasible_arcs = extract_time_space_arcs(pruned)
    feasible_arc_ids = tuple(arc.arc_id for arc in feasible_arcs)
    sink_arcs = build_auxiliary_sink_arcs(
        demand_id=fragment_state.fragment_id,
        destination_nodes=destination_nodes,
    )

    return FragmentNetworkIndex(
        fragment_state=fragment_state,
        demand=demand,
        source=source,
        destination_nodes=destination_nodes,
        auxiliary_sink_id=auxiliary_sink_id_for(fragment_state.fragment_id),
        sink_arcs=sink_arcs,
        feasible_arc_ids=feasible_arc_ids,
        node_flow_indexes=_build_node_flow_indexes(pruned),
        original_node_count=instance.node_count,
        original_arc_count=instance.arc_count,
    )


def build_fragment_network_snapshot(
    instance: ExperimentInstance,
    decision_snapshot: ReroutingDecisionSnapshot,
    rerouting_capacity: ReroutingCapacitySnapshot,
) -> FragmentNetworkSnapshot:
    """Build feasible networks for all selected unfinished fragments."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        decision_snapshot,
        ReroutingDecisionSnapshot,
    ):
        raise TypeError("decision_snapshot must be a ReroutingDecisionSnapshot.")

    if not isinstance(
        rerouting_capacity,
        ReroutingCapacitySnapshot,
    ):
        raise TypeError("rerouting_capacity must be a ReroutingCapacitySnapshot.")

    if decision_snapshot.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The decision snapshot belongs to another instance.")

    if rerouting_capacity.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The capacity snapshot belongs to another instance.")

    if decision_snapshot.current_event_id != rerouting_capacity.current_event_id:
        raise ValueError("Decision and capacity snapshots must use the same event.")

    if decision_snapshot.physical_time != rerouting_capacity.physical_time:
        raise ValueError("Decision and capacity snapshots must use the same time.")

    indexes = tuple(
        build_fragment_network_index(
            instance,
            fragment_state,
            rerouting_capacity,
        )
        for fragment_state in decision_snapshot.fragments
    )

    return FragmentNetworkSnapshot(
        current_event_id=decision_snapshot.current_event_id,
        physical_time=decision_snapshot.physical_time,
        instance_fingerprint=instance.demand_fingerprint,
        indexes=indexes,
    )
