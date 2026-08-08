"""Tests for Phase 11 experiment-layer execution semantics."""

import pytest

from barge_rerouting.experiments.phase11_execution import (
    advance_regular_feasibility_rejection,
    is_proven_infeasible_status,
)
from barge_rerouting.experiments.phase11_pilot import (
    build_table4_pilot_inputs,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


@pytest.mark.parametrize(
    "status",
    (
        "infeasible",
        "Infeasible",
        "integer infeasible",
        "HiGHS 1.15.1 Infeasible",
    ),
)
def test_explicit_infeasibility_is_recognised(
    status: str,
) -> None:
    assert is_proven_infeasible_status(status)


@pytest.mark.parametrize(
    "status",
    (
        "time limit",
        "unknown",
        "unbounded",
        "infeasible or unbounded",
        "HiGHS 1.15.1 Time limit",
    ),
)
def test_noncertified_status_is_not_infeasibility(
    status: str,
) -> None:
    assert not is_proven_infeasible_status(status)


def test_regular_feasibility_rejection_advances_without_commitment() -> None:
    inputs = build_table4_pilot_inputs()

    event = next(event for event in inputs.timeline.events if event.demand.category.value == "R")

    # A fresh state expects sequence 1, so construct the
    # state immediately preceding the selected Regular event
    # using zero-commitment records for earlier events.
    state = RollingBookingState.empty(inputs.instance)

    for earlier_event in inputs.timeline.events:
        if earlier_event.sequence_number >= event.sequence_number:
            break

        state = state.advance(
            inputs.instance,
            event=earlier_event,
            commitment=None,
        )

    before_count = state.processed_event_count
    before_commitments = state.commitments

    after = advance_regular_feasibility_rejection(
        inputs.instance,
        state,
        event,
        solve_status="infeasible",
    )

    assert after.processed_event_count == before_count + 1
    assert after.commitments == before_commitments
    assert after.records[-1].event == event
    assert after.records[-1].commitment is None


def test_a036_rejects_nonregular_use() -> None:
    inputs = build_table4_pilot_inputs()

    event = next(event for event in inputs.timeline.events if event.demand.category.value != "R")

    state = RollingBookingState.empty(inputs.instance)

    for earlier_event in inputs.timeline.events:
        if earlier_event.sequence_number >= event.sequence_number:
            break

        state = state.advance(
            inputs.instance,
            event=earlier_event,
            commitment=None,
        )

    with pytest.raises(
        ValueError,
        match="only to Regular",
    ):
        advance_regular_feasibility_rejection(
            inputs.instance,
            state,
            event,
            solve_status="infeasible",
        )


def test_a036_rejects_ambiguous_solver_failure() -> None:
    inputs = build_table4_pilot_inputs()

    event = next(event for event in inputs.timeline.events if event.demand.category.value == "R")

    state = RollingBookingState.empty(inputs.instance)

    for earlier_event in inputs.timeline.events:
        if earlier_event.sequence_number >= event.sequence_number:
            break

        state = state.advance(
            inputs.instance,
            event=earlier_event,
            commitment=None,
        )

    with pytest.raises(
        ValueError,
        match="explicitly certifies",
    ):
        advance_regular_feasibility_rejection(
            inputs.instance,
            state,
            event,
            solve_status="time limit",
        )
