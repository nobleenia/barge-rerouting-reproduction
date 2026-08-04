"""Demonstrate Full-Reroute over a complete booking timeline."""

from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import (
    load_experiment_config,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.rerouting import (
    run_full_reroute,
)


def main() -> None:
    """Run the three-request shared-capacity example."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
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
                "K001",
                4,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                8,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                20,
            ),
            Demand(
                "K003",
                6,
                "B",
                "A",
                0,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )

    run = run_full_reroute(instance)

    print("Phase 7 complete Full-Reroute run")
    print("Event                     Ordinary  Full-Reroute  Prior commitments rebuilt")

    for result in run.results:
        print(
            f"{result.event.event_id:<25}"
            f"{result.ordinary_acceptance_fraction:>8.2f}"
            f"{result.reroute_acceptance_fraction:>14.2f}  "
            f"{result.rerouted_demand_ids}"
        )

    print()
    print(f"Completed:                 {run.completed}")
    print(f"Processed events:          {run.processed_event_count}")
    print(f"Accepted demands:          {run.final_state.accepted_demand_ids}")
    print(f"Rejected demands:          {run.final_state.rejected_demand_ids}")
    print(f"Accepted volume:           {run.accepted_volume:.1f}")
    print(f"Full-Reroute revenue:      {run.total_revenue:.1f}")
    print(f"Ordinary event revenue:    {run.ordinary_total_revenue:.1f}")
    print(f"Acceptance improvements:   {run.acceptance_improvement_count}")
    print(f"Events reoptimising prior: {run.events_with_prior_reoptimization}")


if __name__ == "__main__":
    main()
