"""Explicit solver-backend selection for existing optimisation models."""

from __future__ import annotations

from enum import StrEnum

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

    if backend is SolverBackend.CPLEX:
        return solve_dca_rrm_model(artifacts)

    if backend is SolverBackend.HIGHS:
        return solve_dca_rrm_model_highs(artifacts)

    raise ValueError(f"Unsupported solver backend: {backend}")
