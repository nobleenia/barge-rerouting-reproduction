"""Regression tests for lossless HiGHS variable-name bridging."""

import pytest
from docplex.mp.model import Model

from barge_rerouting.optimization.highs_bridge import (
    _value_of,
    solve_docplex_mip_with_highs,
)


def test_highs_round_trip_with_very_long_variable_names() -> None:
    """HiGHS extraction must not depend on LP long-name preservation."""
    model = Model(name="highs_long_name_regression")

    common = "fragment_v__" + "__recovery__booking__".join(f"{index:04d}" for index in range(300))

    x_name = common + "__branch_A__sink"
    y_name = common + "__branch_B__sink"

    x = model.continuous_var(
        lb=0.0,
        name=x_name,
    )
    y = model.continuous_var(
        lb=0.0,
        name=y_name,
    )

    model.add_constraint(x == 1.0)
    model.add_constraint(y == 2.0)

    model.minimize(x + y)

    result = solve_docplex_mip_with_highs(
        model,
        time_limit_seconds=30.0,
        relative_mip_gap=0.0,
        log_output=False,
    )

    assert result.is_solved
    assert result.objective_value == pytest.approx(3.0)

    assert _value_of(
        result.values,
        x,
    ) == pytest.approx(1.0)

    assert _value_of(
        result.values,
        y,
    ) == pytest.approx(2.0)

    # The temporary aliasing must not mutate the
    # model retained by the calling code.
    assert x.name == x_name
    assert y.name == y_name

    assert x_name in result.values
    assert y_name in result.values

    assert not any(name.startswith("v_000") for name in result.values)
