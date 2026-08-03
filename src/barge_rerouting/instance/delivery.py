"""Demand-specific auxiliary destination sinks and delivery arcs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from barge_rerouting.domain import (
    TimeSpaceNode,
    validate_time_space_node,
)


def auxiliary_sink_id_for(demand_id: str) -> str:
    """Return the deterministic auxiliary-sink identifier for one demand."""
    if not isinstance(demand_id, str):
        raise TypeError("demand_id must be a string.")

    normalised_demand_id = demand_id.strip()

    if not normalised_demand_id:
        raise ValueError("demand_id must be non-empty.")

    return f"sink::{normalised_demand_id}"


@dataclass(frozen=True, slots=True)
class AuxiliarySinkArc:
    """Artificial zero-cost delivery arc from an eligible arrival node.

    The head is a demand-specific logical sink rather than a physical
    terminal-time node.
    """

    arc_id: str
    demand_id: str
    tail: TimeSpaceNode
    sink_id: str

    def __post_init__(self) -> None:
        """Validate and normalise the auxiliary delivery arc."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")

        if not isinstance(self.sink_id, str):
            raise TypeError("sink_id must be a string.")

        arc_id = self.arc_id.strip()
        demand_id = self.demand_id.strip()
        sink_id = self.sink_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        if not demand_id:
            raise ValueError("demand_id must be non-empty.")

        if not sink_id:
            raise ValueError("sink_id must be non-empty.")

        expected_sink_id = auxiliary_sink_id_for(demand_id)

        if sink_id != expected_sink_id:
            raise ValueError("sink_id must match the deterministic demand-specific sink.")

        tail = validate_time_space_node(
            self.tail,
            field_name="tail",
        )

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "demand_id", demand_id)
        object.__setattr__(self, "tail", tail)
        object.__setattr__(self, "sink_id", sink_id)

    @property
    def head(self) -> str:
        """Return the logical auxiliary-sink identifier."""
        return str(self.sink_id)


def build_auxiliary_sink_arcs(
    *,
    demand_id: str,
    destination_nodes: Sequence[TimeSpaceNode],
) -> tuple[AuxiliarySinkArc, ...]:
    """Create one artificial delivery arc per eligible destination-time node."""
    sink_id = auxiliary_sink_id_for(demand_id)

    validated_destination_nodes = tuple(
        sorted(
            (
                validate_time_space_node(
                    node,
                    field_name="destination_node",
                )
                for node in destination_nodes
            ),
            key=lambda node: (node[1], node[0]),
        )
    )

    if not validated_destination_nodes:
        raise ValueError("At least one destination node is required to build sink arcs.")

    if len(set(validated_destination_nodes)) != len(validated_destination_nodes):
        raise ValueError("Destination nodes must be unique.")

    return tuple(
        AuxiliarySinkArc(
            arc_id=(f"delivery::{demand_id}::{destination_node[0]}@{destination_node[1]}->sink"),
            demand_id=demand_id,
            tail=destination_node,
            sink_id=sink_id,
        )
        for destination_node in validated_destination_nodes
    )
