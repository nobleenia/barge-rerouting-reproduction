"""Tests for one complete Full-Reroute booking event."""

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
    run_full_reroute_event,
)
from barge_rerouting.rolling_horizon import (
    DemandCommitment,
    PlannedArcFlow,
    RollingBookingState,
    build_booking_timeline,
    decompose_commitment_paths,
)


def service_arc_id(
    instance: ExperimentInstance,
    service_id: str,
) -> str:
    """Return one scheduled service arc identifier."""
    return str(next(arc.arc_id for arc in instance.arcs if arc.service_id == service_id))


def build_switch_event():
    """Build the controlled prior state and current request."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    old = Demand(
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
    current = Demand(
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
        demands=(old, current),
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
    old_delivery = str(
        next(sink_arc.arc_id for sink_arc in old_network.sink_arcs if sink_arc.tail == ("C", 2))
    )

    state = RollingBookingState.empty(instance)
    state = state.advance(
        instance,
        event=timeline.event_at_sequence(1),
        commitment=DemandCommitment(
            decision_sequence=1,
            decision_time=0,
            demand=old,
            acceptance_fraction=1.0,
            planned_arc_flows=(
                PlannedArcFlow(prefix, 4.0),
                PlannedArcFlow(bottleneck, 4.0),
                PlannedArcFlow(old_delivery, 4.0),
            ),
        ),
    )

    event = timeline.event_at_sequence(2)

    return {
        "instance": instance,
        "state": state,
        "event": event,
        "prefix": prefix,
        "bottleneck": bottleneck,
        "alt1": alt1,
        "alt2": alt2,
    }


def commitment_for(state, demand_id: str):
    """Return one accepted commitment."""
    return next(commitment for commitment in state.commitments if commitment.demand_id == demand_id)


def test_event_pipeline_improves_current_acceptance() -> None:
    """Full-Reroute must accept what ordinary DCA rejects."""
    example = build_switch_event()

    result = run_full_reroute_event(
        example["instance"],
        example["state"],
        example["event"],
    )

    assert result.ordinary_acceptance_fraction == (pytest.approx(0.0))
    assert result.reroute_acceptance_fraction == (pytest.approx(1.0))
    assert result.current_was_accepted
    assert result.event_was_processed


def test_event_pipeline_preserves_all_intermediate_state() -> None:
    """The result must retain execution and capacity diagnostics."""
    example = build_switch_event()

    result = run_full_reroute_event(
        example["instance"],
        example["state"],
        example["event"],
    )

    assert result.execution_before.physical_time == 1
    assert result.execution_after.physical_time == 1

    assert result.rerouted_demand_ids == ("KOLD",)
    assert result.released_arc_ids == (example["bottleneck"],)

    assert result.state_before.processed_event_count == 1
    assert result.state_after.processed_event_count == 2


def test_event_pipeline_persists_old_and_new_routes() -> None:
    """The final state must contain both reconstructed routes."""
    example = build_switch_event()

    result = run_full_reroute_event(
        example["instance"],
        example["state"],
        example["event"],
    )

    old_commitment = commitment_for(
        result.state_after,
        "KOLD",
    )
    new_commitment = commitment_for(
        result.state_after,
        "KNEW",
    )

    old_path = decompose_commitment_paths(
        example["instance"],
        old_commitment,
    )[0]
    new_path = decompose_commitment_paths(
        example["instance"],
        new_commitment,
    )[0]

    assert old_path.physical_arc_ids == (
        example["prefix"],
        example["alt1"],
        example["alt2"],
    )
    assert new_path.physical_arc_ids == (example["bottleneck"],)


def test_event_without_prior_commitments_matches_ordinary_dca() -> None:
    """The first Full-Reroute event reduces to ordinary booking."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))
    demand = Demand(
        demand_id="KONE",
        volume=4,
        origin="B",
        destination="C",
        reservation_time=0,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.FULLY_SPOT,
        fare_per_teu=100,
    )
    instance = assemble_experiment_instance(
        config,
        demands=(demand,),
    )
    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    result = run_full_reroute_event(
        instance,
        state,
        timeline.event_at_sequence(1),
    )

    assert result.ordinary_acceptance_fraction == (pytest.approx(1.0))
    assert result.reroute_acceptance_fraction == (pytest.approx(1.0))
    assert result.rerouted_demand_ids == ()
    assert result.state_after.accepted_demand_ids == ("KONE",)


def test_event_orchestration_is_deterministic() -> None:
    """Identical input state must produce identical event results."""
    example = build_switch_event()

    first = run_full_reroute_event(
        example["instance"],
        example["state"],
        example["event"],
    )
    second = run_full_reroute_event(
        example["instance"],
        example["state"],
        example["event"],
    )

    assert first == second
