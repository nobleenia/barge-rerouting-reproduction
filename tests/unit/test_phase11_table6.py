"""Tests for the frozen Phase-11C Table-6 contract."""

import pytest

from barge_rerouting.experiments.phase11_table6 import (
    TABLE6_NEW_WATER_FACTORS,
    TABLE6_WATER_FACTORS,
    build_table6_pr_forecast_updates,
    default_table6_experiment_spec,
)


def test_table6_matrix_is_frozen() -> None:
    spec = default_table6_experiment_spec()

    assert spec.service_families == (
        "service_family_1",
        "service_family_2",
    )

    assert spec.capacities_teu == (
        10,
        20,
        30,
        40,
    )

    assert TABLE6_WATER_FACTORS == (
        1.0,
        0.9,
        0.8,
        0.7,
    )

    assert TABLE6_NEW_WATER_FACTORS == (
        0.9,
        0.8,
        0.7,
    )

    assert spec.policy_key == "pr"

    assert len(spec.service_families) * len(spec.capacities_teu) * len(spec.water_factors) == 32

    assert len(spec.service_families) * len(spec.capacities_teu) * len(spec.new_water_factors) == 24


@pytest.mark.parametrize(
    "water_factor",
    (
        1.0,
        0.9,
        0.8,
        0.7,
    ),
)
def test_table6_updates_cover_full_horizon(
    water_factor: float,
) -> None:
    updates = build_table6_pr_forecast_updates(water_factor)

    assert len(updates) == 20

    assert tuple(update.update_time for update in updates) == tuple(
        range(
            0,
            80,
            4,
        )
    )

    assert updates[0].valid_from == 0
    assert updates[0].valid_until == 4

    assert updates[-1].valid_from == 76
    assert updates[-1].valid_until == 99

    assert all(update.water_level_factor == pytest.approx(water_factor) for update in updates)

    assert all(update.affected_service_ids == () for update in updates)


def test_table6_rejects_foreign_water_factor() -> None:
    with pytest.raises(
        ValueError,
        match="must be one of",
    ):
        build_table6_pr_forecast_updates(0.85)
