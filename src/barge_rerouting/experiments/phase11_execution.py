"""Phase 11 execution semantics for publication-facing experiments.

This module contains experiment-layer interpretations that must not
silently alter the validated core booking and rerouting mechanisms.
"""

from __future__ import annotations

from enum import StrEnum

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
)


class Phase11EventDisposition(StrEnum):
    """How a Phase 11 incoming booking event was resolved."""

    OPTIMISATION_SOLVED = "optimisation_solved"
    FEASIBILITY_REJECTED = "feasibility_rejected"
    SOLVER_FAILURE = "solver_failure"


def is_proven_infeasible_status(
    solve_status: str,
) -> bool:
    """Return whether a solver status explicitly certifies infeasibility.

    This deliberately excludes ambiguous states such as
    'infeasible or unbounded', time limits, numerical failures,
    and unknown termination statuses.
    """
    if not isinstance(solve_status, str):
        raise TypeError("solve_status must be a string.")

    normalised = " ".join(solve_status.strip().lower().split())

    if not normalised:
        raise ValueError("solve_status must be non-empty.")

    return normalised == "infeasible" or normalised.endswith(" infeasible")


def advance_regular_feasibility_rejection(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    *,
    solve_status: str,
) -> RollingBookingState:
    """Record one A036 infeasible Regular request and continue.

    The optimisation model itself is not modified. The current
    request receives no commitment, existing commitments remain
    unchanged, and the booking sequence advances by one.

    Only an explicitly certified infeasible Regular event may use
    this transition.
    """
    if not isinstance(
        instance,
        ExperimentInstance,
    ):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        state,
        RollingBookingState,
    ):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(
        event,
        BookingDecisionEvent,
    ):
        raise TypeError("event must be a BookingDecisionEvent.")

    if event.demand.category is not CustomerCategory.REGULAR:
        raise ValueError("A036 applies only to Regular requests.")

    if not is_proven_infeasible_status(solve_status):
        raise ValueError("A036 requires a solver status that explicitly certifies infeasibility.")

    return state.advance(
        instance,
        event=event,
        commitment=None,
    )
