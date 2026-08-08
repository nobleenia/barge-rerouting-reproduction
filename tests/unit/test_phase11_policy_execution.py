"""Regression tests for Phase 11 policy execution."""

from barge_rerouting.experiments.phase11_execution import (
    Phase11EventDisposition,
)
from barge_rerouting.experiments.phase11_pilot import (
    build_table4_pilot_inputs,
)
from barge_rerouting.experiments.phase11_policy_execution import (
    run_phase11_dca,
    run_phase11_dca_r,
)


def test_dca_continues_after_k0045_a036_rejection() -> None:
    inputs = build_table4_pilot_inputs()

    run = run_phase11_dca(
        inputs.instance,
        timeline=inputs.timeline,
    )

    failed_regular = run.result_for_demand("K0045")

    assert failed_regular.event.sequence_number == 28
    assert failed_regular.disposition is Phase11EventDisposition.FEASIBILITY_REJECTED
    assert failed_regular.acceptance_fraction == 0.0
    assert failed_regular.realised_revenue == 0.0

    following = run.event_results[28]

    assert following.event.sequence_number == 29
    assert following.disposition is not Phase11EventDisposition.SOLVER_FAILURE

    assert run.completed
    assert run.final_state.processed_event_count == inputs.timeline.event_count


def test_full_reroute_continues_after_k0097_a036_rejection() -> None:
    inputs = build_table4_pilot_inputs()

    run = run_phase11_dca_r(
        inputs.instance,
        timeline=inputs.timeline,
    )

    failed_regular = run.result_for_demand("K0097")

    assert failed_regular.event.sequence_number == 57
    assert failed_regular.disposition is Phase11EventDisposition.FEASIBILITY_REJECTED
    assert failed_regular.acceptance_fraction == 0.0
    assert failed_regular.realised_revenue == 0.0

    following = run.event_results[57]

    assert following.event.sequence_number == 58
    assert following.disposition is not Phase11EventDisposition.SOLVER_FAILURE

    assert run.completed
    assert run.final_state.processed_event_count == inputs.timeline.event_count
