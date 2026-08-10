"""Tests for deterministic Phase-11 Table-5 campaign construction."""

import pytest

from barge_rerouting.experiments.phase11_services import (
    build_table4_network_config,
)
from barge_rerouting.experiments.phase11_table5 import (
    default_table5_experiment_spec,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    TABLE5_REPORTING_SCHEMA_VERSION,
    Table5CampaignCell,
    build_default_table5_campaign_cells,
    build_default_table5_run_plan,
    build_table5_campaign_cell_inputs,
)


def test_default_campaign_has_eight_cells_and_24_runs() -> None:
    spec = default_table5_experiment_spec()

    cells = build_default_table5_campaign_cells(spec)
    runs = build_default_table5_run_plan(spec)

    assert len(cells) == 8
    assert len(runs) == 24

    assert {cell.service_family for cell in cells} == {
        "service_family_1",
        "service_family_2",
    }

    assert {cell.capacity_teu for cell in cells} == {
        10,
        20,
        30,
        40,
    }

    assert {run.policy_key for run in runs} == {
        "dca",
        "pr",
        "fr",
    }

    assert len({run.run_key for run in runs}) == 24


def test_family1_capacity10_rebuilds_frozen_population() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    assert inputs.requested_booking_count == 800

    assert inputs.requested_volume == pytest.approx(1076.0)

    assert len(inputs.pr_updates) == 20

    assert inputs.booking_timeline.event_count == 800

    assert inputs.pr_timeline.event_count == 820

    assert inputs.reporting_schema_version == TABLE5_REPORTING_SCHEMA_VERSION


def test_family2_capacity40_uses_same_frozen_demand() -> None:
    spec = default_table5_experiment_spec()

    first = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    second = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_2",
            capacity_teu=40,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    assert first.demand_fingerprint == second.demand_fingerprint

    assert first.requested_volume == pytest.approx(second.requested_volume)

    transport_edges = [
        data
        for _, _, _, data in (
            second.instance.graph.edges(
                keys=True,
                data=True,
            )
        )
        if data.get("capacity") is not None
    ]

    assert transport_edges

    assert {float(data["capacity"]) for data in transport_edges} == {40.0}

    assert all("service_family_2" in str(data["service_id"]) for data in transport_edges)


def test_configuration_fingerprint_changes_with_cell() -> None:
    spec = default_table5_experiment_spec()

    first = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    second = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family="service_family_1",
            capacity_teu=20,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    assert first.configuration_fingerprint != second.configuration_fingerprint

    assert first.demand_fingerprint == second.demand_fingerprint


def test_foreign_campaign_cell_is_rejected() -> None:
    spec = default_table5_experiment_spec()

    with pytest.raises(
        ValueError,
        match="Unknown Table-5 capacity",
    ):
        build_table5_campaign_cell_inputs(
            Table5CampaignCell(
                service_family="service_family_1",
                capacity_teu=999,
                reproduction_class=(spec.reproduction_class),
            ),
            spec=spec,
        )


def test_table4_capacity_domain_remains_frozen() -> None:
    with pytest.raises(
        ValueError,
        match="Table 4 capacity must be one of",
    ):
        build_table4_network_config(
            time_periods=tuple(range(99)),
            service_family="service_family_1",
            capacity_teu=40,
        )
