"""Tests for joint current-demand and fragment rerouting."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.rerouting import (
    build_dca_reroute_model,
    build_fragment_network_snapshot,
    build_rerouting_capacity_snapshot,
    build_rerouting_decision_snapshot,
    detect_reroutable_demands,
    solve_dca_reroute_model,
)
from barge_rerouting.rolling_horizon import (
    DemandCommitment,
    PlannedArcFlow,
    RollingBookingState,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def service_arc_id(
    instance: ExperimentInstance,
    service_id: str,
) -> str:
    """Return one transport arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def build_switch_example():
    """Build the controlled capacity-switching instance."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    old_demand = Demand(
        demand_id="KOLD",
        volume=4,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=3,
        category=CustomerCategory.REGULAR,
        fare_per_teu=10,
    )
    current_demand = Demand(
        demand_id="KNEW",
        volume=4,
        origin="B",
        destination="C",
        reservation_time=1,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.FULLY_SPOT,
        fare_per_teu=100,
    )

    instance = assemble_experiment_instance(
        config,
        demands=(
            old_demand,
            current_demand,
        ),
    )
    timeline = build_booking_timeline(instance)

    prefix = service_arc_id(
        instance,
        "S_PREFIX",
    )
    bottleneck = service_arc_id(
        instance,
        "S_BOTTLENECK",
    )
    alt1 = service_arc_id(
        instance,
        "S_ALT1",
    )
    alt2 = service_arc_id(
        instance,
        "S_ALT2",
    )

    old_network = instance.network_index_for("KOLD")
    delivery_at_c2 = str(
        next(sink_arc.arc_id for sink_arc in old_network.sink_arcs if sink_arc.tail == ("C", 2))
    )

    first_event = timeline.event_at_sequence(1)

    old_commitment = DemandCommitment(
        decision_sequence=first_event.sequence_number,
        decision_time=first_event.decision_time,
        demand=old_demand,
        acceptance_fraction=1.0,
        planned_arc_flows=(
            PlannedArcFlow(
                arc_id=prefix,
                volume=4.0,
            ),
            PlannedArcFlow(
                arc_id=bottleneck,
                volume=4.0,
            ),
            PlannedArcFlow(
                arc_id=delivery_at_c2,
                volume=4.0,
            ),
        ),
    )

    state = RollingBookingState.empty(instance)
    state = state.advance(
        instance,
        event=first_event,
        commitment=old_commitment,
    )

    current_event = timeline.event_at_sequence(2)
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution,
        current_event,
    )
    decision = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    rerouting_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    fragment_networks = build_fragment_network_snapshot(
        instance,
        decision,
        rerouting_capacity,
    )

    ordinary_artifacts = build_sequential_booking_model(
        instance,
        state,
        current_event,
        capacity_snapshot=ordinary_capacity,
    )
    ordinary_solution = solve_sequential_booking_model(ordinary_artifacts)

    reroute_artifacts = build_dca_reroute_model(
        instance,
        state,
        current_event,
        rerouting_capacity,
        fragment_networks,
    )
    reroute_solution = solve_dca_reroute_model(reroute_artifacts)

    return {
        "instance": instance,
        "state": state,
        "current_event": current_event,
        "execution": execution,
        "ordinary_capacity": ordinary_capacity,
        "rerouting_capacity": rerouting_capacity,
        "decision": decision,
        "fragment_networks": fragment_networks,
        "ordinary_solution": ordinary_solution,
        "reroute_artifacts": reroute_artifacts,
        "reroute_solution": reroute_solution,
        "prefix": prefix,
        "bottleneck": bottleneck,
        "alt1": alt1,
        "alt2": alt2,
    }


def test_ordinary_dca_rejects_blocked_current_request() -> None:
    """The old reservation leaves no direct capacity."""
    example = build_switch_example()

    ordinary_solution = example["ordinary_solution"]

    assert ordinary_solution.is_solved
    assert ordinary_solution.acceptance_fraction == (pytest.approx(0.0))
    assert ordinary_solution.objective_value == (pytest.approx(0.0))


def test_dca_reroute_accepts_current_request() -> None:
    """Moving old cargo to the alternative route admits KNEW."""
    example = build_switch_example()
    solution = example["reroute_solution"]

    assert solution.is_solved
    assert solution.acceptance_fraction == (pytest.approx(1.0))
    assert solution.objective_value == (pytest.approx(400.0))


def test_old_fragment_moves_to_alternative_route() -> None:
    """KOLD must leave the bottleneck for S_ALT1 and S_ALT2."""
    example = build_switch_example()

    solution = example["reroute_solution"]
    decision = example["decision"]
    fragment_id = decision.fragments[0].fragment_id

    assert solution.fragment_flow_on(
        fragment_id,
        example["bottleneck"],
    ) == pytest.approx(0.0)

    assert solution.fragment_flow_on(
        fragment_id,
        example["alt1"],
    ) == pytest.approx(4.0)

    assert solution.fragment_flow_on(
        fragment_id,
        example["alt2"],
    ) == pytest.approx(4.0)


def test_current_request_uses_released_bottleneck() -> None:
    """KNEW must receive all four TEU on S_BOTTLENECK."""
    example = build_switch_example()
    solution = example["reroute_solution"]

    assert solution.current_flow_on(
        example["bottleneck"],
    ) == pytest.approx(4.0)


def test_every_old_fragment_remains_fully_delivered() -> None:
    """Previously accepted volume cannot be dropped."""
    example = build_switch_example()

    solution = example["reroute_solution"]
    networks = example["fragment_networks"]

    assert len(networks.indexes) == 1

    index = networks.indexes[0]

    assert solution.fragment_delivered_volume(index) == pytest.approx(index.volume)


def test_executed_prefix_is_not_reoptimised() -> None:
    """S_PREFIX remains immutable and absent from the model."""
    example = build_switch_example()

    decision = example["decision"]
    artifacts = example["reroute_artifacts"]

    assert decision.fragments[0].immutable_arc_ids == (example["prefix"],)

    assert example["prefix"] not in artifacts.current_flow_variables
    assert all(arc_id != example["prefix"] for _, arc_id in (artifacts.fragment_flow_variables))
    assert example["prefix"] not in artifacts.capacity_constraints


def test_shared_capacity_is_respected() -> None:
    """The joint flow cannot exceed any available service."""
    example = build_switch_example()

    solution = example["reroute_solution"]
    artifacts = example["reroute_artifacts"]
    fragment_id = example["decision"].fragments[0].fragment_id

    bottleneck_total = solution.current_flow_on(example["bottleneck"]) + solution.fragment_flow_on(
        fragment_id,
        example["bottleneck"],
    )

    assert bottleneck_total == pytest.approx(4.0)
    assert bottleneck_total <= (artifacts.available_capacities[example["bottleneck"]] + 1e-6)


def test_joint_solution_is_deterministic() -> None:
    """Repeated solution extraction gives the same routing."""
    example = build_switch_example()

    second = solve_dca_reroute_model(example["reroute_artifacts"])

    assert second == example["reroute_solution"]


def test_highs_backend_matches_cplex_joint_reroute_solution() -> None:
    """HiGHS must reproduce the validated CPLEX DCA-Reroute optimum."""
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
        solve_dca_reroute_with_backend,
    )

    example = build_switch_example()

    artifacts = example["reroute_artifacts"]
    cplex_solution = example["reroute_solution"]

    try:
        highs_solution = solve_dca_reroute_with_backend(
            artifacts,
            backend=SolverBackend.HIGHS,
        )
    finally:
        artifacts.model.end()

    assert highs_solution.is_solved
    assert cplex_solution.is_solved

    assert highs_solution.objective_value == pytest.approx(cplex_solution.objective_value)

    assert highs_solution.acceptance_fraction == pytest.approx(cplex_solution.acceptance_fraction)

    cplex_current = {result.arc_id: result.volume for result in cplex_solution.current_flows}

    highs_current = {result.arc_id: result.volume for result in highs_solution.current_flows}

    assert set(highs_current) == set(cplex_current)

    for arc_id, value in cplex_current.items():
        assert highs_current[arc_id] == pytest.approx(value)

    cplex_fragments = {
        (
            result.fragment_id,
            result.arc_id,
        ): result.volume
        for result in cplex_solution.fragment_flows
    }

    highs_fragments = {
        (
            result.fragment_id,
            result.arc_id,
        ): result.volume
        for result in highs_solution.fragment_flows
    }

    assert set(highs_fragments) == set(cplex_fragments)

    for key, value in cplex_fragments.items():
        assert highs_fragments[key] == pytest.approx(value)
