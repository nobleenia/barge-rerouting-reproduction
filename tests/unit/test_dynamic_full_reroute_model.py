"""Tests for truck-enabled dynamic Full-Reroute booking."""

import pytest
from test_dynamic_booking_capacity import (
    build_status_then_booking_example,
)

from barge_rerouting.disruption import (
    build_dynamic_full_reroute_model,
    solve_dynamic_full_reroute_model,
    validate_dynamic_full_reroute_solution,
)
from barge_rerouting.disruption.recovery_capacity import (
    RecoveryCapacitySnapshot,
)
from barge_rerouting.rerouting.network import (
    FragmentNetworkSnapshot,
)


def build_dynamic_fr_example():
    """Build a booking solve that can displace prior cargo."""
    example = build_status_then_booking_example()

    recovery_artifacts = example["recovery_artifacts"]
    booking_event = example["current_event"]

    # F3 tests the optimisation layer. F4 will construct
    # these booking-triggered snapshots directly.
    recovery_capacity = RecoveryCapacitySnapshot(
        event_id=booking_event.event_id,
        physical_time=booking_event.decision_time,
        instance_fingerprint=(recovery_artifacts.recovery_capacity.instance_fingerprint),
        arc_states=(recovery_artifacts.recovery_capacity.arc_states),
    )

    fragment_networks = FragmentNetworkSnapshot(
        current_event_id=booking_event.event_id,
        physical_time=booking_event.decision_time,
        instance_fingerprint=(recovery_artifacts.fragment_networks.instance_fingerprint),
        indexes=(recovery_artifacts.fragment_networks.indexes),
    )

    # Use contractual state before the status-only transition:
    # K1 remains the prior 10-TEU accepted commodity.
    booking_state = example["transition"].state_before.booking_state

    artifacts = build_dynamic_full_reroute_model(
        example["instance"],
        booking_state,
        booking_event,
        recovery_capacity,
        fragment_networks,
        truck_penalty_per_teu_by_demand={
            # Moving K1 to truck is relatively cheap.
            "K1": 25.0,
            # Directly trucking new K2 is deliberately
            # unattractive in this controlled test.
            "K2": 1000.0,
        },
    )

    solution = solve_dynamic_full_reroute_model(artifacts)

    return example, artifacts, solution


def test_dynamic_fr_accepts_current_by_displacing_prior_volume() -> None:
    """FR may truck extra prior cargo to admit a valuable request."""
    example, artifacts, solution = build_dynamic_fr_example()

    try:
        assert solution.is_solved
        assert solution.acceptance_fraction == pytest.approx(1.0)

        # Reduced barge capacity is seven TEU.
        #
        # K1 originally requires at least three truck TEU.
        # Accepting K2 uses one barge TEU, so K1 moves
        # four TEU to truck and keeps six on barge.
        assert solution.prior_truck_volume == pytest.approx(4.0)
        assert solution.current_truck_volume == pytest.approx(0.0)

        assert solution.total_truck_volume == pytest.approx(4.0)

        # K2 revenue = 100.
        # K1 truck penalty = 4 * 25 = 100.
        assert solution.objective_value == pytest.approx(0.0)
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_dynamic_fr_improves_over_status_only_recovery() -> None:
    """The incoming request causes one additional prior truck TEU."""
    example, artifacts, solution = build_dynamic_fr_example()

    try:
        status_only = example["transition"].state_after.total_truck_volume

        assert status_only == pytest.approx(3.0)
        assert solution.prior_truck_volume == pytest.approx(4.0)

        assert solution.prior_truck_volume - status_only == pytest.approx(1.0)
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_dynamic_fr_respects_actual_capacity() -> None:
    """Current and rerouted barge flows share reduced capacity."""
    example, artifacts, solution = build_dynamic_fr_example()

    try:
        assert solution.is_solved

        for arc_id, available in artifacts.available_capacities.items():
            used = 0.0

            if arc_id in artifacts.current_network_index.feasible_arc_ids:
                used += solution.current_flow_on(arc_id)

            for index in artifacts.fragment_networks.indexes:
                if arc_id in index.feasible_arc_ids:
                    used += solution.fragment_flow_on(
                        index.fragment_id,
                        arc_id,
                    )

            assert used - available <= 1e-6
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_dynamic_fr_independent_validator_passes() -> None:
    """Extracted FR solution must satisfy all reconstructed identities."""
    example, artifacts, solution = build_dynamic_fr_example()

    try:
        report = validate_dynamic_full_reroute_solution(
            artifacts,
            solution,
        )

        assert report.is_valid
        assert report.violations == ()
        assert report.max_flow_balance_violation <= 1e-6
        assert report.max_delivery_balance_violation <= 1e-6
        assert report.max_capacity_violation <= 1e-6
        assert report.objective_violation <= 1e-6
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()


def test_dynamic_fr_requires_explicit_penalties() -> None:
    """Missing current or prior truck cost must never be guessed."""
    example = build_status_then_booking_example()

    try:
        recovery_artifacts = example["recovery_artifacts"]
        event = example["current_event"]

        capacity = RecoveryCapacitySnapshot(
            event_id=event.event_id,
            physical_time=event.decision_time,
            instance_fingerprint=(recovery_artifacts.recovery_capacity.instance_fingerprint),
            arc_states=(recovery_artifacts.recovery_capacity.arc_states),
        )

        networks = FragmentNetworkSnapshot(
            current_event_id=event.event_id,
            physical_time=event.decision_time,
            instance_fingerprint=(recovery_artifacts.fragment_networks.instance_fingerprint),
            indexes=(recovery_artifacts.fragment_networks.indexes),
        )

        with pytest.raises(
            ValueError,
            match="cover exactly",
        ):
            build_dynamic_full_reroute_model(
                example["instance"],
                example["transition"].state_before.booking_state,
                event,
                capacity,
                networks,
                truck_penalty_per_teu_by_demand={
                    "K1": 25.0,
                },
            )
    finally:
        example["recovery_artifacts"].model.end()


def test_highs_matches_cplex_dynamic_full_reroute_solution() -> None:
    """HiGHS must reproduce the validated CPLEX dynamic-FR optimum."""
    from barge_rerouting.disruption.dynamic_full_reroute import (
        validate_dynamic_full_reroute_solution,
    )
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
        solve_dynamic_full_reroute_with_backend,
    )

    (
        example,
        artifacts,
        cplex_solution,
    ) = build_dynamic_fr_example()

    try:
        highs_solution = solve_dynamic_full_reroute_with_backend(
            artifacts,
            backend=SolverBackend.HIGHS,
        )

        assert cplex_solution.is_solved
        assert highs_solution.is_solved

        assert highs_solution.objective_value == pytest.approx(cplex_solution.objective_value)

        assert highs_solution.acceptance_fraction == pytest.approx(
            cplex_solution.acceptance_fraction
        )

        assert highs_solution.total_truck_volume == pytest.approx(cplex_solution.total_truck_volume)

        assert highs_solution.total_truck_penalty == pytest.approx(
            cplex_solution.total_truck_penalty
        )

        cplex_report = validate_dynamic_full_reroute_solution(
            artifacts,
            cplex_solution,
        )

        highs_report = validate_dynamic_full_reroute_solution(
            artifacts,
            highs_solution,
        )

        assert cplex_report.is_valid
        assert highs_report.is_valid
    finally:
        artifacts.model.end()
        example["recovery_artifacts"].model.end()
