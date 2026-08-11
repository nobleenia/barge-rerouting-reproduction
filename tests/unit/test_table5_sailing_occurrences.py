"""Tests for Table-5 physical sailing reconstruction."""

from barge_rerouting.experiments.phase11_table5 import (
    default_table5_experiment_spec,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCell,
    build_table5_campaign_cell_inputs,
)
from barge_rerouting.reporting.table5_sailing_occurrences import (
    build_table5_sailing_occurrences,
)
from barge_rerouting.reporting.table5_service_capacity import (
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
    build_table5_service_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def _arc(
    *,
    index: int,
    departure: int,
    origin: str,
    destination: str,
) -> Table5TransportArcEvidence:
    return Table5TransportArcEvidence(
        arc_id=f"transport::{index}",
        service_id="service::slot01",
        origin=origin,
        destination=destination,
        departure_time=departure,
        arrival_time=departure + 1,
        nominal_capacity=10.0,
        actual_capacity=10.0,
        original_load=2.0,
        final_load=2.0,
    )


def test_two_repeated_services_become_two_occurrences() -> None:
    snapshot = Table5ServiceCapacitySnapshot(
        reporting_time=20,
        instance_fingerprint="a" * 64,
        arcs=(
            _arc(
                index=1,
                departure=0,
                origin="A",
                destination="B",
            ),
            _arc(
                index=2,
                departure=1,
                origin="B",
                destination="C",
            ),
            _arc(
                index=3,
                departure=2,
                origin="C",
                destination="D",
            ),
            _arc(
                index=4,
                departure=3,
                origin="D",
                destination="E",
            ),
            _arc(
                index=5,
                departure=10,
                origin="A",
                destination="B",
            ),
            _arc(
                index=6,
                departure=11,
                origin="B",
                destination="C",
            ),
            _arc(
                index=7,
                departure=12,
                origin="C",
                destination="D",
            ),
            _arc(
                index=8,
                departure=13,
                origin="D",
                destination="E",
            ),
        ),
    )

    occurrences = build_table5_sailing_occurrences(snapshot)

    assert len(occurrences) == 2

    assert [occurrence.departure_time for occurrence in occurrences] == [
        0,
        10,
    ]

    assert all(occurrence.leg_count == 4 for occurrence in occurrences)


def test_frozen_table5_network_has_28_sailing_occurrences() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family=("service_family_1"),
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    state = RollingBookingState.empty(inputs.instance)

    capacity_snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=state,
        reporting_time=spec.horizon_end,
        status_updates=inputs.pr_updates,
    )

    occurrences = build_table5_sailing_occurrences(capacity_snapshot)

    assert capacity_snapshot.transport_arc_count == 112

    assert len(occurrences) == 28

    assert all(occurrence.leg_count == 4 for occurrence in occurrences)

    assert all(occurrence.standard_water for occurrence in occurrences)

    assert {occurrence.nominal_capacity for occurrence in occurrences} == {10.0}

    assert len({occurrence.occurrence_key for occurrence in occurrences}) == 28


def test_every_transport_arc_belongs_to_exactly_one_occurrence() -> None:
    spec = default_table5_experiment_spec()

    inputs = build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family=("service_family_1"),
            capacity_teu=10,
            reproduction_class=(spec.reproduction_class),
        ),
        spec=spec,
    )

    state = RollingBookingState.empty(inputs.instance)

    capacity_snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.instance,
        final_state=state,
        reporting_time=spec.horizon_end,
        status_updates=inputs.pr_updates,
    )

    occurrences = build_table5_sailing_occurrences(capacity_snapshot)

    occurrence_arc_ids = [arc.arc_id for occurrence in occurrences for arc in occurrence.arcs]

    snapshot_arc_ids = [arc.arc_id for arc in capacity_snapshot.arcs]

    assert len(occurrence_arc_ids) == 112

    assert len(set(occurrence_arc_ids)) == 112

    assert set(occurrence_arc_ids) == set(snapshot_arc_ids)
