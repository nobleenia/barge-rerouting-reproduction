"""Tests for the Phase 0 CPLEX model."""

from pathlib import Path

import pytest

from barge_rerouting.models.toy_lp import solve_toy_model


def test_toy_model_returns_known_optimum(tmp_path: Path) -> None:
    """CPLEX must reproduce the analytically known optimum."""
    result = solve_toy_model(output_root=tmp_path)

    assert result.solve_status.lower() == "optimal"
    assert result.x == pytest.approx(4.0)
    assert result.y == pytest.approx(0.0)
    assert result.objective_value == pytest.approx(12.0)
    assert result.lp_path.exists()
    assert result.log_path.exists()
