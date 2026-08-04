"""Physical-time execution of accepted rolling-horizon commitments."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import (
    AcceptedDemandState,
    DemandFragment,
    TimeSpaceNode,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
)
from barge_rerouting.rolling_horizon.state import RollingBookingState

EXECUTION_TOLERANCE = 1e-6

type FlowNode = TimeSpaceNode | str


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_positive_finite_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a strictly positive finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class PlannedDemandPath:
    """One deterministic source-to-sink component of a committed flow."""

    path_id: str
    demand_id: str
    volume: float
    physical_arc_ids: tuple[str, ...]
    delivery_arc_id: str

    def __post_init__(self) -> None:
        """Validate and normalise the decomposed path."""
        if not isinstance(self.path_id, str):
            raise TypeError("path_id must be a string.")

        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")

        if not isinstance(self.delivery_arc_id, str):
            raise TypeError("delivery_arc_id must be a string.")

        path_id = self.path_id.strip()
        demand_id = self.demand_id.strip()
        delivery_arc_id = self.delivery_arc_id.strip()

        if not path_id:
            raise ValueError("path_id must be non-empty.")

        if not demand_id:
            raise ValueError("demand_id must be non-empty.")

        if not delivery_arc_id:
            raise ValueError("delivery_arc_id must be non-empty.")

        volume = _validate_positive_finite_float(
            "volume",
            self.volume,
        )

        if not isinstance(self.physical_arc_ids, tuple):
            raise TypeError("physical_arc_ids must be a tuple.")

        physical_arc_ids: list[str] = []

        for arc_id in self.physical_arc_ids:
            if not isinstance(arc_id, str):
                raise TypeError("Every physical arc identifier must be a string.")

            normalised_arc_id = arc_id.strip()

            if not normalised_arc_id:
                raise ValueError("Every physical arc identifier must be non-empty.")

            physical_arc_ids.append(normalised_arc_id)

        if len(set(physical_arc_ids)) != len(physical_arc_ids):
            raise ValueError("A decomposed path cannot repeat a physical arc.")

        if delivery_arc_id in physical_arc_ids:
            raise ValueError("The auxiliary delivery arc cannot be a physical arc.")

        object.__setattr__(self, "path_id", path_id)
        object.__setattr__(self, "demand_id", demand_id)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(
            self,
            "physical_arc_ids",
            tuple(physical_arc_ids),
        )
        object.__setattr__(
            self,
            "delivery_arc_id",
            delivery_arc_id,
        )

    @property
    def all_arc_ids(self) -> tuple[str, ...]:
        """Return physical arcs followed by the logical delivery arc."""
        return (
            *self.physical_arc_ids,
            self.delivery_arc_id,
        )


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    """Execution state reconstructed at one physical time."""

    physical_time: int
    instance_fingerprint: str
    demand_states: tuple[AcceptedDemandState, ...]
    planned_paths: tuple[PlannedDemandPath, ...]

    def __post_init__(self) -> None:
        """Validate snapshot consistency."""
        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.demand_states, tuple):
            raise TypeError("demand_states must be a tuple.")

        if not isinstance(self.planned_paths, tuple):
            raise TypeError("planned_paths must be a tuple.")

        for demand_state in self.demand_states:
            if not isinstance(demand_state, AcceptedDemandState):
                raise TypeError("Every demand state must be an AcceptedDemandState.")

        for planned_path in self.planned_paths:
            if not isinstance(planned_path, PlannedDemandPath):
                raise TypeError("Every path must be a PlannedDemandPath.")

        state_demand_ids = [
            str(demand_state.demand.demand_id) for demand_state in self.demand_states
        ]

        if len(set(state_demand_ids)) != len(state_demand_ids):
            raise ValueError("Each demand may have only one execution state.")

        path_ids = [planned_path.path_id for planned_path in self.planned_paths]

        if len(set(path_ids)) != len(path_ids):
            raise ValueError("Planned path identifiers must be unique.")

        unknown_path_demands = {
            planned_path.demand_id for planned_path in self.planned_paths
        }.difference(state_demand_ids)

        if unknown_path_demands:
            raise ValueError("Every planned path must belong to a snapshot demand state.")

        object.__setattr__(self, "physical_time", physical_time)
        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "demand_states",
            tuple(
                sorted(
                    self.demand_states,
                    key=lambda state: state.demand.demand_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "planned_paths",
            tuple(
                sorted(
                    self.planned_paths,
                    key=lambda path: path.path_id,
                )
            ),
        )

    @property
    def active_fragment_count(self) -> int:
        """Return the number of unfinished cargo fragments."""
        return sum(len(demand_state.fragments) for demand_state in self.demand_states)

    @property
    def delivered_barge_volume(self) -> float:
        """Return total volume delivered by barge by this time."""
        return float(
            sum(demand_state.delivered_barge_volume for demand_state in self.demand_states)
        )

    @property
    def remaining_volume(self) -> float:
        """Return total accepted but undelivered volume."""
        return float(sum(demand_state.remaining_volume for demand_state in self.demand_states))

    def demand_state_for(
        self,
        demand_id: str,
    ) -> AcceptedDemandState:
        """Return the execution state for one accepted demand."""
        if not isinstance(demand_id, str):
            raise TypeError("demand_id must be a string.")

        normalised_demand_id = demand_id.strip()

        for demand_state in self.demand_states:
            if demand_state.demand.demand_id == normalised_demand_id:
                return demand_state

        raise KeyError(f"Demand {normalised_demand_id} is not in this snapshot.")

    def executed_transport_volume(
        self,
        instance: ExperimentInstance,
        arc_id: str,
    ) -> float:
        """Return committed volume that has executed one transport arc."""
        _validate_snapshot_instance(self, instance)
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Executed transport volume requires a transport arc.")

        if arc.head[1] > self.physical_time:
            return 0.0

        return float(
            sum(path.volume for path in self.planned_paths if arc_id in path.physical_arc_ids)
        )

    def unexecuted_transport_volume(
        self,
        instance: ExperimentInstance,
        arc_id: str,
    ) -> float:
        """Return committed volume still planned on a transport arc."""
        _validate_snapshot_instance(self, instance)
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Unexecuted transport volume requires a transport arc.")

        if arc.head[1] <= self.physical_time:
            return 0.0

        return float(
            sum(path.volume for path in self.planned_paths if arc_id in path.physical_arc_ids)
        )


def _validate_snapshot_instance(
    snapshot: ExecutionSnapshot,
    instance: ExperimentInstance,
) -> None:
    """Validate that a snapshot belongs to the supplied instance."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if snapshot.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The execution snapshot belongs to another instance.")


def decompose_commitment_paths(
    instance: ExperimentInstance,
    commitment: DemandCommitment,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> tuple[PlannedDemandPath, ...]:
    """Decompose one feasible committed flow into deterministic paths."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(commitment, DemandCommitment):
        raise TypeError("commitment must be a DemandCommitment.")

    if isinstance(tolerance, bool) or not isinstance(
        tolerance,
        (int, float),
    ):
        raise TypeError("tolerance must be a real number.")

    numeric_tolerance = float(tolerance)

    if not isfinite(numeric_tolerance) or numeric_tolerance <= 0:
        raise ValueError("tolerance must be finite and strictly positive.")

    instance_demand = instance.demand_by_id(commitment.demand_id)

    if instance_demand != commitment.demand:
        raise ValueError("Commitment demand does not match the instance.")

    network_index = instance.network_index_for(commitment.demand_id)

    flow_by_arc = {
        planned_flow.arc_id: float(planned_flow.volume)
        for planned_flow in commitment.planned_arc_flows
        if planned_flow.volume > numeric_tolerance
    }

    permitted_arc_ids = set(network_index.all_flow_arc_ids)

    if set(flow_by_arc).difference(permitted_arc_ids):
        raise ValueError("Commitment contains an arc outside its feasible network.")

    tail_by_arc: dict[str, FlowNode] = {}
    head_by_arc: dict[str, FlowNode] = {}
    outgoing_by_node: dict[FlowNode, list[str]] = {}

    for arc_id in network_index.feasible_arc_ids:
        if arc_id not in flow_by_arc:
            continue

        arc = instance.arc_by_id(arc_id)
        tail_by_arc[arc_id] = arc.tail
        head_by_arc[arc_id] = arc.head
        outgoing_by_node.setdefault(arc.tail, []).append(arc_id)

    sink_arc_ids = {sink_arc.arc_id for sink_arc in network_index.sink_arcs}

    for sink_arc in network_index.sink_arcs:
        if sink_arc.arc_id not in flow_by_arc:
            continue

        tail_by_arc[sink_arc.arc_id] = sink_arc.tail
        head_by_arc[sink_arc.arc_id] = sink_arc.sink_id
        outgoing_by_node.setdefault(
            sink_arc.tail,
            [],
        ).append(sink_arc.arc_id)

    for outgoing_arc_ids in outgoing_by_node.values():
        outgoing_arc_ids.sort()

    residual_flow = dict(flow_by_arc)
    paths: list[PlannedDemandPath] = []
    source = network_index.source
    sink = network_index.auxiliary_sink_id

    while (
        sum(residual_flow.get(arc_id, 0.0) for arc_id in outgoing_by_node.get(source, ()))
        > numeric_tolerance
    ):
        current_node: FlowNode = source
        selected_arc_ids: list[str] = []
        traversal_guard = 0

        while current_node != sink:
            candidate_arc_ids = [
                arc_id
                for arc_id in outgoing_by_node.get(
                    current_node,
                    (),
                )
                if residual_flow.get(arc_id, 0.0) > numeric_tolerance
            ]

            if not candidate_arc_ids:
                raise ValueError(
                    "Positive committed flow cannot be decomposed into "
                    "a complete source-to-sink path."
                )

            selected_arc_id = candidate_arc_ids[0]
            selected_arc_ids.append(selected_arc_id)
            current_node = head_by_arc[selected_arc_id]

            traversal_guard += 1

            if traversal_guard > len(flow_by_arc) + 1:
                raise ValueError("Committed flow decomposition encountered a cycle.")

        path_volume = min(residual_flow[arc_id] for arc_id in selected_arc_ids)

        if path_volume <= numeric_tolerance:
            raise ValueError("Decomposed path volume must be strictly positive.")

        delivery_arc_ids = [arc_id for arc_id in selected_arc_ids if arc_id in sink_arc_ids]

        if len(delivery_arc_ids) != 1:
            raise ValueError("Each decomposed path requires exactly one delivery arc.")

        delivery_arc_id = delivery_arc_ids[0]

        if selected_arc_ids[-1] != delivery_arc_id:
            raise ValueError("The auxiliary delivery arc must terminate the path.")

        physical_arc_ids = tuple(arc_id for arc_id in selected_arc_ids if arc_id != delivery_arc_id)

        path_number = len(paths) + 1

        paths.append(
            PlannedDemandPath(
                path_id=(f"{commitment.demand_id}::path::{path_number:04d}"),
                demand_id=commitment.demand_id,
                volume=path_volume,
                physical_arc_ids=physical_arc_ids,
                delivery_arc_id=delivery_arc_id,
            )
        )

        for arc_id in selected_arc_ids:
            remaining_flow = residual_flow[arc_id] - path_volume

            residual_flow[arc_id] = (
                0.0 if abs(remaining_flow) <= numeric_tolerance else remaining_flow
            )

    undecomposed_arc_ids = [
        arc_id for arc_id, volume in residual_flow.items() if volume > numeric_tolerance
    ]

    if undecomposed_arc_ids:
        raise ValueError(
            "Positive committed flow remains after path decomposition: "
            f"{tuple(sorted(undecomposed_arc_ids))}."
        )

    decomposed_volume = sum(path.volume for path in paths)

    if abs(decomposed_volume - commitment.accepted_volume) > numeric_tolerance:
        raise ValueError("Path decomposition does not reproduce accepted volume.")

    return tuple(paths)


def accepted_demand_state_at_time(
    instance: ExperimentInstance,
    commitment: DemandCommitment,
    physical_time: int,
) -> tuple[AcceptedDemandState, tuple[PlannedDemandPath, ...]]:
    """Reconstruct one accepted demand's execution state at time tau."""
    validated_time = _validate_nonnegative_integer(
        "physical_time",
        physical_time,
    )

    planned_paths = decompose_commitment_paths(
        instance,
        commitment,
    )
    network_index = instance.network_index_for(commitment.demand_id)

    sink_arc_by_id = {sink_arc.arc_id: sink_arc for sink_arc in network_index.sink_arcs}

    fragments: list[DemandFragment] = []
    delivered_barge_volume = 0.0

    for planned_path in planned_paths:
        delivery_arc = sink_arc_by_id[planned_path.delivery_arc_id]
        delivery_time = int(delivery_arc.tail[1])

        if delivery_time <= validated_time:
            delivered_barge_volume += planned_path.volume
            continue

        executed_arc_ids: list[str] = []
        current_node = network_index.source

        for arc_id in planned_path.physical_arc_ids:
            arc = instance.arc_by_id(arc_id)

            if arc.head[1] <= validated_time:
                executed_arc_ids.append(arc_id)
                current_node = arc.head
            else:
                break

        fragments.append(
            DemandFragment(
                fragment_id=planned_path.path_id,
                demand_id=planned_path.demand_id,
                volume=planned_path.volume,
                current_node=current_node,
                executed_arc_ids=tuple(executed_arc_ids),
            )
        )

    demand_state = AcceptedDemandState(
        demand=commitment.demand,
        acceptance_fraction=commitment.acceptance_fraction,
        fragments=tuple(fragments),
        delivered_barge_volume=delivered_barge_volume,
    )

    return demand_state, planned_paths


def build_execution_snapshot(
    instance: ExperimentInstance,
    booking_state: RollingBookingState,
    physical_time: int,
) -> ExecutionSnapshot:
    """Reconstruct all commitments known by one physical time."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(booking_state, RollingBookingState):
        raise TypeError("booking_state must be a RollingBookingState.")

    validated_time = _validate_nonnegative_integer(
        "physical_time",
        physical_time,
    )

    if booking_state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another experiment instance.")

    demand_states: list[AcceptedDemandState] = []
    planned_paths: list[PlannedDemandPath] = []

    for commitment in booking_state.commitments:
        if commitment.decision_time > validated_time:
            continue

        demand_state, commitment_paths = accepted_demand_state_at_time(
            instance,
            commitment,
            validated_time,
        )

        demand_states.append(demand_state)
        planned_paths.extend(commitment_paths)

    return ExecutionSnapshot(
        physical_time=validated_time,
        instance_fingerprint=instance.demand_fingerprint,
        demand_states=tuple(demand_states),
        planned_paths=tuple(planned_paths),
    )
