"""Demonstrate physical-time-aware sequential DCA orchestration."""

from __future__ import annotations

from dataclasses import replace

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rolling_horizon import (
    diagnose_booking_feasibility,
    run_time_aware_sequential_dca,
)


def main() -> None:
    """Run a controlled two-time case and the canonical diagnostic."""
    config = load_experiment_config("configs/toy_experiment.yaml")
    quiet_config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    controlled_instance = assemble_experiment_instance(
        quiet_config,
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "B",
                0,
                0,
                1,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                6,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.REGULAR,
                20,
            ),
        ),
    )

    controlled_run = run_time_aware_sequential_dca(controlled_instance)

    print("Controlled time-aware sequential DCA")
    print(f"Completed:       {controlled_run.completed}")
    print(f"Epochs:          {len(controlled_run.epochs)}")
    print(f"Revenue:         {controlled_run.total_revenue:.2f}")
    print(f"Accepted volume: {controlled_run.accepted_volume:.2f}")
    print()

    for epoch in controlled_run.epochs:
        print(f"Physical time {epoch.physical_time}")
        print(
            "  before: "
            f"remaining={epoch.execution_before.remaining_volume:.2f}, "
            f"delivered={epoch.execution_before.delivered_barge_volume:.2f}"
        )

        for result in epoch.event_results:
            print(
                f"  event={result.demand_id}, "
                f"solved={result.is_solved}, "
                f"acceptance={result.acceptance_fraction}, "
                f"accepted={result.accepted_volume:.2f}"
            )

        print(
            "  after:  "
            f"remaining={epoch.execution_after.remaining_volume:.2f}, "
            f"delivered={epoch.execution_after.delivered_barge_volume:.2f}"
        )
        print()

    canonical_instance = assemble_experiment_instance(quiet_config)
    canonical_run = run_time_aware_sequential_dca(canonical_instance)

    print("Canonical time-aware sequential DCA")
    print(f"Completed:         {canonical_run.completed}")
    print(f"Epochs reached:    {len(canonical_run.epochs)}")
    print(f"Events attempted:  {len(canonical_run.results)}")
    print(f"Revenue before stop: {canonical_run.total_revenue:.2f}")

    failure = canonical_run.failure_result

    if failure is not None:
        diagnostic = diagnose_booking_feasibility(
            canonical_instance,
            canonical_run.final_state,
            failure.event,
        )

        print(f"Failure demand:    {failure.demand_id}")
        print(f"Failure time:      {failure.event.decision_time}")
        print(f"Status:            {failure.solve_status}")
        print(f"Maximum routable:  {diagnostic.maximum_routable_volume:.2f}")
        print(f"Shortfall:         {diagnostic.volume_shortfall:.2f}")
        print(f"Bottleneck arcs:   {diagnostic.bottleneck_arc_ids}")


if __name__ == "__main__":
    main()
