"""Persistence for booking-triggered dynamic Full-Reroute."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.dynamic_full_reroute import (
    DynamicFullRerouteModelArtifacts,
    DynamicFullRerouteSolution,
    DynamicFullRerouteValidationReport,
    validate_dynamic_full_reroute_solution,
)
from barge_rerouting.disruption.recovery_transition import (
    RecoveredFragmentPlan,
    RecoveryArcFlow,
    RecoveryOperationalState,
    TruckTransferPlan,
)
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
    PlannedArcFlow,
    validate_commitment_against_instance,
)


def _validate_tolerance(value: object) -> float:
    """Validate one positive finite tolerance."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError("tolerance must be a real number.")

    tolerance = float(value)

    if not isfinite(tolerance):
        raise ValueError("tolerance must be finite.")

    if tolerance <= 0.0:
        raise ValueError("tolerance must be strictly positive.")

    return tolerance


def _normalise_acceptance(
    artifacts: DynamicFullRerouteModelArtifacts,
    solution: DynamicFullRerouteSolution,
    *,
    tolerance: float,
) -> float:
    """Validate and normalize current acceptance."""
    if solution.acceptance_fraction is None:
        raise ValueError("Solved dynamic FR requires an acceptance fraction.")

    acceptance = float(solution.acceptance_fraction)

    if abs(acceptance) <= tolerance:
        acceptance = 0.0
    elif abs(acceptance - 1.0) <= tolerance:
        acceptance = 1.0

    return float(artifacts.event.demand.normalize_acceptance_fraction(acceptance))


def _current_commitment(
    artifacts: DynamicFullRerouteModelArtifacts,
    solution: DynamicFullRerouteSolution,
    *,
    acceptance: float,
    tolerance: float,
) -> DemandCommitment | None:
    """Persist the arriving request as a barge commitment."""
    if solution.current_truck_volume is None:
        raise ValueError("Solved dynamic FR requires current truck volume.")

    current_truck = float(solution.current_truck_volume)

    # The Phase-6--9 contractual state deliberately stores
    # full barge commitments. Immediate current-demand trucking
    # therefore cannot be represented there without changing that
    # invariant or inventing a truck network arc.
    if current_truck > tolerance:
        raise ValueError(
            "Operational dynamic FR cannot persist a "
            "current request transferred directly to truck. "
            "Build the operational model with "
            "allow_current_truck=False."
        )

    if acceptance <= tolerance:
        if any(abs(float(result.volume)) > tolerance for result in solution.current_flows):
            raise ValueError("Rejected current demand retains positive barge flow.")

        return None

    planned_arc_flows = tuple(
        PlannedArcFlow(
            arc_id=result.arc_id,
            volume=float(result.volume),
        )
        for result in solution.current_flows
        if float(result.volume) > tolerance
    )

    commitment = DemandCommitment(
        decision_sequence=artifacts.event.sequence_number,
        decision_time=artifacts.event.decision_time,
        demand=artifacts.event.demand,
        acceptance_fraction=acceptance,
        planned_arc_flows=planned_arc_flows,
    )

    report = validate_commitment_against_instance(
        artifacts.instance,
        commitment,
        tolerance=tolerance,
    )

    if not report.is_valid:
        raise ValueError(f"Dynamic FR current commitment failed validation: {report.violations}.")

    return commitment


def _recovered_fragment_plans(
    artifacts: DynamicFullRerouteModelArtifacts,
    solution: DynamicFullRerouteSolution,
    *,
    tolerance: float,
) -> tuple[
    tuple[RecoveredFragmentPlan, ...],
    tuple[TruckTransferPlan, ...],
]:
    """Persist rerouted prior fragments and incremental trucks."""
    event_id = artifacts.event.event_id

    plans: list[RecoveredFragmentPlan] = []
    transfers: list[TruckTransferPlan] = []

    for index in artifacts.fragment_networks.indexes:
        fragment_id = index.fragment_id
        fragment_state = index.fragment_state

        barge_flows = tuple(
            RecoveryArcFlow(
                arc_id=result.arc_id,
                volume=float(result.volume),
            )
            for result in solution.fragment_flows
            if (result.fragment_id == fragment_id and float(result.volume) > tolerance)
        )

        barge_delivered = float(
            sum(
                solution.fragment_flow_on(
                    fragment_id,
                    sink_arc_id,
                )
                for sink_arc_id in index.sink_arc_ids
            )
        )

        truck_volume = float(solution.fragment_truck_volume_for(fragment_id))

        if abs(truck_volume) <= tolerance:
            truck_volume = 0.0

        transfer: TruckTransferPlan | None = None

        if truck_volume > tolerance:
            transfer = TruckTransferPlan(
                event_id=event_id,
                fragment_id=fragment_id,
                demand_id=index.demand_id,
                transfer_node=(fragment_state.rerouting_source),
                volume=truck_volume,
                penalty_per_teu=(artifacts.truck_penalty_per_teu_by_demand[index.demand_id]),
            )
            transfers.append(transfer)

        plans.append(
            RecoveredFragmentPlan(
                event_id=event_id,
                recovery_time=artifacts.event.decision_time,
                fragment_id=fragment_id,
                demand_id=index.demand_id,
                original_remaining_volume=index.volume,
                rerouting_source=(fragment_state.rerouting_source),
                immutable_arc_ids=(fragment_state.immutable_arc_ids),
                barge_arc_flows=barge_flows,
                barge_delivered_volume=barge_delivered,
                truck_transfer=transfer,
            )
        )

    return tuple(plans), tuple(transfers)


@dataclass(frozen=True, slots=True)
class DynamicFullRerouteTransitionResult:
    """Persistent result of one booking-triggered FR decision."""

    state_before: RecoveryOperationalState
    state_after: RecoveryOperationalState
    current_commitment: DemandCommitment | None
    fragment_plans: tuple[RecoveredFragmentPlan, ...]
    new_truck_transfers: tuple[TruckTransferPlan, ...]
    validation_report: DynamicFullRerouteValidationReport

    def __post_init__(self) -> None:
        """Validate state advancement."""
        if not isinstance(
            self.state_before,
            RecoveryOperationalState,
        ):
            raise TypeError("state_before must be a RecoveryOperationalState.")

        if not isinstance(
            self.state_after,
            RecoveryOperationalState,
        ):
            raise TypeError("state_after must be a RecoveryOperationalState.")

        if (
            self.state_after.booking_state.processed_event_count
            != self.state_before.booking_state.processed_event_count + 1
        ):
            raise ValueError("Dynamic FR must append exactly one booking event.")

        if self.state_after.recovery_event_count != self.state_before.recovery_event_count + 1:
            raise ValueError(
                "Dynamic FR booking must append exactly one rerouting/recovery generation."
            )

        if not isinstance(
            self.validation_report,
            DynamicFullRerouteValidationReport,
        ):
            raise TypeError("validation_report must be a DynamicFullRerouteValidationReport.")

        if not self.validation_report.is_valid:
            raise ValueError("Persisted dynamic FR solution must be independently valid.")

    @property
    def additional_truck_volume(self) -> float:
        """Return only truck volume newly assigned this booking."""
        return float(sum(transfer.volume for transfer in self.new_truck_transfers))

    @property
    def additional_truck_penalty(self) -> float:
        """Return only new truck penalty at this booking."""
        return float(sum(transfer.penalty_value for transfer in self.new_truck_transfers))


def apply_dynamic_full_reroute_solution(
    artifacts: DynamicFullRerouteModelArtifacts,
    solution: DynamicFullRerouteSolution,
    state_before: RecoveryOperationalState,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DynamicFullRerouteTransitionResult:
    """Persist one booking-triggered dynamic FR solution."""
    validated_tolerance = _validate_tolerance(tolerance)

    if not isinstance(
        artifacts,
        DynamicFullRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be DynamicFullRerouteModelArtifacts.")

    if not isinstance(
        solution,
        DynamicFullRerouteSolution,
    ):
        raise TypeError("solution must be DynamicFullRerouteSolution.")

    if not isinstance(
        state_before,
        RecoveryOperationalState,
    ):
        raise TypeError("state_before must be a RecoveryOperationalState.")

    if state_before.booking_state != artifacts.state:
        raise ValueError("Dynamic FR artifacts must use the operational state's booking history.")

    if state_before.instance_fingerprint != artifacts.instance.demand_fingerprint:
        raise ValueError("Operational state belongs to another instance.")

    report = validate_dynamic_full_reroute_solution(
        artifacts,
        solution,
        tolerance=validated_tolerance,
    )

    if not report.is_valid:
        raise ValueError(f"Dynamic FR solution failed independent validation: {report.violations}.")

    acceptance = _normalise_acceptance(
        artifacts,
        solution,
        tolerance=validated_tolerance,
    )

    commitment = _current_commitment(
        artifacts,
        solution,
        acceptance=acceptance,
        tolerance=validated_tolerance,
    )

    booking_state_after = state_before.booking_state.advance(
        artifacts.instance,
        event=artifacts.event,
        commitment=commitment,
    )

    fragment_plans, new_transfers = _recovered_fragment_plans(
        artifacts,
        solution,
        tolerance=validated_tolerance,
    )

    recovered_state = state_before.with_recovery(
        event_id=artifacts.event.event_id,
        fragment_plans=fragment_plans,
        truck_transfers=new_transfers,
    )

    state_after = recovered_state.with_booking_state(booking_state_after)

    return DynamicFullRerouteTransitionResult(
        state_before=state_before,
        state_after=state_after,
        current_commitment=commitment,
        fragment_plans=fragment_plans,
        new_truck_transfers=new_transfers,
        validation_report=report,
    )
