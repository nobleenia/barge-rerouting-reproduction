"""Explicit solver-backend selection for existing optimisation models."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barge_rerouting.rerouting.optimization import (
        DcaRerouteModelArtifacts,
        DcaRerouteSolution,
    )

from barge_rerouting.optimization.dca_rm import (
    DcaRmModelArtifacts,
    DcaRmSolution,
    solve_dca_rm_model,
)
from barge_rerouting.optimization.dca_rrm import (
    DcaRrmModelArtifacts,
    DcaRrmSolution,
    solve_dca_rrm_model,
)
from barge_rerouting.optimization.highs_bridge import (
    solve_dca_rm_model_highs,
    solve_dca_rrm_model_highs,
)


class SolverBackend(StrEnum):
    """Supported explicit optimisation backends."""

    CPLEX = "cplex"
    HIGHS = "highs"
    CPLEX_CE_AWARE = "cplex_ce_aware"


CPLEX_COMMUNITY_MAX_VARIABLES = 1000
CPLEX_COMMUNITY_MAX_CONSTRAINTS = 1000


def select_cplex_ce_aware_backend(
    variable_count: int,
    constraint_count: int,
) -> SolverBackend:
    """Select CPLEX when the model fits the local Community Edition.

    HiGHS is selected only when either model dimension exceeds the
    local CPLEX Community Edition limit. Selection depends only on
    model dimensions and occurs before optimisation.
    """
    if isinstance(variable_count, bool) or not isinstance(
        variable_count,
        int,
    ):
        raise TypeError("variable_count must be an integer.")

    if isinstance(constraint_count, bool) or not isinstance(
        constraint_count,
        int,
    ):
        raise TypeError("constraint_count must be an integer.")

    if variable_count < 0:
        raise ValueError("variable_count must be non-negative.")

    if constraint_count < 0:
        raise ValueError("constraint_count must be non-negative.")

    if (
        variable_count <= CPLEX_COMMUNITY_MAX_VARIABLES
        and constraint_count <= CPLEX_COMMUNITY_MAX_CONSTRAINTS
    ):
        return SolverBackend.CPLEX

    return SolverBackend.HIGHS


def resolve_solver_backend(
    backend: SolverBackend,
    model: object,
) -> SolverBackend:
    """Resolve an explicit or CE-aware backend before solving."""
    if not isinstance(backend, SolverBackend):
        raise TypeError("backend must be a SolverBackend.")

    if backend is not SolverBackend.CPLEX_CE_AWARE:
        return backend

    variable_count = getattr(
        model,
        "number_of_variables",
        None,
    )
    constraint_count = getattr(
        model,
        "number_of_constraints",
        None,
    )

    if not isinstance(variable_count, int):
        raise TypeError("model.number_of_variables must be an integer.")

    if not isinstance(constraint_count, int):
        raise TypeError("model.number_of_constraints must be an integer.")

    return select_cplex_ce_aware_backend(
        variable_count,
        constraint_count,
    )


def solve_dca_rm_with_backend(
    artifacts: DcaRmModelArtifacts,
    *,
    backend: SolverBackend,
) -> DcaRmSolution:
    """Solve one DCA-RM model with the declared backend."""
    if not isinstance(
        backend,
        SolverBackend,
    ):
        raise TypeError("backend must be a SolverBackend.")

    backend = resolve_solver_backend(backend, artifacts.model)

    if backend is SolverBackend.CPLEX:
        return solve_dca_rm_model(artifacts)

    if backend is SolverBackend.HIGHS:
        return solve_dca_rm_model_highs(artifacts)

    raise ValueError(f"Unsupported solver backend: {backend}")


def solve_dca_rrm_with_backend(
    artifacts: DcaRrmModelArtifacts,
    *,
    backend: SolverBackend,
) -> DcaRrmSolution:
    """Solve one DCA-RRM model with the declared backend."""
    if not isinstance(
        backend,
        SolverBackend,
    ):
        raise TypeError("backend must be a SolverBackend.")

    backend = resolve_solver_backend(backend, artifacts.model)

    if backend is SolverBackend.CPLEX:
        return solve_dca_rrm_model(artifacts)

    if backend is SolverBackend.HIGHS:
        return solve_dca_rrm_model_highs(artifacts)

    raise ValueError(f"Unsupported solver backend: {backend}")


def solve_dca_reroute_with_backend(
    artifacts: DcaRerouteModelArtifacts,
    *,
    backend: SolverBackend = SolverBackend.CPLEX,
) -> DcaRerouteSolution:
    """Solve DCA-Reroute using an explicit or CE-aware backend."""
    from barge_rerouting.optimization.highs_bridge import (
        solve_dca_reroute_model_highs,
    )
    from barge_rerouting.rerouting.optimization import (
        DcaRerouteModelArtifacts,
        solve_dca_reroute_model,
    )

    if not isinstance(
        artifacts,
        DcaRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRerouteModelArtifacts.")

    resolved = resolve_solver_backend(
        backend,
        artifacts.model,
    )

    if resolved is SolverBackend.CPLEX:
        return solve_dca_reroute_model(artifacts)

    if resolved is SolverBackend.HIGHS:
        return solve_dca_reroute_model_highs(artifacts)

    raise ValueError(f"Unsupported resolved solver backend: {resolved}")
