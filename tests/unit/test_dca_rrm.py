"""Reduction and composition tests for DCA-RRM."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.optimization.dca_rm import (
    build_dca_rm_model,
    solve_dca_rm_model,
)
from barge_rerouting.optimization.dca_rrm import (
    build_dca_rrm_model,
    solve_dca_rrm_model,
)
from barge_rerouting.rerouting.capacity import (
    build_rerouting_capacity_snapshot,
)
from barge_rerouting.rerouting.eligibility import (
    detect_reroutable_demands,
)
from barge_rerouting.rerouting.in_transit import (
    build_rerouting_decision_snapshot,
)
from barge_rerouting.rerouting.network import (
    build_fragment_network_snapshot,
)
from barge_rerouting.rerouting.optimization import (
    build_dca_reroute_model,
    solve_dca_reroute_model,
)
from barge_rerouting.revenue_management.future_set import (
    select_explicit_future_set,
)
from barge_rerouting.rolling_horizon import (
    RollingBookingState,
    apply_sequential_booking_solution,
    build_booking_timeline,
    build_execution_snapshot,
    build_sequential_booking_model,
    build_transport_capacity_snapshot,
    solve_sequential_booking_model,
)


def quiet_config():
    """Load the controlled rerouting network quietly."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    return replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )


def current_only_instance():
    """Build one current partially-spot request."""
    return assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "CURRENT",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                10,
            ),
        ),
    )


def rerouting_inputs(
    instance,
    state,
    event,
):
    """Build ordinary, released, and fragment snapshots."""
    execution = build_execution_snapshot(
        instance,
        state,
        physical_time=event.decision_time,
    )
    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution,
    )
    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution,
        event,
    )
    decision_snapshot = build_rerouting_decision_snapshot(
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
        decision_snapshot,
        rerouting_capacity,
    )

    return (
        ordinary_capacity,
        rerouting_capacity,
        fragment_networks,
    )


def high_value_forecast():
    """Return one high-value future request forecast."""
    return FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=(CustomerCategory.PARTIALLY_SPOT),
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(0, 0.50),
            VolumeProbability(4, 0.50),
        ),
    )


def state_with_prior_commitment():
    """Build a state with one accepted unfinished demand."""
    instance = assemble_experiment_instance(
        quiet_config(),
        demands=(
            Demand(
                "K001",
                1,
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
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
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

    try:
        solution = solve_sequential_booking_model(artifacts)
        state = apply_sequential_booking_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    return (
        instance,
        state,
        timeline.event_at_sequence(2),
    )


def test_empty_past_and_future_reduce_to_dca() -> None:
    """DCA-RRM must equal sequential DCA when both sets are empty."""
    instance = current_only_instance()
    timeline = build_booking_timeline(instance)
    event = timeline.event_at_sequence(1)
    state = RollingBookingState.empty(instance)

    (
        ordinary_capacity,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (),
    )

    dca_artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
        capacity_snapshot=ordinary_capacity,
    )
    rrm_artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        dca_solution = solve_sequential_booking_model(dca_artifacts)
        rrm_solution = solve_dca_rrm_model(rrm_artifacts)
    finally:
        dca_artifacts.model.end()
        rrm_artifacts.model.end()

    assert rrm_artifacts.fragment_count == 0
    assert rrm_artifacts.forecast_count == 0

    assert rrm_solution.is_solved
    assert rrm_solution.acceptance_fraction == (pytest.approx(dca_solution.acceptance_fraction))
    assert rrm_solution.objective_value == pytest.approx(dca_solution.objective_value)
    assert rrm_solution.current_revenue == (pytest.approx(dca_solution.objective_value))
    assert rrm_solution.future_expected_revenue == (pytest.approx(0.0))


def test_no_past_fragments_reduce_to_dca_rm() -> None:
    """DCA-RRM must equal DCA-RM without unfinished past demand."""
    instance = current_only_instance()
    timeline = build_booking_timeline(instance)
    event = timeline.event_at_sequence(1)
    state = RollingBookingState.empty(instance)

    (
        ordinary_capacity,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (high_value_forecast(),),
    )

    rm_artifacts = build_dca_rm_model(
        instance,
        state,
        event,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
        capacity_snapshot=ordinary_capacity,
    )
    rrm_artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        rm_solution = solve_dca_rm_model(rm_artifacts)
        rrm_solution = solve_dca_rrm_model(rrm_artifacts)
    finally:
        rm_artifacts.model.end()
        rrm_artifacts.model.end()

    assert rrm_artifacts.fragment_count == 0
    assert rrm_artifacts.forecast_count == 1

    assert rrm_solution.acceptance_fraction == (pytest.approx(rm_solution.acceptance_fraction))
    assert rrm_solution.objective_value == pytest.approx(rm_solution.objective_value)
    assert rrm_solution.current_revenue == pytest.approx(rm_solution.current_revenue)
    assert rrm_solution.future_expected_revenue == pytest.approx(
        rm_solution.future_expected_revenue
    )

    assert rrm_solution.protection_for("FUTURE").protected_volume == pytest.approx(
        rm_solution.protection_for("FUTURE").protected_volume
    )


def test_empty_future_set_reduces_to_dca_reroute() -> None:
    """DCA-RRM must equal DCA-R when K(current) is empty."""
    (
        instance,
        state,
        event,
    ) = state_with_prior_commitment()

    (
        _,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    assert fragment_networks.indexes

    future_set = select_explicit_future_set(
        instance,
        event,
        (),
    )

    reroute_artifacts = build_dca_reroute_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
    )
    rrm_artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        reroute_solution = solve_dca_reroute_model(reroute_artifacts)
        rrm_solution = solve_dca_rrm_model(rrm_artifacts)
    finally:
        reroute_artifacts.model.end()
        rrm_artifacts.model.end()

    assert rrm_artifacts.fragment_count > 0
    assert rrm_artifacts.forecast_count == 0

    assert rrm_solution.acceptance_fraction == (pytest.approx(reroute_solution.acceptance_fraction))
    assert rrm_solution.objective_value == pytest.approx(reroute_solution.objective_value)
    assert rrm_solution.current_revenue == pytest.approx(reroute_solution.objective_value)
    assert rrm_solution.future_expected_revenue == (pytest.approx(0.0))

    for index in fragment_networks.indexes:
        assert rrm_solution.fragment_delivered_volume(index) == pytest.approx(index.volume)


def test_combined_model_contains_all_three_commodity_groups() -> None:
    """Past, current, and future flows must coexist."""
    (
        instance,
        state,
        event,
    ) = state_with_prior_commitment()

    (
        _,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (high_value_forecast(),),
    )

    artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        solution = solve_dca_rrm_model(artifacts)
    finally:
        artifacts.model.end()

    assert artifacts.current_flow_variable_count > 0
    assert artifacts.fragment_flow_variable_count > 0
    assert artifacts.future_flow_variable_count > 0
    assert artifacts.selector_variable_count > 0
    assert artifacts.combined_capacity_constraints

    assert solution.is_solved
    assert solution.current_revenue is not None
    assert solution.future_expected_revenue is not None
    assert solution.objective_value == pytest.approx(
        solution.current_revenue + solution.future_expected_revenue
    )

    for index in fragment_networks.indexes:
        assert solution.fragment_delivered_volume(index) == pytest.approx(index.volume)


def build_solved_combined_model():
    """Build and solve one past-current-future model."""
    (
        instance,
        state,
        event,
    ) = state_with_prior_commitment()

    (
        _,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (high_value_forecast(),),
    )

    artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )
    solution = solve_dca_rrm_model(artifacts)

    return artifacts, solution


def test_combined_solution_passes_independent_validation() -> None:
    """A genuine solver result must satisfy every equation."""
    from barge_rerouting.optimization.dca_rrm import (
        validate_dca_rrm_solution,
    )

    artifacts, solution = build_solved_combined_model()

    try:
        report = validate_dca_rrm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert report.is_valid
    assert report.violations == ()
    assert report.objective_violation == pytest.approx(0.0)
    assert report.max_capacity_violation == pytest.approx(0.0)
    assert report.max_fragment_flow_balance_violation == pytest.approx(0.0)
    assert report.max_future_flow_balance_violation == pytest.approx(0.0)


def test_validator_detects_altered_objective() -> None:
    """The validator must independently recompute value."""
    from dataclasses import replace

    from barge_rerouting.optimization.dca_rrm import (
        validate_dca_rrm_solution,
    )

    artifacts, solution = build_solved_combined_model()

    assert solution.objective_value is not None

    altered = replace(
        solution,
        objective_value=(solution.objective_value + 1.0),
    )

    try:
        report = validate_dca_rrm_solution(
            artifacts,
            altered,
        )
    finally:
        artifacts.model.end()

    assert not report.is_valid
    assert report.objective_violation == pytest.approx(1.0)
    assert "Reported DCA-RRM objective is incorrect." in report.violations


def test_validator_detects_nonbinary_selector() -> None:
    """The validator must reject fractional y(k,j)."""
    from dataclasses import replace

    from barge_rerouting.optimization.dca_rrm import (
        validate_dca_rrm_solution,
    )

    artifacts, solution = build_solved_combined_model()

    assert solution.selectors

    altered_selectors = (
        replace(
            solution.selectors[0],
            selected_value=0.5,
        ),
        *solution.selectors[1:],
    )
    altered = replace(
        solution,
        selectors=altered_selectors,
    )

    try:
        report = validate_dca_rrm_solution(
            artifacts,
            altered,
        )
    finally:
        artifacts.model.end()

    assert not report.is_valid
    assert report.max_selector_binary_violation == pytest.approx(0.5)
    assert "At least one future selector is non-binary." in report.violations


def test_rrm_transition_persists_only_realised_commodities() -> None:
    """Future protection must not become a stored commitment."""
    from barge_rerouting.revenue_management.rrm_transition import (
        apply_dca_rrm_solution,
    )
    from barge_rerouting.rolling_horizon.commitment import (
        validate_commitment_against_instance,
    )

    artifacts, solution = build_solved_combined_model()

    try:
        transition = apply_dca_rrm_solution(
            artifacts,
            solution,
        )
    finally:
        artifacts.model.end()

    assert (
        transition.state_after.processed_event_count
        == transition.state_before.processed_event_count + 1
    )

    assert transition.discarded_forecast_ids == ("FUTURE",)
    assert transition.discarded_protected_volume >= 0.0
    assert transition.discarded_expected_future_revenue == pytest.approx(
        solution.future_expected_revenue
    )

    assert "FUTURE" not in (transition.state_after.accepted_demand_ids)

    assert transition.state_after.records[-1].event == artifacts.event

    for commitment in transition.state_after.commitments:
        report = validate_commitment_against_instance(
            artifacts.instance,
            commitment,
        )

        assert report.is_valid


def test_empty_future_transition_reduces_to_dca_reroute() -> None:
    """Without forecasts, DCA-RRM persistence must equal DCA-R."""
    from barge_rerouting.rerouting.transition import (
        apply_dca_reroute_solution,
    )
    from barge_rerouting.revenue_management.rrm_transition import (
        apply_dca_rrm_solution,
    )

    (
        instance,
        state,
        event,
    ) = state_with_prior_commitment()

    (
        _,
        rerouting_capacity,
        fragment_networks,
    ) = rerouting_inputs(
        instance,
        state,
        event,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (),
    )

    reroute_artifacts = build_dca_reroute_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
    )
    rrm_artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=(FutureValueInterpretation.PRINTED),
    )

    try:
        reroute_solution = solve_dca_reroute_model(reroute_artifacts)
        rrm_solution = solve_dca_rrm_model(rrm_artifacts)

        reroute_transition = apply_dca_reroute_solution(
            reroute_artifacts,
            reroute_solution,
        )
        rrm_transition = apply_dca_rrm_solution(
            rrm_artifacts,
            rrm_solution,
        )
    finally:
        reroute_artifacts.model.end()
        rrm_artifacts.model.end()

    assert rrm_transition.discarded_forecast_ids == ()
    assert rrm_transition.discarded_protected_volume == pytest.approx(0.0)
    assert rrm_transition.discarded_expected_future_revenue == pytest.approx(0.0)

    assert rrm_transition.state_after == reroute_transition.state_after


def test_rrm_transition_rejects_invalid_solution() -> None:
    """No invalid combined solution may update persistent state."""
    from barge_rerouting.revenue_management.rrm_transition import (
        apply_dca_rrm_solution,
    )

    artifacts, solution = build_solved_combined_model()

    assert solution.objective_value is not None

    altered = replace(
        solution,
        objective_value=(solution.objective_value + 1.0),
    )

    try:
        with pytest.raises(
            ValueError,
            match=("failed independent validation"),
        ):
            apply_dca_rrm_solution(
                artifacts,
                altered,
            )
    finally:
        artifacts.model.end()


def test_highs_combined_solution_matches_cplex_and_validates() -> None:
    """HiGHS must solve genuine past-current-future DCA-RRM."""
    from barge_rerouting.optimization.dca_rrm import (
        validate_dca_rrm_solution,
    )
    from barge_rerouting.optimization.highs_bridge import (
        solve_dca_rrm_model_highs,
    )

    artifacts, cplex_solution = build_solved_combined_model()

    try:
        highs_solution = solve_dca_rrm_model_highs(artifacts)

        highs_report = validate_dca_rrm_solution(
            artifacts,
            highs_solution,
        )
    finally:
        artifacts.model.end()

    assert artifacts.fragment_count > 0
    assert artifacts.forecast_count > 0

    assert cplex_solution.is_solved
    assert highs_solution.is_solved
    assert highs_report.is_valid

    assert highs_solution.objective_value == pytest.approx(cplex_solution.objective_value)

    assert highs_solution.acceptance_fraction == pytest.approx(cplex_solution.acceptance_fraction)

    assert highs_report.violations == ()
    assert highs_report.max_capacity_violation == pytest.approx(0.0)
    assert highs_report.max_fragment_flow_balance_violation == pytest.approx(0.0)
    assert highs_report.max_future_flow_balance_violation == pytest.approx(0.0)
