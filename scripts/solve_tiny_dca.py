"""Solve a controlled three-demand DCA example."""

from __future__ import annotations

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
)


def main() -> None:
    """Build and solve the controlled DCA example."""
    config = load_experiment_config("configs/toy_experiment.yaml")

    demands = (
        Demand(
            demand_id="R001",
            volume=4.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.REGULAR,
            fare_per_teu=10.0,
        ),
        Demand(
            demand_id="P001",
            volume=6.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=20.0,
        ),
        Demand(
            demand_id="F001",
            volume=8.0,
            origin="B",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=2,
            category=CustomerCategory.FULLY_SPOT,
            fare_per_teu=100.0,
        ),
    )

    instance = assemble_experiment_instance(
        config,
        demands=demands,
    )
    artifacts = build_dca_model(instance)
    solution = solve_dca_model(artifacts)

    service_arc = next(arc for arc in instance.arcs if arc.service_id == "S6")

    print("DCA solution")
    print(f"Status:              {solution.solve_status}")
    print(f"Solved:              {solution.is_solved}")
    print(f"Objective:           {solution.objective_value}")
    print(f"Acceptance variables: {artifacts.acceptance_variable_count}")
    print(f"Flow variables:       {artifacts.flow_variable_count}")
    print()

    for demand in instance.demands:
        acceptance = solution.acceptance_for(demand.demand_id)
        service_flow = solution.flow_for(
            demand.demand_id,
            service_arc.arc_id,
        )

        print(
            demand.demand_id,
            "| category=",
            demand.category.value,
            "| requested=",
            demand.volume,
            "| accepted fraction=",
            acceptance,
            "| service flow=",
            service_flow,
        )

    total_service_flow = sum(
        solution.flow_for(
            demand.demand_id,
            service_arc.arc_id,
        )
        for demand in instance.demands
    )

    print()
    print(f"Shared service:      {service_arc.arc_id}")
    print(f"Capacity:            {service_arc.nominal_capacity}")
    print(f"Used capacity:       {total_service_flow}")


if __name__ == "__main__":
    main()
