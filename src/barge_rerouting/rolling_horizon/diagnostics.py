"""Residual-capacity feasibility and bottleneck diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import networkx as nx

from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.state import RollingBookingState
from barge_rerouting.rolling_horizon.timeline import BookingDecisionEvent

DIAGNOSTIC_TOLERANCE = 1e-6


def _validate_required_volume(value: object) -> float:
    """Validate a strictly positive finite diagnostic volume."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("required_volume must be a real number.")

    required_volume = float(value)

    if not isfinite(required_volume):
        raise ValueError("required_volume must be finite.")

    if required_volume <= 0:
        raise ValueError("required_volume must be strictly positive.")

    return required_volume


@dataclass(frozen=True, slots=True)
class BottleneckArcDiagnostic:
    """Residual-capacity information for one minimum-cut transport arc."""

    arc_id: str
    service_id: str | None
    residual_capacity: float
    nominal_capacity: float

    def __post_init__(self) -> None:
        """Validate and normalise bottleneck information."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        arc_id = self.arc_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        service_id = None if self.service_id is None else str(self.service_id).strip()

        residual_capacity = float(self.residual_capacity)
        nominal_capacity = float(self.nominal_capacity)

        if not isfinite(residual_capacity):
            raise ValueError("residual_capacity must be finite.")

        if not isfinite(nominal_capacity):
            raise ValueError("nominal_capacity must be finite.")

        if residual_capacity < -DIAGNOSTIC_TOLERANCE:
            raise ValueError("residual_capacity must be nonnegative.")

        if nominal_capacity <= 0:
            raise ValueError("nominal_capacity must be positive.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(
            self,
            "residual_capacity",
            max(0.0, residual_capacity),
        )
        object.__setattr__(
            self,
            "nominal_capacity",
            nominal_capacity,
        )


@dataclass(frozen=True, slots=True)
class BookingFeasibilityDiagnostic:
    """Maximum-routable-volume and minimum-cut result for one request."""

    demand_id: str
    required_volume: float
    maximum_routable_volume: float
    volume_shortfall: float
    minimum_cut_capacity: float
    bottleneck_arcs: tuple[BottleneckArcDiagnostic, ...]

    @property
    def is_feasible(self) -> bool:
        """Return whether the complete required volume can be routed."""
        return self.volume_shortfall <= DIAGNOSTIC_TOLERANCE

    @property
    def bottleneck_arc_ids(self) -> tuple[str, ...]:
        """Return minimum-cut transport arc identifiers."""
        return tuple(bottleneck.arc_id for bottleneck in self.bottleneck_arcs)


def _diagnostic_arc_node(
    demand_id: str,
    arc_id: str,
) -> tuple[str, str, str]:
    """Return an artificial node that preserves one parallel arc."""
    return ("diagnostic-arc", demand_id, arc_id)


def diagnose_booking_feasibility(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    *,
    required_volume: float | None = None,
) -> BookingFeasibilityDiagnostic:
    """Diagnose how much current demand can traverse residual capacity."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another experiment instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The diagnostic event must be the next unprocessed event.")

    demand = instance.demand_by_id(event.demand_id)

    if demand != event.demand:
        raise ValueError("The booking event demand does not match the instance.")

    selected_required_volume = _validate_required_volume(
        demand.volume if required_volume is None else required_volume
    )

    network_index = instance.network_index_for(event.demand_id)

    graph = nx.DiGraph()
    super_source = (
        "diagnostic-source",
        event.demand_id,
        event.sequence_number,
    )
    logical_sink = network_index.auxiliary_sink_id

    graph.add_edge(
        super_source,
        network_index.source,
        capacity=selected_required_volume,
    )

    high_capacity = selected_required_volume + 1.0
    transport_arc_nodes: dict[str, tuple[str, str, str]] = {}

    for arc_id in network_index.feasible_arc_ids:
        arc = instance.arc_by_id(arc_id)
        arc_node = _diagnostic_arc_node(
            event.demand_id,
            arc_id,
        )

        if arc.is_transport:
            arc_capacity = float(
                state.residual_transport_capacity(
                    instance,
                    arc_id,
                )
            )
            transport_arc_nodes[arc_id] = arc_node
        else:
            arc_capacity = high_capacity

        graph.add_edge(
            arc.tail,
            arc_node,
            capacity=arc_capacity,
        )
        graph.add_edge(
            arc_node,
            arc.head,
            capacity=high_capacity,
        )

    for sink_arc in network_index.sink_arcs:
        arc_node = _diagnostic_arc_node(
            event.demand_id,
            sink_arc.arc_id,
        )

        graph.add_edge(
            sink_arc.tail,
            arc_node,
            capacity=high_capacity,
        )
        graph.add_edge(
            arc_node,
            sink_arc.sink_id,
            capacity=high_capacity,
        )

    maximum_routable_volume = float(
        nx.maximum_flow_value(
            graph,
            super_source,
            logical_sink,
            capacity="capacity",
        )
    )

    minimum_cut_capacity, partition = nx.minimum_cut(
        graph,
        super_source,
        logical_sink,
        capacity="capacity",
    )
    reachable_nodes, nonreachable_nodes = partition

    volume_shortfall = max(
        0.0,
        selected_required_volume - maximum_routable_volume,
    )

    bottleneck_arcs: list[BottleneckArcDiagnostic] = []

    if volume_shortfall > DIAGNOSTIC_TOLERANCE:
        for arc_id, arc_node in transport_arc_nodes.items():
            arc = instance.arc_by_id(arc_id)

            if arc.tail not in reachable_nodes or arc_node not in nonreachable_nodes:
                continue

            if arc.nominal_capacity is None:
                raise ValueError(f"Transport arc {arc_id} has no nominal capacity.")

            service_id = None if arc.service_id is None else str(arc.service_id)

            bottleneck_arcs.append(
                BottleneckArcDiagnostic(
                    arc_id=arc_id,
                    service_id=service_id,
                    residual_capacity=(
                        state.residual_transport_capacity(
                            instance,
                            arc_id,
                        )
                    ),
                    nominal_capacity=float(arc.nominal_capacity),
                )
            )

    return BookingFeasibilityDiagnostic(
        demand_id=event.demand_id,
        required_volume=selected_required_volume,
        maximum_routable_volume=maximum_routable_volume,
        volume_shortfall=volume_shortfall,
        minimum_cut_capacity=float(minimum_cut_capacity),
        bottleneck_arcs=tuple(
            sorted(
                bottleneck_arcs,
                key=lambda item: item.arc_id,
            )
        ),
    )
