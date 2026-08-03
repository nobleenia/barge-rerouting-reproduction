"""Tests for the deterministic current-demand allocation model."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.optimization import (
    build_dca_model,
    solve_dca_model,
)


def build_controlled_instance() -> ExperimentInstance:
    """Create a capacity-constrained three-demand instance."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

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

    return assemble_experiment_instance(
        config,
        demands=demands,
    )


def test_model_has_expected_variable_and_constraint_indexes() -> None:
    """The controlled instance must produce predictable model dimensions."""
    artifacts = build_dca_model(build_controlled_instance())

    assert artifacts.acceptance_variable_count == 3
    assert artifacts.flow_variable_count == 6
    assert len(artifacts.flow_balance_constraints) == 6
    assert len(artifacts.sink_balance_constraints) == 3
    assert len(artifacts.capacity_constraints) == 1


def test_controlled_dca_solution_respects_customer_categories() -> None:
    """Regular is mandatory, partial fills residual capacity, binary is rejected."""
    artifacts = build_dca_model(build_controlled_instance())
    solution = solve_dca_model(artifacts)

    assert solution.is_solved
    assert solution.objective_value == pytest.approx(160.0)

    assert solution.acceptance_for("R001") == pytest.approx(1.0)
    assert solution.acceptance_for("P001") == pytest.approx(1.0)
    assert solution.acceptance_for("F001") == pytest.approx(0.0)


def test_shared_transport_capacity_is_not_exceeded() -> None:
    """Total routed volume on S6 must equal its ten-TEU capacity."""
    instance = build_controlled_instance()
    artifacts = build_dca_model(instance)
    solution = solve_dca_model(artifacts)

    service_arc = next(arc for arc in instance.arcs if arc.service_id == "S6")

    total_flow = sum(
        solution.flow_for(
            demand.demand_id,
            service_arc.arc_id,
        )
        for demand in instance.demands
    )

    assert total_flow == pytest.approx(10.0)
    assert total_flow <= float(service_arc.nominal_capacity)


def test_transport_and_delivery_flows_are_equal_per_demand() -> None:
    """Destination conservation must transfer transport flow into the sink."""
    instance = build_controlled_instance()
    artifacts = build_dca_model(instance)
    solution = solve_dca_model(artifacts)

    service_arc = next(arc for arc in instance.arcs if arc.service_id == "S6")

    for network_index in instance.demand_network_indexes:
        transport_flow = solution.flow_for(
            network_index.demand_id,
            service_arc.arc_id,
        )
        delivery_flow = solution.flow_for(
            network_index.demand_id,
            network_index.sink_arc_ids[0],
        )

        assert delivery_flow == pytest.approx(transport_flow)
