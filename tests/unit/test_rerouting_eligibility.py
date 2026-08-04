"""Tests for deterministic Full-Reroute eligibility detection."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import CustomerCategory, Demand
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    ReroutingExclusionReason,
    detect_reroutable_demands,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)


def quiet_config():
    """Load the canonical toy configuration without solver logs."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def build_eligibility_example():
    """Build two accepted past demands and one current request."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                2,
                "A",
                "B",
                0,
                0,
                1,
                CustomerCategory.REGULAR,
                20,
            ),
            Demand(
                "K003",
                1,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.REGULAR,
                30,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    for sequence_number in (1, 2):
        event = timeline.event_at_sequence(sequence_number)
        artifacts = build_sequential_booking_model(
            instance,
            state,
            event,
        )
        solution = solve_sequential_booking_model(artifacts)

        assert solution.is_solved

        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )

    current_event = timeline.event_at_sequence(3)
    execution_snapshot = build_execution_snapshot(
        instance,
        state,
        physical_time=current_event.decision_time,
    )

    return instance, timeline, state, current_event, execution_snapshot


def service_ids_for(instance, arc_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Return scheduled-service IDs for selected transport arcs."""
    return tuple(str(instance.arc_by_id(arc_id).service_id) for arc_id in arc_ids)


def test_detects_only_accepted_unfinished_demand() -> None:
    """A delivered demand is excluded while unfinished cargo is selected."""
    (
        instance,
        _,
        state,
        current_event,
        execution_snapshot,
    ) = build_eligibility_example()

    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )

    assert eligibility.reroutable_demand_ids == ("K001",)
    assert eligibility.excluded_demand_ids == ("K002",)
    assert eligibility.reroutable_fragment_count == 1

    exclusion = eligibility.exclusions[0]

    assert exclusion.reason is ReroutingExclusionReason.FULLY_DELIVERED


def test_fragment_starts_from_actual_time_one_position() -> None:
    """The unfinished fragment must not restart from its original source."""
    (
        instance,
        _,
        state,
        current_event,
        execution_snapshot,
    ) = build_eligibility_example()

    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )
    demand_state = eligibility.demand_state_for("K001")
    fragment_state = demand_state.fragments[0]

    assert fragment_state.current_node == ("B", 1)
    assert service_ids_for(
        instance,
        fragment_state.executed_arc_ids,
    ) == ("S1",)
    assert service_ids_for(
        instance,
        fragment_state.old_unexecuted_transport_arc_ids,
    ) == ("S2",)

    assert demand_state.accepted_volume == pytest.approx(4.0)
    assert demand_state.remaining_volume == pytest.approx(4.0)
    assert demand_state.delivered_volume == pytest.approx(0.0)


def test_equal_time_event_does_not_execute_old_route() -> None:
    """A prior same-time commitment is reroutable from its origin."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.REGULAR,
                10,
            ),
            Demand(
                "K002",
                1,
                "B",
                "C",
                0,
                1,
                2,
                CustomerCategory.REGULAR,
                20,
            ),
        ),
    )

    timeline = build_booking_timeline(instance)
    state = RollingBookingState.empty(instance)

    first_event = timeline.event_at_sequence(1)
    artifacts = build_sequential_booking_model(
        instance,
        state,
        first_event,
    )
    solution = solve_sequential_booking_model(artifacts)

    assert solution.is_solved

    state = apply_sequential_booking_solution(
        artifacts,
        solution,
    )

    current_event = timeline.event_at_sequence(2)
    execution_snapshot = build_execution_snapshot(
        instance,
        state,
        physical_time=0,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )

    fragment_state = eligibility.demand_state_for("K001").fragments[0]

    assert fragment_state.current_node == ("A", 0)
    assert fragment_state.executed_arc_ids == ()
    assert service_ids_for(
        instance,
        fragment_state.old_unexecuted_transport_arc_ids,
    ) == ("S1", "S2")


def test_current_event_must_be_next_unprocessed_event() -> None:
    """Eligibility cannot be constructed for an already processed event."""
    (
        instance,
        timeline,
        state,
        _,
        execution_snapshot,
    ) = build_eligibility_example()

    with pytest.raises(
        ValueError,
        match="next unprocessed event",
    ):
        detect_reroutable_demands(
            instance,
            state,
            execution_snapshot,
            timeline.event_at_sequence(2),
        )


def test_detection_is_deterministic() -> None:
    """Repeated construction must produce identical eligibility state."""
    (
        instance,
        _,
        state,
        current_event,
        execution_snapshot,
    ) = build_eligibility_example()

    first = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )
    second = detect_reroutable_demands(
        instance,
        state,
        execution_snapshot,
        current_event,
    )

    assert first == second
