"""Demonstrate opportunity-cost decisions in DCA-RM."""

from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.optimization.dca_rm import (
    build_dca_rm_model,
    solve_dca_rm_model,
    validate_dca_rm_solution,
)
from barge_rerouting.revenue_management import (
    select_explicit_future_set,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    build_booking_timeline,
)


def solve_case(probability_four: float):
    """Solve one zero-or-four future forecast case."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))
    current = Demand(
        "CURRENT",
        4,
        "A",
        "C",
        0,
        0,
        2,
        CustomerCategory.PARTIALLY_SPOT,
        10,
    )
    instance = assemble_experiment_instance(
        config,
        demands=(current,),
    )
    state = RollingBookingState.empty(instance)
    event = build_booking_timeline(instance).event_at_sequence(1)

    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(
                0,
                1.0 - probability_four,
            ),
            VolumeProbability(
                4,
                probability_four,
            ),
        ),
    )
    future_set = select_explicit_future_set(
        instance,
        event,
        (forecast,),
    )
    artifacts = build_dca_rm_model(
        instance,
        state,
        event,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        solution = solve_dca_rm_model(artifacts)
        report = validate_dca_rm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    if not report.is_valid:
        raise RuntimeError(report.violations)

    return solution


def main() -> None:
    """Display the probability-driven decision reversal."""
    high = solve_case(0.50)
    low = solve_case(0.05)

    print("Phase 8C DCA-RM opportunity-cost gate")
    print("Case               Current acceptance  Future maxvol  Objective")

    for name, solution in (
        ("High probability", high),
        ("Low probability", low),
    ):
        protection = solution.protection_for("FUTURE")

        print(
            f"{name:<19}"
            f"{solution.acceptance_fraction:>18.2f}"
            f"{protection.protected_volume:>15.2f}"
            f"{solution.objective_value:>11.2f}"
        )

    print()
    print("High-probability future value exceeds the current request's revenue.")
    print("Lowering the future probability reverses the capacity-protection decision.")


if __name__ == "__main__":
    main()
