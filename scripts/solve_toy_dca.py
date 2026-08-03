"""Solve and validate the canonical twenty-demand DCA instance."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
    validate_dca_solution,
)


def main() -> None:
    """Build, export, solve, validate, and summarise the canonical DCA model."""
    config = load_experiment_config("configs/toy_experiment.yaml")
    instance = assemble_experiment_instance(config)
    artifacts = build_dca_model(instance)

    model_directory = Path("results/models")
    model_directory.mkdir(parents=True, exist_ok=True)

    exported_model_path = artifacts.model.export_as_lp(
        basename="toy_dca",
        path=str(model_directory),
    )

    solution = solve_dca_model(artifacts)

    print("Canonical DCA model")
    print(f"Experiment:          {config.experiment_name}")
    print(f"Fingerprint:         {instance.demand_fingerprint}")
    print(f"Acceptance variables:{artifacts.acceptance_variable_count:>5}")
    print(f"Flow variables:      {artifacts.flow_variable_count:>5}")
    print(f"Flow constraints:    {len(artifacts.flow_balance_constraints):>5}")
    print(f"Sink constraints:    {len(artifacts.sink_balance_constraints):>5}")
    print(f"Capacity constraints:{len(artifacts.capacity_constraints):>5}")
    print(f"LP model:            {exported_model_path}")
    print(f"Solve status:        {solution.solve_status}")

    if not solution.is_solved:
        print("No feasible solution was returned.")
        return

    report = validate_dca_solution(
        instance,
        solution,
    )

    acceptance_lookup = {
        result.demand_id: result.acceptance_fraction for result in solution.acceptances
    }

    category_counts: Counter[str] = Counter()
    accepted_volume = 0.0
    requested_volume = 0.0

    for demand in instance.demands:
        acceptance = acceptance_lookup[demand.demand_id]
        requested_volume += demand.volume
        accepted_volume += demand.volume * acceptance

        if acceptance > 1e-6:
            category_counts[demand.category.value] += 1

    print(f"Objective:           {solution.objective_value}")
    print(f"Validation passed:   {report.is_valid}")
    print(f"Objective check:     {report.recomputed_objective}")
    print(f"Requested volume:    {requested_volume}")
    print(f"Accepted volume:     {accepted_volume}")
    print(f"Accepted R demands:  {category_counts['R']}")
    print(f"Accepted P demands:  {category_counts['P']}")
    print(f"Accepted F demands:  {category_counts['F']}")
    print(f"Max flow violation:  {report.max_flow_balance_violation:.3e}")
    print(f"Max sink violation:  {report.max_sink_balance_violation:.3e}")
    print(f"Max capacity excess: {report.max_capacity_violation:.3e}")

    print()
    print("Transport-arc utilisation:")

    flow_lookup = {(result.demand_id, result.arc_id): result.volume for result in solution.flows}

    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        used_capacity = sum(
            flow_lookup.get(
                (network_index.demand_id, arc.arc_id),
                0.0,
            )
            for network_index in instance.demand_network_indexes
        )

        print(f"  {arc.arc_id}: {used_capacity:.2f}/{arc.nominal_capacity:.2f} TEU")


if __name__ == "__main__":
    main()
