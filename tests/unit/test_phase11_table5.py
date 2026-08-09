"""Tests for the frozen Phase 11 Table 5 experiment contract."""

import pytest

from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_CAPACITIES_TEU,
    TABLE5_CONTROLLED_HORIZON_END,
    TABLE5_DEMAND_COUNT,
    TABLE5_POLICY_KEYS,
    TABLE5_PR_TRIGGER_INTERVAL_PERIODS,
    TABLE5_PR_TRIGGER_TIMES,
    TABLE5_REQUEST_PERIODS,
    TABLE5_REQUESTS_PER_PERIOD,
    TABLE5_SERVICE_FAMILIES,
    TABLE5_STANDARD_WATER_FACTOR,
    build_table5_demand_process,
    build_table5_pr_forecast_updates,
    default_table5_experiment_spec,
)


def test_table5_experiment_matrix_is_frozen() -> None:
    spec = default_table5_experiment_spec()

    assert TABLE5_SERVICE_FAMILIES == (
        "service_family_1",
        "service_family_2",
    )

    assert TABLE5_CAPACITIES_TEU == (
        10,
        20,
        30,
        40,
    )

    assert TABLE5_POLICY_KEYS == (
        "dca",
        "pr",
        "fr",
    )

    assert spec.service_families == (TABLE5_SERVICE_FAMILIES)
    assert spec.capacities_teu == (TABLE5_CAPACITIES_TEU)
    assert spec.policy_keys == TABLE5_POLICY_KEYS

    assert len(spec.service_families) * len(spec.capacities_teu) * len(spec.policy_keys) == 24


def test_table5_request_process_contains_800_requests() -> None:
    process = build_table5_demand_process()

    assert TABLE5_REQUESTS_PER_PERIOD == 10
    assert TABLE5_REQUEST_PERIODS == tuple(range(80))
    assert TABLE5_DEMAND_COUNT == 800

    assert process.request_periods == tuple(range(80))
    assert process.requests_per_period == 10
    assert process.request_count == 800

    assert process.horizon_end == (TABLE5_CONTROLLED_HORIZON_END)
    assert process.horizon_end == 98


def test_table5_pr_epochs_are_every_four_periods() -> None:
    assert TABLE5_PR_TRIGGER_INTERVAL_PERIODS == 4

    assert TABLE5_PR_TRIGGER_TIMES == tuple(
        range(
            0,
            80,
            4,
        )
    )

    assert len(TABLE5_PR_TRIGGER_TIMES) == 20

    assert all(
        later - earlier == 4
        for earlier, later in zip(
            TABLE5_PR_TRIGGER_TIMES,
            TABLE5_PR_TRIGGER_TIMES[1:],
            strict=False,
        )
    )


def test_table5_pr_updates_are_capacity_neutral() -> None:
    updates = build_table5_pr_forecast_updates()

    assert len(updates) == 20

    assert tuple(update.update_time for update in updates) == TABLE5_PR_TRIGGER_TIMES

    for update in updates:
        assert update.water_level_factor == pytest.approx(TABLE5_STANDARD_WATER_FACTOR)
        assert update.water_level_factor == pytest.approx(1.0)
        assert update.affected_service_ids == ()

    assert updates[0].valid_from == 0
    assert updates[0].valid_until == 4

    assert updates[-1].valid_from == 76
    assert updates[-1].valid_until == 99


def test_table5_standard_water_is_exactly_one() -> None:
    spec = default_table5_experiment_spec()

    assert spec.water_level_factor == pytest.approx(1.0)
