"""Tests for the Phase 11 Table 5 pilot inputs."""

import pytest

from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_CONTROLLED_HORIZON_END,
)
from barge_rerouting.experiments.phase11_table5_demands import (
    TABLE5_EXPECTED_DEMAND_FINGERPRINT,
)
from barge_rerouting.experiments.phase11_table5_pilot import (
    TABLE5_PILOT_CAPACITY_TEU,
    TABLE5_PILOT_SERVICE_FAMILY,
    TABLE5_TRUCK_PENALTY_FARE_MULTIPLIER,
    build_table5_pilot_inputs,
)


def test_table5_pilot_assembles_all_800_feasible_demands() -> None:
    inputs = build_table5_pilot_inputs()

    assert len(inputs.instance.demands) == 800

    assert len(inputs.instance.demand_network_indexes) == 800

    assert inputs.demand_fingerprint == TABLE5_EXPECTED_DEMAND_FINGERPRINT

    assert all(index.destination_nodes for index in (inputs.instance.demand_network_indexes))

    assert all(index.feasible_arc_ids for index in (inputs.instance.demand_network_indexes))


def test_table5_pilot_uses_extended_service_horizon() -> None:
    inputs = build_table5_pilot_inputs()

    assert inputs.config.network.time_periods == tuple(range(TABLE5_CONTROLLED_HORIZON_END + 1))

    assert TABLE5_CONTROLLED_HORIZON_END == 98

    assert (
        max(demand.due_time for demand in inputs.instance.demands) <= TABLE5_CONTROLLED_HORIZON_END
    )


def test_table5_pilot_policy_timeline_counts() -> None:
    inputs = build_table5_pilot_inputs()

    assert inputs.booking_timeline.event_count == 800

    assert inputs.pr_timeline.booking_event_count == 800

    assert inputs.pr_timeline.status_update_count == 20

    assert inputs.pr_timeline.event_count == 820

    assert tuple(update.update_time for update in inputs.pr_updates) == tuple(
        range(
            0,
            80,
            4,
        )
    )


def test_table5_pilot_truck_penalties_follow_a044() -> None:
    inputs = build_table5_pilot_inputs()

    assert TABLE5_TRUCK_PENALTY_FARE_MULTIPLIER == pytest.approx(1.0)

    assert len(inputs.truck_penalty_per_teu_by_demand) == 800

    for demand in inputs.instance.demands:
        assert inputs.truck_penalty_per_teu_by_demand[demand.demand_id] == pytest.approx(
            demand.fare_per_teu
        )


def test_table5_pilot_identity_is_frozen() -> None:
    inputs = build_table5_pilot_inputs()

    assert TABLE5_PILOT_SERVICE_FAMILY == "service_family_1"

    assert TABLE5_PILOT_CAPACITY_TEU == 10

    assert len(inputs.configuration_fingerprint) == 64
