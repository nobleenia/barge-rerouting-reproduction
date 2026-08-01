"""A tiny linear programme used to verify the CPLEX installation.

Mathematical model:

    maximize   3x + 2y
    subject to x + y <= 4
               x, y >= 0

The analytically known optimum is:
    x = 4
    y = 0
    objective = 12
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docplex.mp.model import Model


@dataclass(frozen=True)
class ToySolution:
    """Structured output returned after solving the toy model."""

    x: float
    y: float
    objective_value: float
    solve_status: str
    elapsed_seconds: float
    lp_path: Path
    log_path: Path


def build_toy_model() -> tuple[Model, Any, Any]:
    """Create the toy linear-programming model.

    Returns:
        The DOcplex model together with decision variables x and y.
    """
    model = Model(name="phase0_toy_lp")

    # Continuous nonnegative decision variables.
    x = model.continuous_var(lb=0, name="x")
    y = model.continuous_var(lb=0, name="y")

    # Shared capacity constraint: x + y cannot exceed 4.
    model.add_constraint(x + y <= 4, ctname="shared_capacity")

    # Objective: maximize the total contribution of x and y.
    model.maximize(3 * x + 2 * y)

    return model, x, y


def solve_toy_model(output_root: Path | str = Path("results")) -> ToySolution:
    """Export and solve the toy model using CPLEX.

    Args:
        output_root:
            Root folder under which model exports and solver logs are saved.

    Returns:
        A ToySolution containing the optimum and diagnostic information.

    Raises:
        RuntimeError:
            If CPLEX does not return a feasible solution.
    """
    output_root = Path(output_root)
    export_directory = output_root / "model_exports"
    log_directory = output_root / "solver_logs"

    export_directory.mkdir(parents=True, exist_ok=True)
    log_directory.mkdir(parents=True, exist_ok=True)

    model, x, y = build_toy_model()

    exported_path = model.export_as_lp(
        path=str(export_directory),
        basename="phase0_toy_lp",
    )
    lp_path = Path(exported_path)

    log_path = log_directory / "phase0_toy_lp.log"

    try:
        with log_path.open("w", encoding="utf-8") as log_stream:
            solution = model.solve(log_output=log_stream)

        if solution is None:
            details = model.solve_details
            raise RuntimeError(
                "CPLEX did not return a solution. "
                f"Status: {details.status}; status code: {details.status_code}"
            )

        return ToySolution(
            x=float(solution.get_value(x)),
            y=float(solution.get_value(y)),
            objective_value=float(solution.objective_value),
            solve_status=str(model.solve_details.status),
            elapsed_seconds=float(model.solve_details.time),
            lp_path=lp_path,
            log_path=log_path,
        )
    finally:
        model.end()


def main() -> None:
    """Solve the model and print its result."""
    result = solve_toy_model()

    print("Phase 0 CPLEX model solved successfully")
    print(f"Status:    {result.solve_status}")
    print(f"x:         {result.x:.6f}")
    print(f"y:         {result.y:.6f}")
    print(f"Objective: {result.objective_value:.6f}")
    print(f"Time:      {result.elapsed_seconds:.6f} seconds")
    print(f"LP file:   {result.lp_path}")
    print(f"Log file:  {result.log_path}")


if __name__ == "__main__":
    main()
