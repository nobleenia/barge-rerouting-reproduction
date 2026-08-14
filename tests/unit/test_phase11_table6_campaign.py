"""Tests for Phase-11C campaign construction."""

import pytest

from barge_rerouting.experiments.phase11_table6_campaign import (
    build_default_table6_new_run_plan,
    build_table6_base_inputs,
    build_table6_campaign_run_inputs,
)


def test_table6_new_run_plan_contains_24_unique_rows() -> None:
    plan = build_default_table6_new_run_plan()

    assert len(plan) == 24
    assert len({run.run_key for run in plan}) == 24

    assert {run.water_factor for run in plan} == {
        0.9,
        0.8,
        0.7,
    }

    assert {run.policy_key for run in plan} == {"pr"}


def test_table6_run_key_contains_water_factor() -> None:
    run = build_default_table6_new_run_plan()[0]

    assert run.run_key == ("service_family_1__capacity_10__water_0p9__pr")


def test_table6_reuses_frozen_table5_demand() -> None:
    run = build_default_table6_new_run_plan()[1]

    base = build_table6_base_inputs(run)

    inputs = build_table6_campaign_run_inputs(
        run,
        base_inputs=base,
    )

    assert inputs.requested_booking_count == 800

    assert inputs.requested_volume == pytest.approx(1076.0)

    assert inputs.demand_fingerprint == (
        "9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944"
    )

    assert inputs.timeline.booking_event_count == 800
    assert inputs.timeline.status_update_count == 20

    assert all(update.water_level_factor == pytest.approx(0.8) for update in inputs.status_updates)


def test_water_factor_changes_scenario_fingerprint() -> None:
    plan = build_default_table6_new_run_plan()

    run_09 = next(
        run
        for run in plan
        if (
            run.service_family == "service_family_1"
            and run.capacity_teu == 10
            and run.water_factor == 0.9
        )
    )

    run_08 = next(
        run
        for run in plan
        if (
            run.service_family == "service_family_1"
            and run.capacity_teu == 10
            and run.water_factor == 0.8
        )
    )

    base = build_table6_base_inputs(run_09)

    inputs_09 = build_table6_campaign_run_inputs(
        run_09,
        base_inputs=base,
    )

    inputs_08 = build_table6_campaign_run_inputs(
        run_08,
        base_inputs=base,
    )

    assert inputs_09.base_configuration_fingerprint == inputs_08.base_configuration_fingerprint

    assert inputs_09.demand_fingerprint == inputs_08.demand_fingerprint

    assert inputs_09.scenario_fingerprint != inputs_08.scenario_fingerprint
