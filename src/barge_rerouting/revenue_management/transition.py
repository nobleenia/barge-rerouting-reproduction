"""Persistence of realised current decisions from DCA-RM solutions."""

from __future__ import annotations

from math import isfinite

from barge_rerouting.optimization.dca_rm import (
    DcaRmModelArtifacts,
    DcaRmSolution,
    validate_dca_rm_solution,
)
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
    PlannedArcFlow,
    validate_commitment_against_instance,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def _validate_tolerance(value: object) -> float:
    """Validate and return a positive finite tolerance."""
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


def commitment_from_dca_rm_solution(
    artifacts: DcaRmModelArtifacts,
    solution: DcaRmSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DemandCommitment | None:
    """Convert only the realised current decision into a commitment.

    Future selectors, protected volumes, and tentative future flows
    are optimisation information. They are deliberately excluded
    from persistent booking state.
    """
    if not isinstance(
        artifacts,
        DcaRmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRmModelArtifacts.")

    if not isinstance(solution, DcaRmSolution):
        raise TypeError("solution must be a DcaRmSolution.")

    validated_tolerance = _validate_tolerance(tolerance)

    if not solution.is_solved:
        raise ValueError("An unsolved DCA-RM model cannot create a commitment.")

    if solution.acceptance_fraction is None:
        raise ValueError("Solved DCA-RM decision has no acceptance value.")

    if solution.current_revenue is None:
        raise ValueError("Solved DCA-RM decision has no current revenue.")

    if solution.future_expected_revenue is None:
        raise ValueError("Solved DCA-RM decision has no future value.")

    if solution.objective_value is None:
        raise ValueError("Solved DCA-RM decision has no objective value.")

    if solution.event_id != artifacts.event.event_id:
        raise ValueError("Solution event does not match model artifacts.")

    if solution.demand_id != artifacts.event.demand_id:
        raise ValueError("Solution demand does not match model artifacts.")

    report = validate_dca_rm_solution(
        artifacts,
        solution,
        tolerance=validated_tolerance,
    )

    if not report.is_valid:
        raise ValueError("DCA-RM solution failed independent validation.")

    demand = artifacts.event.demand
    acceptance = float(solution.acceptance_fraction)

    if abs(acceptance) <= validated_tolerance:
        acceptance = 0.0
    elif abs(acceptance - 1.0) <= validated_tolerance:
        acceptance = 1.0

    acceptance = demand.normalize_acceptance_fraction(
        acceptance,
        tolerance=validated_tolerance,
    )

    expected_current_revenue = demand.maximum_revenue * acceptance

    if abs(float(solution.current_revenue) - expected_current_revenue) > validated_tolerance:
        raise ValueError("DCA-RM current revenue does not match the realised acceptance decision.")

    expected_objective = float(solution.current_revenue) + float(solution.future_expected_revenue)

    if abs(float(solution.objective_value) - expected_objective) > validated_tolerance:
        raise ValueError(
            "DCA-RM objective does not equal current revenue plus future expected contribution."
        )

    if acceptance <= validated_tolerance:
        if any(abs(flow.volume) > validated_tolerance for flow in solution.current_flows):
            raise ValueError("A rejected current demand cannot retain positive current flow.")

        return None

    planned_arc_flows = tuple(
        PlannedArcFlow(
            arc_id=flow.arc_id,
            volume=flow.volume,
        )
        for flow in solution.current_flows
        if flow.volume > validated_tolerance
    )

    commitment = DemandCommitment(
        decision_sequence=artifacts.event.sequence_number,
        decision_time=artifacts.event.decision_time,
        demand=demand,
        acceptance_fraction=acceptance,
        planned_arc_flows=planned_arc_flows,
    )

    commitment_report = validate_commitment_against_instance(
        artifacts.instance,
        commitment,
        tolerance=validated_tolerance,
    )

    if not commitment_report.is_valid:
        raise ValueError("Realised DCA-RM commitment failed network validation.")

    for (
        arc_id,
        available_capacity,
    ) in artifacts.available_capacities.items():
        planned_volume = commitment.planned_volume_on(arc_id)

        if planned_volume - available_capacity > validated_tolerance:
            raise ValueError(f"Realised current commitment exceeds available capacity on {arc_id}.")

    return commitment


def apply_dca_rm_solution(
    artifacts: DcaRmModelArtifacts,
    solution: DcaRmSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> RollingBookingState:
    """Persist one current acceptance or rejection.

    No future protection variable or tentative future flow is carried
    into the returned booking state.
    """
    commitment = commitment_from_dca_rm_solution(
        artifacts,
        solution,
        tolerance=tolerance,
    )

    return artifacts.state.advance(
        artifacts.instance,
        event=artifacts.event,
        commitment=commitment,
    )
