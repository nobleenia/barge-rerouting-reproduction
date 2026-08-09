"""Tests for deterministic CPLEX Community Edition solver selection."""

import pytest

from barge_rerouting.optimization.solver_backend import (
    SolverBackend,
    select_cplex_ce_aware_backend,
)


@pytest.mark.parametrize(
    ("variables", "constraints"),
    (
        (0, 0),
        (194, 159),
        (999, 999),
        (1000, 1000),
        (1000, 1),
        (1, 1000),
    ),
)
def test_ce_aware_selection_uses_cplex_within_limits(
    variables: int,
    constraints: int,
) -> None:
    assert (
        select_cplex_ce_aware_backend(
            variables,
            constraints,
        )
        is SolverBackend.CPLEX
    )


@pytest.mark.parametrize(
    ("variables", "constraints"),
    (
        (1001, 1),
        (1, 1001),
        (1001, 1001),
        (1051, 798),
        (1199, 906),
        (2874, 2164),
    ),
)
def test_ce_aware_selection_uses_highs_above_limits(
    variables: int,
    constraints: int,
) -> None:
    assert (
        select_cplex_ce_aware_backend(
            variables,
            constraints,
        )
        is SolverBackend.HIGHS
    )


@pytest.mark.parametrize(
    ("variables", "constraints"),
    (
        (-1, 0),
        (0, -1),
    ),
)
def test_ce_aware_selection_rejects_negative_dimensions(
    variables: int,
    constraints: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        select_cplex_ce_aware_backend(
            variables,
            constraints,
        )


@pytest.mark.parametrize(
    ("variables", "constraints"),
    (
        (True, 1),
        (1, False),
        (1.5, 1),
        (1, 2.5),
    ),
)
def test_ce_aware_selection_rejects_invalid_types(
    variables: object,
    constraints: object,
) -> None:
    with pytest.raises(TypeError):
        select_cplex_ce_aware_backend(  # type: ignore[arg-type]
            variables,
            constraints,
        )


def test_disruption_ce_aware_imports_in_clean_process() -> None:
    """Dynamic disruption runners must not depend on import order."""
    import subprocess
    import sys

    code = (
        "from barge_rerouting.disruption.partial_reroute "
        "import run_partial_reroute; "
        "from barge_rerouting.disruption.dynamic_full_reroute_run "
        "import run_dynamic_full_reroute; "
        "from barge_rerouting.optimization.solver_backend "
        "import SolverBackend; "
        "assert callable(run_partial_reroute); "
        "assert callable(run_dynamic_full_reroute); "
        "assert SolverBackend.CPLEX_CE_AWARE.value "
        "== 'cplex_ce_aware'"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
