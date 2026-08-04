"""Tests for persistence of solved DCA-Reroute decisions."""

from pathlib import Path

import pytest

from barge_rerouting.config import (
    load_experiment_config,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.rerouting import (
    apply_dca_reroute_solution,
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
    build_transport_capacity_snapshot,
    decompose_commitment_paths,
)


def service_arc_id(
    instance: ExperimentInstance,
    service_id: str,
) -> str:
    """Return one scheduled transport arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def build_transition_example():
    """Build, solve, and persist the controlled rerouting event."""
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
        decision_sequence=1,
        decision_time=0,
        demand=old_demand,
        acceptance_fraction=1.0,
        planned_arc_flows=(
            PlannedArcFlow(prefix, 4.0),
            PlannedArcFlow(bottleneck, 4.0),
            PlannedArcFlow(delivery_at_c2, 4.0),
        ),
    )

    state = RollingBookingState.empty(instance)
    state = state.advance(
        instance,
        event=first_event,
        commitment=old_commitment,
    )

    current_event = timeline.event_at_sequence(2)
    execution_before = build_execution_snapshot(
        instance,
        state,
        physical_time=1,
    )
    capacity_before = build_transport_capacity_snapshot(
        instance,
        execution_before,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_before,
        current_event,
    )
    decision = build_rerouting_decision_snapshot(
        instance,
        capacity_before,
        eligibility,
    )
    rerouting_capacity = build_rerouting_capacity_snapshot(
        instance,
        capacity_before,
        eligibility,
    )
    fragment_networks = build_fragment_network_snapshot(
        instance,
        decision,
        rerouting_capacity,
    )
    artifacts = build_dca_reroute_model(
        instance,
        state,
        current_event,
        rerouting_capacity,
        fragment_networks,
    )
    solution = solve_dca_reroute_model(artifacts)
    transition = apply_dca_reroute_solution(
        artifacts,
        solution,
    )

    execution_after = build_execution_snapshot(
        instance,
        transition.state_after,
        physical_time=1,
    )
    capacity_after = build_transport_capacity_snapshot(
        instance,
        execution_after,
    )

    return {
        "instance": instance,
        "state_before": state,
        "transition": transition,
        "execution_after": execution_after,
        "capacity_after": capacity_after,
        "prefix": prefix,
        "bottleneck": bottleneck,
        "alt1": alt1,
        "alt2": alt2,
    }


def commitment_for(state, demand_id: str):
    """Return one positive commitment from a booking state."""
    return next(commitment for commitment in state.commitments if commitment.demand_id == demand_id)


def test_transition_records_current_event_once() -> None:
    """Persistence must append exactly one current booking record."""
    example = build_transition_example()

    before = example["state_before"]
    after = example["transition"].state_after

    assert before.processed_event_count == 1
    assert after.processed_event_count == 2
    assert after.accepted_demand_ids == (
        "KOLD",
        "KNEW",
    )
    assert example["transition"].current_was_accepted


def test_prior_booking_metadata_is_preserved() -> None:
    """Rerouting changes the route, not the original booking decision."""
    example = build_transition_example()

    old_before = commitment_for(
        example["state_before"],
        "KOLD",
    )
    old_after = commitment_for(
        example["transition"].state_after,
        "KOLD",
    )

    assert old_after.decision_sequence == (old_before.decision_sequence)
    assert old_after.decision_time == old_before.decision_time
    assert old_after.demand == old_before.demand
    assert old_after.acceptance_fraction == pytest.approx(old_before.acceptance_fraction)
    assert old_after.accepted_volume == pytest.approx(4.0)


def test_old_commitment_stores_new_complete_route() -> None:
    """The executed prefix and new alternative suffix must coexist."""
    example = build_transition_example()

    instance = example["instance"]
    old_after = commitment_for(
        example["transition"].state_after,
        "KOLD",
    )
    paths = decompose_commitment_paths(
        instance,
        old_after,
    )

    assert len(paths) == 1
    assert paths[0].physical_arc_ids == (
        example["prefix"],
        example["alt1"],
        example["alt2"],
    )
    assert paths[0].delivery_arc_id.startswith("delivery::KOLD::C@3")

    assert old_after.planned_volume_on(example["bottleneck"]) == pytest.approx(0.0)


def test_current_commitment_uses_released_service() -> None:
    """The new request must persist its bottleneck route."""
    example = build_transition_example()

    instance = example["instance"]
    current = commitment_for(
        example["transition"].state_after,
        "KNEW",
    )
    paths = decompose_commitment_paths(
        instance,
        current,
    )

    assert len(paths) == 1
    assert paths[0].physical_arc_ids == (example["bottleneck"],)
    assert paths[0].delivery_arc_id.startswith("delivery::KNEW::C@2")
    assert current.accepted_volume == pytest.approx(4.0)


def test_rebuilt_execution_preserves_completed_prefix() -> None:
    """The historical S_PREFIX movement must remain executed."""
    example = build_transition_example()

    execution = example["execution_after"]

    assert execution.executed_transport_volume(
        example["instance"],
        example["prefix"],
    ) == pytest.approx(4.0)

    old_state = execution.demand_state_for("KOLD")

    assert old_state.remaining_volume == pytest.approx(4.0)
    assert old_state.fragments[0].current_node == ("B", 1)
    assert old_state.fragments[0].executed_arc_ids == (example["prefix"],)


def test_capacity_snapshot_reflects_new_owners() -> None:
    """Future reservations must match the persisted rerouted plans."""
    example = build_transition_example()

    capacity = example["capacity_after"]

    prefix = capacity.state_for(example["prefix"])
    bottleneck = capacity.state_for(example["bottleneck"])
    alt1 = capacity.state_for(example["alt1"])
    alt2 = capacity.state_for(example["alt2"])

    assert prefix.completed_volume == pytest.approx(4.0)
    assert prefix.future_reserved_volume == pytest.approx(0.0)

    assert bottleneck.future_reserved_volume == pytest.approx(4.0)
    assert alt1.future_reserved_volume == pytest.approx(4.0)
    assert alt2.future_reserved_volume == pytest.approx(4.0)


def test_transition_is_deterministic() -> None:
    """Applying the same solved decision gives the same new state."""
    first = build_transition_example()
    second = build_transition_example()

    assert first["transition"] == second["transition"]
    assert first["capacity_after"] == second["capacity_after"]
