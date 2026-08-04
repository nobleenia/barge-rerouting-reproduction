"""Persistent accepted-demand commitments and planned arc flows."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import Demand
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization import (
    DcaSolution,
    validate_dca_solution,
)
from barge_rerouting.rolling_horizon.timeline import BookingDecisionEvent

COMMITMENT_TOLERANCE = 1e-6


def _validate_positive_integer(name: str, value: object) -> int:
    """Validate and return a strictly positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return value


def _validate_nonnegative_integer(name: str, value: object) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_tolerance(value: object) -> float:
    """Validate and return a strictly positive numerical tolerance."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("tolerance must be a real number.")

    tolerance = float(value)

    if not isfinite(tolerance):
        raise ValueError("tolerance must be finite.")

    if tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")

    return tolerance


@dataclass(frozen=True, slots=True)
class PlannedArcFlow:
    """Positive planned volume on one flow arc."""

    arc_id: str
    volume: float

    def __post_init__(self) -> None:
        """Validate and normalise the planned flow."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        arc_id = self.arc_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        if isinstance(self.volume, bool) or not isinstance(
            self.volume,
            (int, float),
        ):
            raise TypeError("volume must be a real number.")

        volume = float(self.volume)

        if not isfinite(volume):
            raise ValueError("volume must be finite.")

        if volume <= 0:
            raise ValueError("volume must be strictly positive.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(self, "volume", volume)


@dataclass(frozen=True, slots=True)
class DemandCommitment:
    """Persistent positively accepted booking and its future flow plan."""

    decision_sequence: int
    decision_time: int
    demand: Demand
    acceptance_fraction: float
    planned_arc_flows: tuple[PlannedArcFlow, ...]

    def __post_init__(self) -> None:
        """Validate and normalise the accepted commitment."""
        decision_sequence = _validate_positive_integer(
            "decision_sequence",
            self.decision_sequence,
        )
        decision_time = _validate_nonnegative_integer(
            "decision_time",
            self.decision_time,
        )

        if not isinstance(self.demand, Demand):
            raise TypeError("demand must be a Demand object.")

        if decision_time != self.demand.reservation_time:
            raise ValueError("decision_time must equal the demand reservation time.")

        acceptance_fraction = self.demand.normalize_acceptance_fraction(self.acceptance_fraction)

        if acceptance_fraction <= COMMITMENT_TOLERANCE:
            raise ValueError("A rejected demand must not create a DemandCommitment.")

        if not isinstance(self.planned_arc_flows, tuple):
            raise TypeError("planned_arc_flows must be a tuple.")

        planned_arc_flows = tuple(self.planned_arc_flows)

        if not planned_arc_flows:
            raise ValueError("An accepted commitment requires positive planned arc flows.")

        for planned_flow in planned_arc_flows:
            if not isinstance(planned_flow, PlannedArcFlow):
                raise TypeError("Every planned flow must be a PlannedArcFlow object.")

        arc_ids = [planned_flow.arc_id for planned_flow in planned_arc_flows]

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("A commitment may contain only one flow per arc identifier.")

        object.__setattr__(
            self,
            "decision_sequence",
            decision_sequence,
        )
        object.__setattr__(self, "decision_time", decision_time)
        object.__setattr__(
            self,
            "acceptance_fraction",
            acceptance_fraction,
        )
        object.__setattr__(
            self,
            "planned_arc_flows",
            tuple(
                sorted(
                    planned_arc_flows,
                    key=lambda planned_flow: planned_flow.arc_id,
                )
            ),
        )

    @property
    def event_id(self) -> str:
        """Return the booking event that created this commitment."""
        return f"booking::{self.decision_sequence:04d}::{self.demand.demand_id}"

    @property
    def demand_id(self) -> str:
        """Return the committed demand identifier."""
        return str(self.demand.demand_id)

    @property
    def accepted_volume(self) -> float:
        """Return the positively committed cargo volume."""
        return float(self.demand.volume) * float(self.acceptance_fraction)

    @property
    def planned_arc_ids(self) -> tuple[str, ...]:
        """Return all arcs used by the stored future plan."""
        return tuple(planned_flow.arc_id for planned_flow in self.planned_arc_flows)

    def planned_volume_on(self, arc_id: str) -> float:
        """Return planned volume on one arc, or zero when unused."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for planned_flow in self.planned_arc_flows:
            if planned_flow.arc_id == normalised_arc_id:
                return float(planned_flow.volume)

        return 0.0


@dataclass(frozen=True, slots=True)
class CommitmentValidationReport:
    """Independent validation results for one stored commitment."""

    is_valid: bool
    max_flow_balance_violation: float
    sink_balance_violation: float
    max_capacity_violation: float
    violations: tuple[str, ...]


def validate_commitment_against_instance(
    instance: ExperimentInstance,
    commitment: DemandCommitment,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> CommitmentValidationReport:
    """Validate a stored flow plan against its assembled demand network."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(commitment, DemandCommitment):
        raise TypeError("commitment must be a DemandCommitment.")

    validated_tolerance = _validate_tolerance(tolerance)

    instance_demand = instance.demand_by_id(commitment.demand_id)

    if instance_demand != commitment.demand:
        raise ValueError("Commitment demand does not match the assembled instance.")

    network_index = instance.network_index_for(commitment.demand_id)
    permitted_arc_ids = set(network_index.all_flow_arc_ids)

    unknown_arc_ids = set(commitment.planned_arc_ids).difference(permitted_arc_ids)

    if unknown_arc_ids:
        raise ValueError("Commitment contains arcs outside its feasible demand network.")

    flow_lookup = {
        planned_flow.arc_id: float(planned_flow.volume)
        for planned_flow in commitment.planned_arc_flows
    }

    violations: list[str] = []
    max_flow_balance_violation = 0.0
    max_capacity_violation = 0.0

    for node_index in network_index.node_flow_indexes:
        node = node_index.node

        outgoing_flow = sum(
            flow_lookup.get(arc_id, 0.0) for arc_id in network_index.outgoing_flow_arc_ids(node)
        )
        incoming_flow = sum(
            flow_lookup.get(arc_id, 0.0) for arc_id in network_index.incoming_flow_arc_ids(node)
        )

        required_balance = commitment.accepted_volume if node == network_index.source else 0.0

        balance_violation = abs(outgoing_flow - incoming_flow - required_balance)

        max_flow_balance_violation = max(
            max_flow_balance_violation,
            balance_violation,
        )

        if balance_violation > validated_tolerance:
            violations.append(f"Flow-balance violation at {node}: {balance_violation}.")

    delivered_volume = sum(
        flow_lookup.get(sink_arc_id, 0.0) for sink_arc_id in network_index.sink_arc_ids
    )

    sink_balance_violation = abs(delivered_volume - commitment.accepted_volume)

    if sink_balance_violation > validated_tolerance:
        violations.append(f"Auxiliary-sink balance violation: {sink_balance_violation}.")

    for arc_id in network_index.feasible_arc_ids:
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no capacity.")

        capacity_violation = max(
            0.0,
            flow_lookup.get(arc_id, 0.0) - arc.nominal_capacity,
        )

        max_capacity_violation = max(
            max_capacity_violation,
            capacity_violation,
        )

        if capacity_violation > validated_tolerance:
            violations.append(f"Capacity violation on {arc.arc_id}: {capacity_violation}.")

    return CommitmentValidationReport(
        is_valid=not violations,
        max_flow_balance_violation=max_flow_balance_violation,
        sink_balance_violation=sink_balance_violation,
        max_capacity_violation=max_capacity_violation,
        violations=tuple(violations),
    )


def commitment_from_dca_solution(
    instance: ExperimentInstance,
    event: BookingDecisionEvent,
    solution: DcaSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DemandCommitment | None:
    """Convert one solved booking decision into a persistent commitment.

    A rejected demand returns ``None``.
    """
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(solution, DcaSolution):
        raise TypeError("solution must be a DcaSolution.")

    validated_tolerance = _validate_tolerance(tolerance)

    instance_demand = instance.demand_by_id(event.demand_id)

    if instance_demand != event.demand:
        raise ValueError("Booking event demand does not match the assembled instance.")

    solution_report = validate_dca_solution(
        instance,
        solution,
        tolerance=validated_tolerance,
    )

    if not solution_report.is_valid:
        raise ValueError(
            "The DCA solution failed independent validation and cannot "
            "create a persistent commitment."
        )

    acceptance_fraction = solution.acceptance_for(event.demand_id)

    if acceptance_fraction <= validated_tolerance:
        return None

    network_index = instance.network_index_for(event.demand_id)
    planned_arc_flows: list[PlannedArcFlow] = []

    for arc_id in network_index.all_flow_arc_ids:
        volume = solution.flow_for(event.demand_id, arc_id)

        if volume < -validated_tolerance:
            raise ValueError(f"Negative planned flow found on arc {arc_id}.")

        if volume > validated_tolerance:
            planned_arc_flows.append(
                PlannedArcFlow(
                    arc_id=arc_id,
                    volume=volume,
                )
            )

    commitment = DemandCommitment(
        decision_sequence=event.sequence_number,
        decision_time=event.decision_time,
        demand=event.demand,
        acceptance_fraction=acceptance_fraction,
        planned_arc_flows=tuple(planned_arc_flows),
    )

    commitment_report = validate_commitment_against_instance(
        instance,
        commitment,
        tolerance=validated_tolerance,
    )

    if not commitment_report.is_valid:
        raise ValueError(
            "The extracted commitment is inconsistent with its demand-specific network."
        )

    return commitment
