"""Conversion of NetworkX edges into solver-ready arc objects."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

import networkx as nx

from barge_rerouting.domain.network import (
    ArcType,
    TimeSpaceArc,
    TimeSpaceNode,
)


def extract_time_space_arcs(
    graph: nx.MultiDiGraph,
) -> tuple[TimeSpaceArc, ...]:
    """Convert every graph edge into a validated immutable arc.

    Args:
        graph:
            Time-space multigraph produced by the network builder.

    Returns:
        A deterministic tuple sorted by unique arc identifier.

    Raises:
        ValueError:
            If required edge attributes are missing or identifiers are
            duplicated.
    """
    arcs: list[TimeSpaceArc] = []
    seen_arc_ids: set[str] = set()

    for raw_tail, raw_head, raw_key, raw_attributes in graph.edges(
        keys=True,
        data=True,
    ):
        tail = cast(TimeSpaceNode, raw_tail)
        head = cast(TimeSpaceNode, raw_head)
        attributes = cast(dict[str, Any], raw_attributes)

        arc_id = str(attributes.get("arc_id", raw_key))

        if arc_id in seen_arc_ids:
            raise ValueError(f"Duplicate arc identifier: {arc_id}")

        seen_arc_ids.add(arc_id)

        try:
            arc_type = ArcType(str(attributes["arc_type"]))
        except KeyError as error:
            raise ValueError(f"Arc {arc_id} is missing required attribute 'arc_type'.") from error
        except ValueError as error:
            raise ValueError(f"Arc {arc_id} has an unsupported arc_type.") from error

        raw_capacity = attributes.get("capacity")
        capacity = None if raw_capacity is None else float(raw_capacity)

        raw_service_id = attributes.get("service_id")
        service_id = None if raw_service_id is None else str(raw_service_id)

        raw_direction = attributes.get("direction")
        direction = None if raw_direction is None else str(raw_direction)

        arcs.append(
            TimeSpaceArc(
                arc_id=arc_id,
                tail=tail,
                head=head,
                arc_type=arc_type,
                nominal_capacity=capacity,
                service_id=service_id,
                direction=direction,
            )
        )

    return tuple(sorted(arcs, key=lambda arc: arc.arc_id))


def index_arcs_by_id(
    arcs: Iterable[TimeSpaceArc],
) -> dict[str, TimeSpaceArc]:
    """Create a unique dictionary keyed by arc identifier."""
    index: dict[str, TimeSpaceArc] = {}

    for arc in arcs:
        if arc.arc_id in index:
            raise ValueError(f"Duplicate arc identifier: {arc.arc_id}")

        index[arc.arc_id] = arc

    return index
