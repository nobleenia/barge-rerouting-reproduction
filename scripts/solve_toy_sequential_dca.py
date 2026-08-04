"""Run canonical sequential DCA and compare it with static DCA."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
)
from barge_rerouting.rolling_horizon import (
    diagnose_booking_feasibility,
    run_sequential_dca,
)


def main() -> None:
    """Solve the static benchmark and canonical sequential process."""
    config = load_experiment_config("configs/toy_experiment.yaml")

    quiet_config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(quiet_config)

    static_solution = solve_dca_model(build_dca_model(instance))
    sequential_run = run_sequential_dca(instance)

    output_directory = Path("results/sequential")
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / "toy_sequential_dca_events.csv"

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as output_file:
        writer = csv.writer(output_file)
        writer.writerow(
            (
                "sequence",
                "decision_time",
                "demand_id",
                "category",
                "requested_volume",
                "solved",
                "solve_status",
                "acceptance_fraction",
                "accepted_volume",
                "event_revenue",
                "capacity_transitions",
            )
        )

        for result in sequential_run.results:
            transition_text = ";".join(
                (
                    f"{transition.arc_id}:"
                    f"{transition.residual_before:.6f}->"
                    f"{transition.residual_after:.6f}"
                )
                for transition in result.capacity_transitions
            )

            writer.writerow(
                (
                    result.event.sequence_number,
                    result.event.decision_time,
                    result.demand_id,
                    result.event.demand.category.value,
                    result.event.demand.volume,
                    result.is_solved,
                    result.solve_status,
                    result.acceptance_fraction,
                    result.accepted_volume,
                    result.objective_value,
                    transition_text,
                )
            )

    print("Canonical sequential DCA")
    print(f"Experiment:          {quiet_config.experiment_name}")
    print(f"Fingerprint:         {instance.demand_fingerprint}")
    print(f"Timeline events:     {sequential_run.timeline.event_count}")
    print(f"Processed results:   {len(sequential_run.results)}")
    print(f"Completed:           {sequential_run.completed}")
    print()

    for result in sequential_run.results:
        if not result.is_solved:
            decision = "UNSOLVED"
            acceptance_text = "-"
            revenue_text = "-"
        elif result.is_accepted:
            decision = "ACCEPTED"
            acceptance_text = f"{result.acceptance_fraction:.4f}"
            revenue_text = f"{result.objective_value:.2f}"
        else:
            decision = "REJECTED"
            acceptance_text = f"{result.acceptance_fraction:.4f}"
            revenue_text = f"{result.objective_value:.2f}"

        print(
            f"{result.event.sequence_number:02d} "
            f"| t={result.event.decision_time} "
            f"| {result.demand_id} "
            f"| {result.event.demand.category.value} "
            f"| requested={result.event.demand.volume:.2f} "
            f"| {decision} "
            f"| acceptance={acceptance_text} "
            f"| accepted={result.accepted_volume:.2f} "
            f"| revenue={revenue_text}"
        )

    print()
    print(f"Sequential revenue:  {sequential_run.total_revenue:.2f}")
    print(f"Sequential volume:   {sequential_run.accepted_volume:.2f}")
    print(f"Accepted demands:   {sequential_run.final_state.accepted_demand_ids}")
    print(f"Rejected demands:   {sequential_run.final_state.rejected_demand_ids}")

    if static_solution.is_solved:
        static_objective = float(static_solution.objective_value or 0.0)
        print(f"Static objective:    {static_objective:.2f}")

        if sequential_run.completed:
            revenue_gap = static_objective - sequential_run.total_revenue
            gap_percentage = 100.0 * revenue_gap / static_objective if static_objective > 0 else 0.0

            print(f"Static advantage:    {revenue_gap:.2f}")
            print(f"Relative gap:        {gap_percentage:.2f}%")
        else:
            print(
                "Static comparison:   sequential run terminated before all demands were processed"
            )

    failure = sequential_run.failure_result

    if failure is not None:
        print()
        print("Sequential failure")
        print(f"Demand:              {failure.demand_id}")
        print(f"Category:            {failure.event.demand.category.value}")
        print(f"Status:              {failure.solve_status}")

        if failure.event.demand.category.value == "R":
            print(
                "Interpretation:      prior commitments left no feasible "
                "capacity for a mandatory regular request"
            )

        diagnostic = diagnose_booking_feasibility(
            instance,
            sequential_run.final_state,
            failure.event,
        )

        print(f"Required volume:      {diagnostic.required_volume:.2f}")
        print(f"Maximum routable:     {diagnostic.maximum_routable_volume:.2f}")
        print(f"Volume shortfall:     {diagnostic.volume_shortfall:.2f}")
        print("Minimum-cut bottlenecks:")

        for bottleneck in diagnostic.bottleneck_arcs:
            print(
                f"  {bottleneck.arc_id} "
                f"| service={bottleneck.service_id} "
                f"| residual={bottleneck.residual_capacity:.2f} "
                f"| nominal={bottleneck.nominal_capacity:.2f}"
            )

    print()
    print(f"Event log:           {output_path}")


if __name__ == "__main__":
    main()
