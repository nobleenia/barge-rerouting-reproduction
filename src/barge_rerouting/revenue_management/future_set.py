"""Construction of future-demand sets for revenue management."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

import networkx as nx

from barge_rerouting.domain import (
    Demand,
    FutureDemandForecast,
    TimeSpaceNode,
)
from barge_rerouting.instance import (
    DemandNetworkIndex,
    ExperimentInstance,
    NodeFlowIndex,
    auxiliary_sink_id_for,
    build_auxiliary_sink_arcs,
)
from barge_rerouting.network.arcs import (
    extract_time_space_arcs,
)
from barge_rerouting.network.feasibility import (
    extract_demand_feasible_network,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
)


class FutureDemandSelectionMode(StrEnum):
    """Rule used to construct the future-demand set."""

    EXPLICIT = "explicit"
    A004_SHARED_ARC = "a004-shared-arc"


class FutureDemandExclusionReason(StrEnum):
    """Reason a forecast was excluded from the inferred future set."""

    NOT_LATER_THAN_CURRENT_EVENT = "not-later-than-current-event"
    OUTSIDE_LOOKAHEAD = "outside-lookahead"
    ZERO_MAXIMUM_VOLUME = "zero-maximum-volume"
    NETWORK_INFEASIBLE = "network-infeasible"
    NO_SHARED_TRANSPORT_ARC = "no-shared-transport-arc"


@dataclass(frozen=True, slots=True)
class FutureDemandCandidate:
    """One forecast and its feasible tentative-flow network."""

    forecast: FutureDemandForecast
    network_index: DemandNetworkIndex
    shared_transport_arc_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate forecast and projected-network consistency."""
        if not isinstance(
            self.forecast,
            FutureDemandForecast,
        ):
            raise TypeError("forecast must be a FutureDemandForecast.")

        if not isinstance(
            self.network_index,
            DemandNetworkIndex,
        ):
            raise TypeError("network_index must be a DemandNetworkIndex.")

        if self.network_index.demand_id != self.forecast.forecast_id:
            raise ValueError("Projected network identifier must match the forecast identifier.")

        if not isinstance(
            self.shared_transport_arc_ids,
            tuple,
        ):
            raise TypeError("shared_transport_arc_ids must be a tuple.")

        shared_arc_ids: list[str] = []

        for arc_id in self.shared_transport_arc_ids:
            if not isinstance(arc_id, str):
                raise TypeError("Every shared transport arc identifier must be a string.")

            normalised_arc_id = arc_id.strip()

            if not normalised_arc_id:
                raise ValueError("Shared transport arc identifiers must be non-empty.")

            shared_arc_ids.append(normalised_arc_id)

        if len(set(shared_arc_ids)) != len(shared_arc_ids):
            raise ValueError("Shared transport arc identifiers must be unique.")

        object.__setattr__(
            self,
            "shared_transport_arc_ids",
            tuple(sorted(shared_arc_ids)),
        )

    @property
    def forecast_id(self) -> str:
        """Return the future-demand forecast identifier."""
        return str(self.forecast.forecast_id)

    @property
    def transport_arc_ids(self) -> tuple[str, ...]:
        """Return feasible transport arcs for tentative flow."""
        return tuple(
            arc_id
            for arc_id in self.network_index.feasible_arc_ids
            if arc_id.startswith("transport::")
        )


@dataclass(frozen=True, slots=True)
class FutureDemandExclusion:
    """One forecast excluded from the inferred future set."""

    forecast_id: str
    reason: FutureDemandExclusionReason

    def __post_init__(self) -> None:
        """Validate the exclusion record."""
        if not isinstance(self.forecast_id, str):
            raise TypeError("forecast_id must be a string.")

        forecast_id = self.forecast_id.strip()

        if not forecast_id:
            raise ValueError("forecast_id must be non-empty.")

        if not isinstance(
            self.reason,
            FutureDemandExclusionReason,
        ):
            raise TypeError("reason must be a FutureDemandExclusionReason.")

        object.__setattr__(
            self,
            "forecast_id",
            forecast_id,
        )


@dataclass(frozen=True, slots=True)
class FutureDemandSet:
    """Selected future forecasts for one current booking event."""

    current_event: BookingDecisionEvent
    selection_mode: FutureDemandSelectionMode
    candidates: tuple[FutureDemandCandidate, ...]
    exclusions: tuple[FutureDemandExclusion, ...]

    def __post_init__(self) -> None:
        """Validate ordering and forecast uniqueness."""
        if not isinstance(
            self.current_event,
            BookingDecisionEvent,
        ):
            raise TypeError("current_event must be a BookingDecisionEvent.")

        if not isinstance(
            self.selection_mode,
            FutureDemandSelectionMode,
        ):
            raise TypeError("selection_mode must be a FutureDemandSelectionMode.")

        if not isinstance(self.candidates, tuple):
            raise TypeError("candidates must be a tuple.")

        if not isinstance(self.exclusions, tuple):
            raise TypeError("exclusions must be a tuple.")

        for candidate in self.candidates:
            if not isinstance(
                candidate,
                FutureDemandCandidate,
            ):
                raise TypeError("Every candidate must be a FutureDemandCandidate.")

        for exclusion in self.exclusions:
            if not isinstance(
                exclusion,
                FutureDemandExclusion,
            ):
                raise TypeError("Every exclusion must be a FutureDemandExclusion.")

        candidates = tuple(
            sorted(
                self.candidates,
                key=lambda item: item.forecast_id,
            )
        )
        exclusions = tuple(
            sorted(
                self.exclusions,
                key=lambda item: item.forecast_id,
            )
        )

        selected_ids = tuple(item.forecast_id for item in candidates)
        excluded_ids = tuple(item.forecast_id for item in exclusions)

        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("Selected forecast identifiers must be unique.")

        if len(set(excluded_ids)) != len(excluded_ids):
            raise ValueError("Excluded forecast identifiers must be unique.")

        if set(selected_ids).intersection(excluded_ids):
            raise ValueError("A forecast cannot be both selected and excluded.")

        object.__setattr__(
            self,
            "candidates",
            candidates,
        )
        object.__setattr__(
            self,
            "exclusions",
            exclusions,
        )

    @property
    def forecast_ids(self) -> tuple[str, ...]:
        """Return the selected set K(current)."""
        return tuple(candidate.forecast_id for candidate in self.candidates)

    @property
    def excluded_forecast_ids(self) -> tuple[str, ...]:
        """Return excluded forecast identifiers."""
        return tuple(exclusion.forecast_id for exclusion in self.exclusions)

    def candidate_for(
        self,
        forecast_id: str,
    ) -> FutureDemandCandidate:
        """Return one selected future-demand candidate."""
        if not isinstance(forecast_id, str):
            raise TypeError("forecast_id must be a string.")

        normalised_id = forecast_id.strip()

        for candidate in self.candidates:
            if candidate.forecast_id == normalised_id:
                return candidate

        raise KeyError(f"Forecast {normalised_id} is not in the selected future set.")

    def exclusion_for(
        self,
        forecast_id: str,
    ) -> FutureDemandExclusion:
        """Return one forecast exclusion record."""
        if not isinstance(forecast_id, str):
            raise TypeError("forecast_id must be a string.")

        normalised_id = forecast_id.strip()

        for exclusion in self.exclusions:
            if exclusion.forecast_id == normalised_id:
                return exclusion

        raise KeyError(f"Forecast {normalised_id} was not excluded.")


def _normalise_forecasts(
    forecasts: Sequence[FutureDemandForecast],
    *,
    current_event: BookingDecisionEvent,
) -> tuple[FutureDemandForecast, ...]:
    """Validate and deterministically order forecast inputs."""
    if isinstance(forecasts, (str, bytes)):
        raise TypeError("forecasts must be a sequence of forecasts.")

    selected = tuple(forecasts)

    for forecast in selected:
        if not isinstance(
            forecast,
            FutureDemandForecast,
        ):
            raise TypeError("Every forecast must be a FutureDemandForecast.")

        if forecast.forecast_id == current_event.demand_id:
            raise ValueError(
                "A future forecast identifier cannot equal the current demand identifier."
            )

    forecast_ids = tuple(forecast.forecast_id for forecast in selected)

    if len(set(forecast_ids)) != len(forecast_ids):
        raise ValueError("Future forecast identifiers must be unique.")

    return tuple(
        sorted(
            selected,
            key=lambda forecast: forecast.forecast_id,
        )
    )


def _build_node_flow_indexes(
    graph: nx.MultiDiGraph,
) -> tuple[NodeFlowIndex, ...]:
    """Build node-level incoming and outgoing arc indexes."""
    arcs = extract_time_space_arcs(graph)

    nodes = tuple(
        sorted(
            (cast(TimeSpaceNode, raw_node) for raw_node in graph.nodes),
            key=lambda node: (node[1], node[0]),
        )
    )

    incoming_by_node: dict[
        TimeSpaceNode,
        list[str],
    ] = {node: [] for node in nodes}
    outgoing_by_node: dict[
        TimeSpaceNode,
        list[str],
    ] = {node: [] for node in nodes}

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


def _project_forecast_network(
    instance: ExperimentInstance,
    current_event: BookingDecisionEvent,
    forecast: FutureDemandForecast,
) -> DemandNetworkIndex | None:
    """Project a forecast onto the existing time-space network."""
    if forecast.maximum_volume <= 0:
        raise ValueError(f"Forecast {forecast.forecast_id} has no positive protection level.")

    if forecast.availability_time < current_event.decision_time:
        raise ValueError(
            f"Forecast {forecast.forecast_id} becomes available before the current decision time."
        )

    projected_demand = Demand(
        demand_id=forecast.forecast_id,
        volume=float(forecast.maximum_volume),
        origin=forecast.origin,
        destination=forecast.destination,
        reservation_time=current_event.decision_time,
        availability_time=forecast.availability_time,
        due_time=forecast.due_time,
        category=forecast.category,
        fare_per_teu=forecast.fare_per_teu,
    )

    feasible_result = extract_demand_feasible_network(
        instance.graph,
        origin=forecast.origin,
        destination=forecast.destination,
        availability_time=forecast.availability_time,
        due_time=forecast.due_time,
    )

    if not feasible_result.is_feasible:
        return None

    feasible_arcs = extract_time_space_arcs(feasible_result.graph)
    feasible_arc_ids = tuple(arc.arc_id for arc in feasible_arcs)

    sink_arcs = build_auxiliary_sink_arcs(
        demand_id=forecast.forecast_id,
        destination_nodes=(feasible_result.destination_nodes),
    )

    return DemandNetworkIndex(
        demand=projected_demand,
        source=feasible_result.source,
        destination_nodes=(feasible_result.destination_nodes),
        auxiliary_sink_id=auxiliary_sink_id_for(forecast.forecast_id),
        sink_arcs=sink_arcs,
        feasible_arc_ids=feasible_arc_ids,
        node_flow_indexes=_build_node_flow_indexes(feasible_result.graph),
        original_node_count=(feasible_result.original_node_count),
        original_arc_count=(feasible_result.original_arc_count),
    )


def _transport_arc_ids(
    instance: ExperimentInstance,
    network_index: DemandNetworkIndex,
) -> tuple[str, ...]:
    """Return feasible capacity-constrained transport arcs."""
    return tuple(
        sorted(
            arc_id
            for arc_id in network_index.feasible_arc_ids
            if instance.arc_by_id(arc_id).is_transport
        )
    )


def _candidate_from_network(
    instance: ExperimentInstance,
    forecast: FutureDemandForecast,
    network_index: DemandNetworkIndex,
    *,
    current_transport_arc_ids: set[str],
) -> FutureDemandCandidate:
    """Build one selected candidate and interaction index."""
    future_transport_arc_ids = set(
        _transport_arc_ids(
            instance,
            network_index,
        )
    )

    return FutureDemandCandidate(
        forecast=forecast,
        network_index=network_index,
        shared_transport_arc_ids=tuple(
            sorted(current_transport_arc_ids.intersection(future_transport_arc_ids))
        ),
    )


def select_explicit_future_set(
    instance: ExperimentInstance,
    current_event: BookingDecisionEvent,
    forecasts: Sequence[FutureDemandForecast],
) -> FutureDemandSet:
    """Use an explicitly supplied future-demand set.

    No shared-arc inference is applied. Every supplied forecast must
    have positive maximum volume and a feasible time-space path.
    """
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        current_event,
        BookingDecisionEvent,
    ):
        raise TypeError("current_event must be a BookingDecisionEvent.")

    current_index = instance.network_index_for(current_event.demand_id)

    if current_index.demand != current_event.demand:
        raise ValueError("The current event does not belong to the assembled instance.")

    current_transport_arc_ids = set(
        _transport_arc_ids(
            instance,
            current_index,
        )
    )

    normalised_forecasts = _normalise_forecasts(
        forecasts,
        current_event=current_event,
    )

    candidates: list[FutureDemandCandidate] = []

    for forecast in normalised_forecasts:
        network_index = _project_forecast_network(
            instance,
            current_event,
            forecast,
        )

        if network_index is None:
            raise ValueError(
                f"Explicit forecast {forecast.forecast_id} has no feasible time-space path."
            )

        candidates.append(
            _candidate_from_network(
                instance,
                forecast,
                network_index,
                current_transport_arc_ids=(current_transport_arc_ids),
            )
        )

    return FutureDemandSet(
        current_event=current_event,
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
        candidates=tuple(candidates),
        exclusions=(),
    )


def select_a004_interacting_future_set(
    instance: ExperimentInstance,
    current_event: BookingDecisionEvent,
    forecasts: Sequence[FutureDemandForecast],
    *,
    lookahead_end_time: int | None = None,
) -> FutureDemandSet:
    """Infer K(current) using the disclosed A004 rule.

    Because forecasts currently have no booking-time field, future
    availability is used as the operational proxy for being later
    than the current booking event.

    A forecast is selected when it:

    1. becomes available strictly after the current decision time;
    2. lies within the optional look-ahead horizon;
    3. has a feasible time-space path; and
    4. shares at least one transport arc with the current demand.
    """
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        current_event,
        BookingDecisionEvent,
    ):
        raise TypeError("current_event must be a BookingDecisionEvent.")

    if lookahead_end_time is not None:
        if isinstance(lookahead_end_time, bool) or not isinstance(lookahead_end_time, int):
            raise TypeError("lookahead_end_time must be an integer or None.")

        if lookahead_end_time < current_event.decision_time:
            raise ValueError("lookahead_end_time cannot precede the current decision time.")

    current_index = instance.network_index_for(current_event.demand_id)

    if current_index.demand != current_event.demand:
        raise ValueError("The current event does not belong to the assembled instance.")

    current_transport_arc_ids = set(
        _transport_arc_ids(
            instance,
            current_index,
        )
    )

    normalised_forecasts = _normalise_forecasts(
        forecasts,
        current_event=current_event,
    )

    candidates: list[FutureDemandCandidate] = []
    exclusions: list[FutureDemandExclusion] = []

    for forecast in normalised_forecasts:
        if forecast.maximum_volume <= 0:
            exclusions.append(
                FutureDemandExclusion(
                    forecast_id=forecast.forecast_id,
                    reason=(FutureDemandExclusionReason.ZERO_MAXIMUM_VOLUME),
                )
            )
            continue

        if forecast.availability_time <= current_event.decision_time:
            exclusions.append(
                FutureDemandExclusion(
                    forecast_id=forecast.forecast_id,
                    reason=(FutureDemandExclusionReason.NOT_LATER_THAN_CURRENT_EVENT),
                )
            )
            continue

        if lookahead_end_time is not None and forecast.availability_time > lookahead_end_time:
            exclusions.append(
                FutureDemandExclusion(
                    forecast_id=forecast.forecast_id,
                    reason=(FutureDemandExclusionReason.OUTSIDE_LOOKAHEAD),
                )
            )
            continue

        network_index = _project_forecast_network(
            instance,
            current_event,
            forecast,
        )

        if network_index is None:
            exclusions.append(
                FutureDemandExclusion(
                    forecast_id=forecast.forecast_id,
                    reason=(FutureDemandExclusionReason.NETWORK_INFEASIBLE),
                )
            )
            continue

        candidate = _candidate_from_network(
            instance,
            forecast,
            network_index,
            current_transport_arc_ids=(current_transport_arc_ids),
        )

        if not candidate.shared_transport_arc_ids:
            exclusions.append(
                FutureDemandExclusion(
                    forecast_id=forecast.forecast_id,
                    reason=(FutureDemandExclusionReason.NO_SHARED_TRANSPORT_ARC),
                )
            )
            continue

        candidates.append(candidate)

    return FutureDemandSet(
        current_event=current_event,
        selection_mode=(FutureDemandSelectionMode.A004_SHARED_ARC),
        candidates=tuple(candidates),
        exclusions=tuple(exclusions),
    )
