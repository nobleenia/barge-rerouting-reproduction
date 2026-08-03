"""Validated assembled optimisation-instance objects."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from barge_rerouting.config import ExperimentConfig
from barge_rerouting.domain import (
    Demand,
    TimeSpaceArc,
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.instance.delivery import AuxiliarySinkArc


def _normalise_arc_ids(
    value: object,
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate, normalise, and deterministically sort arc identifiers."""
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


@dataclass(frozen=True, slots=True)
class NodeFlowIndex:
    """Incoming and outgoing feasible arcs for one demand at one node."""

    node: TimeSpaceNode
    incoming_arc_ids: tuple[str, ...]
    outgoing_arc_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate and normalise the node-level flow index."""
        node = validate_time_space_node(
            self.node,
            field_name="node",
        )
        incoming_arc_ids = _normalise_arc_ids(
            self.incoming_arc_ids,
            field_name="incoming_arc_ids",
        )
        outgoing_arc_ids = _normalise_arc_ids(
            self.outgoing_arc_ids,
            field_name="outgoing_arc_ids",
        )

        overlapping_arc_ids = set(incoming_arc_ids).intersection(outgoing_arc_ids)

        if overlapping_arc_ids:
            raise ValueError(
                "An arc cannot be both incoming and outgoing at the same time-space node."
            )

        object.__setattr__(self, "node", node)
        object.__setattr__(
            self,
            "incoming_arc_ids",
            incoming_arc_ids,
        )
        object.__setattr__(
            self,
            "outgoing_arc_ids",
            outgoing_arc_ids,
        )

    @property
    def degree(self) -> int:
        """Return the total feasible incident-arc count."""
        return len(self.incoming_arc_ids) + len(self.outgoing_arc_ids)


@dataclass(frozen=True, slots=True)
class DemandNetworkIndex:
    """Demand-specific feasible network and flow-conservation indexes."""

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
        """Validate demand-network consistency."""
        if not isinstance(self.demand, Demand):
            raise TypeError("demand must be a Demand object.")

        source = validate_time_space_node(
            self.source,
            field_name="source",
        )

        expected_source: TimeSpaceNode = (
            self.demand.origin,
            self.demand.availability_time,
        )

        if source != expected_source:
            raise ValueError(
                "Demand-network source must equal the demand origin at its availability time."
            )

        if not isinstance(self.destination_nodes, tuple):
            raise TypeError("destination_nodes must be a tuple.")

        destination_nodes = tuple(
            validate_time_space_node(
                node,
                field_name="destination_node",
            )
            for node in self.destination_nodes
        )

        if not destination_nodes:
            raise ValueError(
                "A feasible demand network requires at least one destination-time node."
            )

        if len(set(destination_nodes)) != len(destination_nodes):
            raise ValueError("destination_nodes must be unique.")

        destination_nodes = tuple(
            sorted(
                destination_nodes,
                key=lambda node: (node[1], node[0]),
            )
        )

        for destination_node in destination_nodes:
            if destination_node[0] != self.demand.destination:
                raise ValueError("Every destination node must use the demand destination.")

            if destination_node[1] < self.demand.availability_time:
                raise ValueError("A destination node cannot precede demand availability.")

            if destination_node[1] > self.demand.due_time:
                raise ValueError("A destination node cannot occur after the demand due time.")

        if not isinstance(self.auxiliary_sink_id, str):
            raise TypeError("auxiliary_sink_id must be a string.")

        auxiliary_sink_id = self.auxiliary_sink_id.strip()

        if not auxiliary_sink_id:
            raise ValueError("auxiliary_sink_id must be non-empty.")

        expected_sink_id = f"sink::{self.demand.demand_id}"

        if auxiliary_sink_id != expected_sink_id:
            raise ValueError("auxiliary_sink_id must match the indexed demand identifier.")

        if not isinstance(self.sink_arcs, tuple):
            raise TypeError("sink_arcs must be a tuple.")

        sink_arcs = tuple(self.sink_arcs)

        if not sink_arcs:
            raise ValueError("A feasible demand network requires auxiliary sink arcs.")

        for sink_arc in sink_arcs:
            if not isinstance(sink_arc, AuxiliarySinkArc):
                raise TypeError("Every sink arc must be an AuxiliarySinkArc object.")

            if sink_arc.demand_id != self.demand.demand_id:
                raise ValueError("Every sink arc must reference the indexed demand.")

            if sink_arc.sink_id != auxiliary_sink_id:
                raise ValueError("Every sink arc must terminate at the indexed sink.")

        sink_arc_ids = [sink_arc.arc_id for sink_arc in sink_arcs]

        if len(set(sink_arc_ids)) != len(sink_arc_ids):
            raise ValueError("Auxiliary sink arc identifiers must be unique.")

        sink_arc_tails = [sink_arc.tail for sink_arc in sink_arcs]

        if len(set(sink_arc_tails)) != len(sink_arc_tails):
            raise ValueError("Each destination node must have exactly one sink arc.")

        if set(sink_arc_tails) != set(destination_nodes):
            raise ValueError(
                "Auxiliary sink arcs must cover every eligible destination-time node exactly once."
            )

        feasible_arc_ids = _normalise_arc_ids(
            self.feasible_arc_ids,
            field_name="feasible_arc_ids",
        )

        if not feasible_arc_ids:
            raise ValueError("A feasible demand network requires at least one arc.")

        if not isinstance(self.node_flow_indexes, tuple):
            raise TypeError("node_flow_indexes must be a tuple.")

        node_flow_indexes = tuple(self.node_flow_indexes)

        if not node_flow_indexes:
            raise ValueError("A feasible demand network requires node flow indexes.")

        for node_index in node_flow_indexes:
            if not isinstance(node_index, NodeFlowIndex):
                raise TypeError("Every node flow index must be a NodeFlowIndex object.")

        indexed_nodes = tuple(node_index.node for node_index in node_flow_indexes)

        if len(set(indexed_nodes)) != len(indexed_nodes):
            raise ValueError("Node flow indexes must use unique nodes.")

        if source not in indexed_nodes:
            raise ValueError("The demand source must appear in the node flow indexes.")

        for destination_node in destination_nodes:
            if destination_node not in indexed_nodes:
                raise ValueError("Every eligible destination must appear in the node flow indexes.")

        incoming_occurrences: list[str] = []
        outgoing_occurrences: list[str] = []

        for node_index in node_flow_indexes:
            incoming_occurrences.extend(node_index.incoming_arc_ids)
            outgoing_occurrences.extend(node_index.outgoing_arc_ids)

        if len(incoming_occurrences) != len(set(incoming_occurrences)):
            raise ValueError("Each feasible arc must enter exactly one indexed node.")

        if len(outgoing_occurrences) != len(set(outgoing_occurrences)):
            raise ValueError("Each feasible arc must leave exactly one indexed node.")

        feasible_arc_id_set = set(feasible_arc_ids)

        if set(incoming_occurrences) != feasible_arc_id_set:
            raise ValueError("Incoming indexes do not match the feasible arc set.")

        if set(outgoing_occurrences) != feasible_arc_id_set:
            raise ValueError("Outgoing indexes do not match the feasible arc set.")

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
            raise ValueError("original_node_count cannot be below the feasible node count.")

        if self.original_arc_count < len(feasible_arc_ids):
            raise ValueError("original_arc_count cannot be below the feasible arc count.")

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
                    key=lambda sink_arc: sink_arc.arc_id,
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
    def demand_id(self) -> str:
        """Return the indexed demand identifier."""
        return str(self.demand.demand_id)

    @property
    def feasible_node_count(self) -> int:
        """Return the number of nodes retained for this demand."""
        return len(self.node_flow_indexes)

    @property
    def feasible_arc_count(self) -> int:
        """Return the number of arcs retained for this demand."""
        return len(self.feasible_arc_ids)

    @property
    def removed_node_count(self) -> int:
        """Return the number of full-network nodes removed."""
        return self.original_node_count - self.feasible_node_count

    @property
    def removed_arc_count(self) -> int:
        """Return the number of full-network arcs removed."""
        return self.original_arc_count - self.feasible_arc_count

    def flow_index_for(
        self,
        node: TimeSpaceNode,
    ) -> NodeFlowIndex:
        """Return the flow index for one feasible node."""
        validated_node = validate_time_space_node(
            node,
            field_name="node",
        )

        for node_index in self.node_flow_indexes:
            if node_index.node == validated_node:
                return node_index

        raise KeyError(f"Node {validated_node} is not feasible for demand {self.demand_id}.")

    @property
    def sink_arc_ids(self) -> tuple[str, ...]:
        """Return all demand-specific auxiliary delivery arc IDs."""
        return tuple(sink_arc.arc_id for sink_arc in self.sink_arcs)

    @property
    def all_flow_arc_ids(self) -> tuple[str, ...]:
        """Return physical, holding, and auxiliary delivery arc IDs."""
        return tuple(
            sorted(
                (
                    *self.feasible_arc_ids,
                    *self.sink_arc_ids,
                )
            )
        )

    def incoming_flow_arc_ids(
        self,
        node: TimeSpaceNode,
    ) -> tuple[str, ...]:
        """Return physical arcs entering one time-space node."""
        return self.flow_index_for(node).incoming_arc_ids

    def outgoing_flow_arc_ids(
        self,
        node: TimeSpaceNode,
    ) -> tuple[str, ...]:
        """Return physical and delivery arcs leaving one time-space node."""
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

    def sink_arc_for_destination(
        self,
        destination_node: TimeSpaceNode,
    ) -> AuxiliarySinkArc:
        """Return the delivery arc for one eligible arrival node."""
        validated_node = validate_time_space_node(
            destination_node,
            field_name="destination_node",
        )

        for sink_arc in self.sink_arcs:
            if sink_arc.tail == validated_node:
                return sink_arc

        raise KeyError(
            f"Node {validated_node} is not an eligible destination for demand {self.demand_id}."
        )


@dataclass(frozen=True, slots=True)
class ExperimentInstance:
    """Canonical assembled data used by optimisation policies."""

    config: ExperimentConfig
    graph: nx.MultiDiGraph
    arcs: tuple[TimeSpaceArc, ...]
    demands: tuple[Demand, ...]
    demand_fingerprint: str
    demand_network_indexes: tuple[DemandNetworkIndex, ...]

    def __post_init__(self) -> None:
        """Validate global experiment-instance consistency."""
        if not isinstance(self.config, ExperimentConfig):
            raise TypeError("config must be an ExperimentConfig.")

        if not isinstance(self.graph, nx.MultiDiGraph):
            raise TypeError("graph must be a NetworkX MultiDiGraph.")

        if not isinstance(self.arcs, tuple):
            raise TypeError("arcs must be a tuple.")

        if not isinstance(self.demands, tuple):
            raise TypeError("demands must be a tuple.")

        if not isinstance(self.demand_network_indexes, tuple):
            raise TypeError("demand_network_indexes must be a tuple.")

        for arc in self.arcs:
            if not isinstance(arc, TimeSpaceArc):
                raise TypeError("Every global arc must be a TimeSpaceArc object.")

        for demand in self.demands:
            if not isinstance(demand, Demand):
                raise TypeError("Every experiment demand must be a Demand object.")

        for network_index in self.demand_network_indexes:
            if not isinstance(network_index, DemandNetworkIndex):
                raise TypeError("Every demand network index must be a DemandNetworkIndex object.")

        arc_ids = [arc.arc_id for arc in self.arcs]

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Global arc identifiers must be unique.")

        demand_ids = [demand.demand_id for demand in self.demands]

        if len(set(demand_ids)) != len(demand_ids):
            raise ValueError("Demand identifiers must be unique.")

        indexed_demand_ids = [
            network_index.demand_id for network_index in self.demand_network_indexes
        ]

        if len(set(indexed_demand_ids)) != len(indexed_demand_ids):
            raise ValueError("Demand-network index identifiers must be unique.")

        if set(indexed_demand_ids) != set(demand_ids):
            raise ValueError("Every demand must have exactly one demand-network index.")

        global_arc_id_set = set(arc_ids)

        for network_index in self.demand_network_indexes:
            unknown_arc_ids = set(network_index.feasible_arc_ids).difference(global_arc_id_set)

            if unknown_arc_ids:
                raise ValueError(
                    f"Demand {network_index.demand_id} references arcs outside the global graph."
                )

        if not isinstance(self.demand_fingerprint, str):
            raise TypeError("demand_fingerprint must be a string.")

        fingerprint = self.demand_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("demand_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("demand_fingerprint must be hexadecimal.")

        object.__setattr__(
            self,
            "demand_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "arcs",
            tuple(
                sorted(
                    self.arcs,
                    key=lambda arc: arc.arc_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "demands",
            tuple(
                sorted(
                    self.demands,
                    key=lambda demand: demand.demand_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "demand_network_indexes",
            tuple(
                sorted(
                    self.demand_network_indexes,
                    key=lambda index: index.demand_id,
                )
            ),
        )

    @property
    def node_count(self) -> int:
        """Return the full time-space-network node count."""
        return int(self.graph.number_of_nodes())

    @property
    def arc_count(self) -> int:
        """Return the full time-space-network arc count."""
        return len(self.arcs)

    @property
    def demand_count(self) -> int:
        """Return the number of realised demands."""
        return len(self.demands)

    @property
    def total_feasible_demand_arcs(self) -> int:
        """Return total demand-arc combinations after pruning."""
        total: int = 0

        for network_index in self.demand_network_indexes:
            total += network_index.feasible_arc_count

        return total

    def arc_by_id(self, arc_id: str) -> TimeSpaceArc:
        """Return one global arc by unique identifier."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for arc in self.arcs:
            if arc.arc_id == normalised_arc_id:
                return arc

        raise KeyError(f"Unknown global arc identifier: {normalised_arc_id}")

    def demand_by_id(self, demand_id: str) -> Demand:
        """Return one demand by unique identifier."""
        if not isinstance(demand_id, str):
            raise TypeError("demand_id must be a string.")

        normalised_demand_id = demand_id.strip()

        for demand in self.demands:
            if demand.demand_id == normalised_demand_id:
                return demand

        raise KeyError(f"Unknown experiment demand identifier: {normalised_demand_id}")

    def network_index_for(
        self,
        demand_id: str,
    ) -> DemandNetworkIndex:
        """Return the feasible network index for one demand."""
        if not isinstance(demand_id, str):
            raise TypeError("demand_id must be a string.")

        normalised_demand_id = demand_id.strip()

        for network_index in self.demand_network_indexes:
            if network_index.demand_id == normalised_demand_id:
                return network_index

        raise KeyError(f"Unknown demand-network index identifier: {normalised_demand_id}")
