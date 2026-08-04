"""Persistent state transition after a solved DCA-Reroute decision."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import TimeSpaceNode
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.network import (
    FragmentNetworkIndex,
)
from barge_rerouting.rerouting.optimization import (
    DcaRerouteModelArtifacts,
    DcaRerouteSolution,
)
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
    PlannedArcFlow,
    validate_commitment_against_instance,
)
from barge_rerouting.rolling_horizon.execution import (
    decompose_commitment_paths,
)
from barge_rerouting.rolling_horizon.state import (
    BookingDecisionRecord,
    RollingBookingState,
)


def _validate_tolerance(value: object) -> float:
    """Validate and return a finite positive tolerance."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("tolerance must be a real number.")

    tolerance = float(value)

    if not isfinite(tolerance):
        raise ValueError("tolerance must be finite.")

    if tolerance <= 0:
        raise ValueError("tolerance must be strictly positive.")

    return tolerance


def _add_flow(
    flow_by_arc: dict[str, float],
    arc_id: str,
    volume: float,
    *,
    tolerance: float,
) -> None:
    """Add one positive arc flow to an aggregate flow plan."""
    if not isinstance(arc_id, str):
        raise TypeError("arc_id must be a string.")

    normalised_arc_id = arc_id.strip()

    if not normalised_arc_id:
        raise ValueError("arc_id must be non-empty.")

    numeric_volume = float(volume)

    if not isfinite(numeric_volume):
        raise ValueError("Arc flow must be finite.")

    if numeric_volume < -tolerance:
        raise ValueError(f"Negative solved flow on {normalised_arc_id}: {numeric_volume}.")

    if numeric_volume <= tolerance:
        return

    flow_by_arc[normalised_arc_id] = flow_by_arc.get(normalised_arc_id, 0.0) + numeric_volume


def _normalise_acceptance_fraction(
    artifacts: DcaRerouteModelArtifacts,
    solution: DcaRerouteSolution,
    *,
    tolerance: float,
) -> float:
    """Validate and normalise the current acceptance decision."""
    if solution.acceptance_fraction is None:
        raise ValueError("A solved DCA-Reroute solution requires an acceptance fraction.")

    acceptance_fraction = float(solution.acceptance_fraction)

    if abs(acceptance_fraction) <= tolerance:
        acceptance_fraction = 0.0
    elif abs(acceptance_fraction - 1.0) <= tolerance:
        acceptance_fraction = 1.0

    return float(artifacts.event.demand.normalize_acceptance_fraction(acceptance_fraction))


def _validate_solution_indexes(
    artifacts: DcaRerouteModelArtifacts,
    solution: DcaRerouteSolution,
) -> None:
    """Ensure the extracted solution covers every model variable."""
    current_arc_ids = tuple(result.arc_id for result in solution.current_flows)

    if len(set(current_arc_ids)) != len(current_arc_ids):
        raise ValueError("Current-demand solution arc identifiers must be unique.")

    if set(current_arc_ids) != set(artifacts.current_flow_variables):
        raise ValueError("Current-demand solution flows do not match the model variable index.")

    fragment_arc_keys = tuple(
        (
            result.fragment_id,
            result.arc_id,
        )
        for result in solution.fragment_flows
    )

    if len(set(fragment_arc_keys)) != len(fragment_arc_keys):
        raise ValueError("Fragment solution arc identifiers must be unique.")

    if set(fragment_arc_keys) != set(artifacts.fragment_flow_variables):
        raise ValueError("Fragment solution flows do not match the model variable index.")


def _validate_solution(
    artifacts: DcaRerouteModelArtifacts,
    solution: DcaRerouteSolution,
    *,
    tolerance: float,
) -> float:
    """Validate one solved result against its model artifacts."""
    if not isinstance(
        artifacts,
        DcaRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRerouteModelArtifacts.")

    if not isinstance(solution, DcaRerouteSolution):
        raise TypeError("solution must be a DcaRerouteSolution.")

    if not solution.is_solved:
        raise ValueError("An unsolved DCA-Reroute model cannot update state.")

    if solution.event_id != artifacts.event.event_id:
        raise ValueError("Solution event does not match the model event.")

    if solution.demand_id != artifacts.event.demand_id:
        raise ValueError("Solution demand does not match the model event.")

    if solution.objective_value is None:
        raise ValueError("A solved DCA-Reroute solution requires an objective value.")

    acceptance_fraction = _normalise_acceptance_fraction(
        artifacts,
        solution,
        tolerance=tolerance,
    )
    expected_objective = artifacts.event.demand.maximum_revenue * acceptance_fraction

    if abs(float(solution.objective_value) - expected_objective) > tolerance:
        raise ValueError("DCA-Reroute objective does not match the current acceptance decision.")

    _validate_solution_indexes(
        artifacts,
        solution,
    )

    return acceptance_fraction


def _original_delivery_arc_id(
    instance: ExperimentInstance,
    *,
    demand_id: str,
    destination_node: TimeSpaceNode,
) -> str:
    """Map a fragment delivery node to the original demand sink arc."""
    network_index = instance.network_index_for(demand_id)

    matching_arc_ids = tuple(
        str(sink_arc.arc_id)
        for sink_arc in network_index.sink_arcs
        if sink_arc.tail == destination_node
    )

    if len(matching_arc_ids) != 1:
        raise ValueError(
            "Expected exactly one original delivery arc for "
            f"demand {demand_id} at {destination_node}; "
            f"found {len(matching_arc_ids)}."
        )

    return matching_arc_ids[0]


def _current_commitment_from_solution(
    artifacts: DcaRerouteModelArtifacts,
    solution: DcaRerouteSolution,
    *,
    acceptance_fraction: float,
    tolerance: float,
) -> DemandCommitment | None:
    """Build the current request's persistent commitment."""
    if acceptance_fraction <= tolerance:
        if any(abs(float(result.volume)) > tolerance for result in solution.current_flows):
            raise ValueError("A rejected current demand cannot retain positive flow.")

        return None

    planned_arc_flows: list[PlannedArcFlow] = []

    for result in solution.current_flows:
        volume = float(result.volume)

        if volume < -tolerance:
            raise ValueError(f"Negative current-demand flow on {result.arc_id}.")

        if volume <= tolerance:
            continue

        planned_arc_flows.append(
            PlannedArcFlow(
                arc_id=result.arc_id,
                volume=volume,
            )
        )

    commitment = DemandCommitment(
        decision_sequence=(artifacts.event.sequence_number),
        decision_time=artifacts.event.decision_time,
        demand=artifacts.event.demand,
        acceptance_fraction=acceptance_fraction,
        planned_arc_flows=tuple(planned_arc_flows),
    )

    report = validate_commitment_against_instance(
        artifacts.instance,
        commitment,
        tolerance=tolerance,
    )

    if not report.is_valid:
        raise ValueError(
            f"The current DCA-Reroute commitment failed validation: {report.violations}."
        )

    return commitment


def _indexes_by_demand(
    artifacts: DcaRerouteModelArtifacts,
) -> dict[str, tuple[FragmentNetworkIndex, ...]]:
    """Group fragment networks by original demand."""
    grouped: dict[str, list[FragmentNetworkIndex]] = {}

    for index in artifacts.fragment_networks.indexes:
        grouped.setdefault(
            index.demand_id,
            [],
        ).append(index)

    return {
        demand_id: tuple(
            sorted(
                indexes,
                key=lambda index: index.fragment_id,
            )
        )
        for demand_id, indexes in grouped.items()
    }


def _rebuild_prior_commitment(
    instance: ExperimentInstance,
    old_commitment: DemandCommitment,
    indexes: tuple[FragmentNetworkIndex, ...],
    solution: DcaRerouteSolution,
    *,
    tolerance: float,
) -> DemandCommitment:
    """Replace only the reroutable paths of one prior commitment."""
    if not indexes:
        raise ValueError("A rerouted commitment requires fragment indexes.")

    index_by_fragment_id = {index.fragment_id: index for index in indexes}

    if len(index_by_fragment_id) != len(indexes):
        raise ValueError("Fragment indexes must have unique identifiers.")

    if {index.demand_id for index in indexes} != {old_commitment.demand_id}:
        raise ValueError("Every fragment index must belong to the reconstructed commitment.")

    flow_by_arc: dict[str, float] = {}
    reconstructed_fragment_ids: set[str] = set()

    for old_path in decompose_commitment_paths(
        instance,
        old_commitment,
        tolerance=tolerance,
    ):
        index = index_by_fragment_id.get(old_path.path_id)

        if index is None:
            # This path was already delivered or otherwise excluded.
            # Its complete original flow remains unchanged.
            for arc_id in old_path.all_arc_ids:
                _add_flow(
                    flow_by_arc,
                    arc_id,
                    old_path.volume,
                    tolerance=tolerance,
                )

            continue

        reconstructed_fragment_ids.add(old_path.path_id)

        decision_state = index.fragment_state
        eligibility_state = decision_state.fragment_state

        if eligibility_state.old_path != old_path:
            raise ValueError(
                "Fragment index old path does not match the stored commitment decomposition."
            )

        if abs(index.volume - old_path.volume) > tolerance:
            raise ValueError("Fragment volume differs from its old decomposed path volume.")

        # Preserve completed and currently in-transit movements.
        for arc_id in decision_state.immutable_arc_ids:
            _add_flow(
                flow_by_arc,
                arc_id,
                index.volume,
                tolerance=tolerance,
            )

        # Add the newly optimised future physical flow.
        for arc_id in index.feasible_arc_ids:
            _add_flow(
                flow_by_arc,
                arc_id,
                solution.fragment_flow_on(
                    index.fragment_id,
                    arc_id,
                ),
                tolerance=tolerance,
            )

        # Convert fragment-specific sink arcs back into the
        # original demand's delivery arcs.
        for sink_arc in index.sink_arcs:
            solved_volume = solution.fragment_flow_on(
                index.fragment_id,
                str(sink_arc.arc_id),
            )
            original_delivery_arc_id = _original_delivery_arc_id(
                instance,
                demand_id=index.demand_id,
                destination_node=sink_arc.tail,
            )

            _add_flow(
                flow_by_arc,
                original_delivery_arc_id,
                solved_volume,
                tolerance=tolerance,
            )

    missing_fragment_ids = set(index_by_fragment_id).difference(reconstructed_fragment_ids)

    if missing_fragment_ids:
        raise ValueError(
            "Fragment networks were not found in the old "
            f"commitment paths: {tuple(sorted(missing_fragment_ids))}."
        )

    rebuilt_commitment = DemandCommitment(
        decision_sequence=(old_commitment.decision_sequence),
        decision_time=old_commitment.decision_time,
        demand=old_commitment.demand,
        acceptance_fraction=(old_commitment.acceptance_fraction),
        planned_arc_flows=tuple(
            PlannedArcFlow(
                arc_id=arc_id,
                volume=volume,
            )
            for arc_id, volume in sorted(flow_by_arc.items())
        ),
    )

    report = validate_commitment_against_instance(
        instance,
        rebuilt_commitment,
        tolerance=tolerance,
    )

    if not report.is_valid:
        raise ValueError(f"A rebuilt prior commitment failed validation: {report.violations}.")

    return rebuilt_commitment


def _validate_global_capacity(
    instance: ExperimentInstance,
    state: RollingBookingState,
    *,
    tolerance: float,
) -> None:
    """Validate aggregate capacity across all stored commitments."""
    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no capacity.")

        reserved_volume = state.reserved_transport_volume(
            instance,
            arc.arc_id,
        )

        if reserved_volume - arc.nominal_capacity > tolerance:
            raise ValueError(
                "Updated booking state exceeds capacity on "
                f"{arc.arc_id}: reserved={reserved_volume}, "
                f"capacity={arc.nominal_capacity}."
            )


@dataclass(frozen=True, slots=True)
class DcaRerouteTransitionResult:
    """Persistent state produced by one solved rerouting event."""

    state_before: RollingBookingState
    state_after: RollingBookingState
    current_commitment: DemandCommitment | None
    rerouted_commitments: tuple[DemandCommitment, ...]

    def __post_init__(self) -> None:
        """Validate transition ordering and commitment identity."""
        if not isinstance(
            self.state_before,
            RollingBookingState,
        ):
            raise TypeError("state_before must be a RollingBookingState.")

        if not isinstance(
            self.state_after,
            RollingBookingState,
        ):
            raise TypeError("state_after must be a RollingBookingState.")

        if self.state_before.instance_fingerprint != self.state_after.instance_fingerprint:
            raise ValueError("Transition states must belong to the same instance.")

        if self.state_after.processed_event_count != self.state_before.processed_event_count + 1:
            raise ValueError("A DCA-Reroute transition must record exactly one new event.")

        if self.current_commitment is not None and not isinstance(
            self.current_commitment,
            DemandCommitment,
        ):
            raise TypeError("current_commitment must be a DemandCommitment or None.")

        if not isinstance(
            self.rerouted_commitments,
            tuple,
        ):
            raise TypeError("rerouted_commitments must be a tuple.")

        for commitment in self.rerouted_commitments:
            if not isinstance(
                commitment,
                DemandCommitment,
            ):
                raise TypeError("Every rerouted commitment must be a DemandCommitment.")

        demand_ids = tuple(commitment.demand_id for commitment in self.rerouted_commitments)

        if len(set(demand_ids)) != len(demand_ids):
            raise ValueError("Rerouted commitment demand identifiers must be unique.")

        object.__setattr__(
            self,
            "rerouted_commitments",
            tuple(
                sorted(
                    self.rerouted_commitments,
                    key=lambda commitment: (
                        commitment.decision_sequence,
                        commitment.demand_id,
                    ),
                )
            ),
        )

    @property
    def current_was_accepted(self) -> bool:
        """Return whether the current event created a commitment."""
        return self.current_commitment is not None

    @property
    def rerouted_demand_ids(self) -> tuple[str, ...]:
        """Return prior demands whose stored routes changed."""
        return tuple(commitment.demand_id for commitment in self.rerouted_commitments)


def apply_dca_reroute_solution(
    artifacts: DcaRerouteModelArtifacts,
    solution: DcaRerouteSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DcaRerouteTransitionResult:
    """Persist prior reroutes and the current booking decision."""
    validated_tolerance = _validate_tolerance(tolerance)
    acceptance_fraction = _validate_solution(
        artifacts,
        solution,
        tolerance=validated_tolerance,
    )

    grouped_indexes = _indexes_by_demand(artifacts)
    prior_commitment_by_id = {
        commitment.demand_id: commitment for commitment in artifacts.state.commitments
    }

    unknown_demand_ids = set(grouped_indexes).difference(prior_commitment_by_id)

    if unknown_demand_ids:
        raise ValueError(
            "Fragment networks reference demands without "
            "prior commitments: "
            f"{tuple(sorted(unknown_demand_ids))}."
        )

    replacement_by_demand_id: dict[
        str,
        DemandCommitment,
    ] = {}

    for demand_id, indexes in grouped_indexes.items():
        replacement_by_demand_id[demand_id] = _rebuild_prior_commitment(
            artifacts.instance,
            prior_commitment_by_id[demand_id],
            indexes,
            solution,
            tolerance=validated_tolerance,
        )

    revised_records: list[BookingDecisionRecord] = []

    for record in artifacts.state.records:
        replacement = replacement_by_demand_id.get(record.demand_id)

        if replacement is None:
            revised_records.append(record)
            continue

        if record.commitment is None:
            raise ValueError("A rejected prior event cannot be rerouted.")

        revised_records.append(
            BookingDecisionRecord(
                event=record.event,
                commitment=replacement,
            )
        )

    revised_prior_state = RollingBookingState(
        instance_fingerprint=(artifacts.state.instance_fingerprint),
        records=tuple(revised_records),
    )

    current_commitment = _current_commitment_from_solution(
        artifacts,
        solution,
        acceptance_fraction=acceptance_fraction,
        tolerance=validated_tolerance,
    )

    updated_state = revised_prior_state.advance(
        artifacts.instance,
        event=artifacts.event,
        commitment=current_commitment,
    )

    _validate_global_capacity(
        artifacts.instance,
        updated_state,
        tolerance=validated_tolerance,
    )

    return DcaRerouteTransitionResult(
        state_before=artifacts.state,
        state_after=updated_state,
        current_commitment=current_commitment,
        rerouted_commitments=tuple(replacement_by_demand_id.values()),
    )
