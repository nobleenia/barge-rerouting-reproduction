"""Persistent transition after a solved DCA-RRM decision."""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.optimization.dca_rrm import (
    DcaRrmModelArtifacts,
    DcaRrmSolution,
    validate_dca_rrm_solution,
)
from barge_rerouting.rerouting.optimization import (
    DcaRerouteSolution,
)
from barge_rerouting.rerouting.transition import (
    DcaRerouteTransitionResult,
    apply_dca_reroute_solution,
)
from barge_rerouting.rolling_horizon.commitment import (
    COMMITMENT_TOLERANCE,
    DemandCommitment,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


@dataclass(frozen=True, slots=True)
class DcaRrmTransitionResult:
    """Persistent outcome of one combined DCA-RRM solve."""

    state_before: RollingBookingState
    state_after: RollingBookingState
    current_commitment: DemandCommitment | None
    rerouted_commitments: tuple[DemandCommitment, ...]
    discarded_forecast_ids: tuple[str, ...]
    discarded_protected_volume: float
    discarded_expected_future_revenue: float

    def __post_init__(self) -> None:
        """Validate transition and discarded-forecast metadata."""
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
            raise ValueError("A DCA-RRM transition must record exactly one new booking event.")

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

        if not isinstance(
            self.discarded_forecast_ids,
            tuple,
        ):
            raise TypeError("discarded_forecast_ids must be a tuple.")

        normalised_forecast_ids: list[str] = []

        for forecast_id in self.discarded_forecast_ids:
            if not isinstance(forecast_id, str):
                raise TypeError("Every discarded forecast ID must be a string.")

            normalised = forecast_id.strip()

            if not normalised:
                raise ValueError("Every discarded forecast ID must be non-empty.")

            normalised_forecast_ids.append(normalised)

        if len(set(normalised_forecast_ids)) != len(normalised_forecast_ids):
            raise ValueError("Discarded forecast IDs must be unique.")

        if self.discarded_protected_volume < 0.0:
            raise ValueError("discarded_protected_volume must be non-negative.")

        if self.discarded_expected_future_revenue < 0.0:
            raise ValueError("discarded_expected_future_revenue must be non-negative.")

        object.__setattr__(
            self,
            "discarded_forecast_ids",
            tuple(sorted(normalised_forecast_ids)),
        )

    @property
    def current_was_accepted(self) -> bool:
        """Return whether the current demand was accepted."""
        return self.current_commitment is not None

    @property
    def rerouted_demand_ids(self) -> tuple[str, ...]:
        """Return prior demands rebuilt in persistent state."""
        return tuple(commitment.demand_id for commitment in self.rerouted_commitments)


def _persistence_solution(
    artifacts: DcaRrmModelArtifacts,
    solution: DcaRrmSolution,
) -> DcaRerouteSolution:
    """Remove forecast-only components from a DCA-RRM result."""
    if solution.current_revenue is None:
        raise ValueError("A solved DCA-RRM result requires current revenue.")

    return DcaRerouteSolution(
        event_id=solution.event_id,
        demand_id=solution.demand_id,
        is_solved=solution.is_solved,
        solve_status=solution.solve_status,
        objective_value=float(solution.current_revenue),
        acceptance_fraction=solution.acceptance_fraction,
        current_flows=solution.current_flows,
        fragment_flows=solution.fragment_flows,
    )


def apply_dca_rrm_solution(
    artifacts: DcaRrmModelArtifacts,
    solution: DcaRrmSolution,
    *,
    tolerance: float = COMMITMENT_TOLERANCE,
) -> DcaRrmTransitionResult:
    """Persist only realised and rerouted commodities.

    The following forecast-planning quantities are deliberately
    discarded after the booking decision:

    - future selectors;
    - selected protected volumes;
    - tentative future flows;
    - expected future revenue contributions.

    They affect the optimisation decision but do not become
    contractual reservations in the rolling booking state.
    """
    if not isinstance(
        artifacts,
        DcaRrmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRrmModelArtifacts.")

    if not isinstance(solution, DcaRrmSolution):
        raise TypeError("solution must be a DcaRrmSolution.")

    report = validate_dca_rrm_solution(
        artifacts,
        solution,
        tolerance=tolerance,
    )

    if not report.is_valid:
        raise ValueError(f"DCA-RRM solution failed independent validation: {report.violations}.")

    persistence_solution = _persistence_solution(
        artifacts,
        solution,
    )

    base_transition: DcaRerouteTransitionResult = apply_dca_reroute_solution(
        artifacts.base_artifacts,
        persistence_solution,
        tolerance=tolerance,
    )

    return DcaRrmTransitionResult(
        state_before=base_transition.state_before,
        state_after=base_transition.state_after,
        current_commitment=(base_transition.current_commitment),
        rerouted_commitments=(base_transition.rerouted_commitments),
        discarded_forecast_ids=tuple(protection.forecast_id for protection in solution.protections),
        discarded_protected_volume=float(
            sum(protection.protected_volume for protection in solution.protections)
        ),
        discarded_expected_future_revenue=float(solution.future_expected_revenue or 0.0),
    )
