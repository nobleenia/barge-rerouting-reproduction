"""Inspect a controlled sequential DCA-RRM run."""

from dataclasses import replace
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
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.rrm_run import (
    run_time_aware_dca_rrm,
)


def main() -> None:
    """Run the controlled opportunity-cost example."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))
    config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "CURRENT",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                10,
            ),
            Demand(
                "FUTURE",
                4,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )

    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(0, 0.50),
            VolumeProbability(4, 0.50),
        ),
    )

    def provider(event, state):
        del state

        if event.demand_id == "CURRENT":
            return (forecast,)

        return ()

    run = run_time_aware_dca_rrm(
        instance,
        provider,
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )

    print("Phase 9D sequential DCA-RRM inspection")
    print()

    header = (
        f"{'Seq.':>4} "
        f"{'Demand':<10} "
        f"{'Solved':<7} "
        f"{'Accept':>8} "
        f"{'Revenue':>10} "
        f"{'Future':>10} "
        f"{'Objective':>11} "
        f"{'Rerouted':<16} "
        f"{'Protected':<16}"
    )
    print(header)
    print("-" * len(header))

    for result in run.results:
        acceptance = (
            "—" if result.acceptance_fraction is None else f"{result.acceptance_fraction:.3f}"
        )

        print(
            f"{result.event.sequence_number:>4} "
            f"{result.event.demand_id:<10} "
            f"{str(result.event_was_processed):<7} "
            f"{acceptance:>8} "
            f"{result.current_realised_revenue:>10.2f} "
            f"{result.future_expected_revenue:>10.2f} "
            f"{result.optimisation_objective:>11.2f} "
            f"{','.join(result.rerouted_demand_ids) or '-':<16} "
            f"{','.join(result.protected_forecast_ids) or '-':<16}"
        )

    print()
    print(f"Completed:                    {run.completed}")
    print(f"Processed events:             {run.processed_event_count}")
    print(f"Accepted realised volume:     {run.accepted_volume:.2f}")
    print(f"Realised revenue:             {run.total_realised_revenue:.2f}")
    print(f"Summed event objectives:      {run.summed_event_objectives:.2f}")
    print(f"Expected future contribution: {run.total_expected_future_contribution:.2f}")
    print(f"Discarded tentative volume:   {run.cumulative_discarded_future_volume:.2f}")
    print(f"Accepted demand IDs:          {run.final_state.accepted_demand_ids}")
    print(f"Rejected demand IDs:          {run.final_state.rejected_demand_ids}")


if __name__ == "__main__":
    main()
