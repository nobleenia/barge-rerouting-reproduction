"""Tests for publication-facing Phase 11 service families."""

from collections import defaultdict

import pytest

from barge_rerouting.experiments import (
    TABLE4_FAMILY_1_DEPARTURE_OFFSETS,
    TABLE4_FAMILY_2_DEPARTURE_OFFSETS,
    TABLE4_REPEAT_PERIOD,
    TABLE4_TERMINALS,
    build_periodic_corridor_transport_legs,
    build_table4_network_config,
    default_table4_service_family_specs,
)


def _legs(
    family: str,
    *,
    capacity: int = 10,
):
    """Build two complete weekly cycles for testing."""
    return build_periodic_corridor_transport_legs(
        time_periods=tuple(range(0, 29)),
        service_family=family,
        capacity_teu=capacity,
    )


def test_default_family_specs_preserve_two_to_one_frequency() -> None:
    """Family 2 has exactly twice Family 1's slot frequency."""
    specs = default_table4_service_family_specs()

    assert len(specs) == 2

    by_key = {spec.family_key: spec for spec in specs}

    assert by_key["service_family_1"].service_slots_per_direction == 2

    assert by_key["service_family_2"].service_slots_per_direction == 4

    assert (
        by_key["service_family_2"].service_slots_per_direction
        == 2 * by_key["service_family_1"].service_slots_per_direction
    )


def test_controlled_offsets_are_explicit_and_weekly() -> None:
    """Unpublished schedule choices remain inspectable constants."""
    assert TABLE4_REPEAT_PERIOD == 14

    assert TABLE4_FAMILY_1_DEPARTURE_OFFSETS == (
        0,
        7,
    )

    assert TABLE4_FAMILY_2_DEPARTURE_OFFSETS == (
        0,
        3,
        7,
        10,
    )


def test_family_one_has_two_service_ids_per_direction() -> None:
    """Recurring cycles reuse two directional service slots."""
    legs = _legs("service_family_1")

    eastbound = {leg.service_id for leg in legs if leg.direction == "eastbound"}
    westbound = {leg.service_id for leg in legs if leg.direction == "westbound"}

    assert len(eastbound) == 2
    assert len(westbound) == 2


def test_family_two_has_four_service_ids_per_direction() -> None:
    """Family 2 doubles the directional service frequency."""
    legs = _legs("service_family_2")

    eastbound = {leg.service_id for leg in legs if leg.direction == "eastbound"}
    westbound = {leg.service_id for leg in legs if leg.direction == "westbound"}

    assert len(eastbound) == 4
    assert len(westbound) == 4


def test_every_occurrence_moves_only_between_adjacent_terminals() -> None:
    """Generated service legs follow the A-B-C-D-E corridor."""
    terminal_index = {terminal: index for index, terminal in enumerate(TABLE4_TERMINALS)}

    for family in (
        "service_family_1",
        "service_family_2",
    ):
        for leg in _legs(family):
            difference = abs(terminal_index[leg.destination] - terminal_index[leg.origin])

            assert difference == 1
            assert leg.arrival_time - leg.departure_time == 1


def test_recurring_service_slots_repeat_every_fourteen_periods() -> None:
    """The same service slot reappears after one weekly cycle."""
    legs = _legs("service_family_1")

    first_leg_departures: dict[str, list[int]] = defaultdict(list)

    for leg in legs:
        if leg.direction == "eastbound" and leg.origin == "A":
            first_leg_departures[leg.service_id].append(leg.departure_time)

    assert len(first_leg_departures) == 2

    for departures in first_leg_departures.values():
        assert len(departures) == 2
        assert departures[1] - departures[0] == 14


def test_capacity_is_applied_to_every_scheduled_leg() -> None:
    """Nominal Table 4 capacity is uniform over one network cell."""
    legs = _legs(
        "service_family_2",
        capacity=15,
    )

    assert legs

    assert {float(leg.capacity) for leg in legs} == {15.0}


def test_table4_network_config_preserves_published_corridor() -> None:
    """Generated network config carries the fixed A--E corridor."""
    config = build_table4_network_config(
        time_periods=tuple(range(0, 29)),
        service_family="service_family_1",
        capacity_teu=20,
    )

    assert config.terminals == TABLE4_TERMINALS
    assert config.time_periods == tuple(range(0, 29))
    assert config.add_holding_arcs
    assert config.transport_legs


def test_noncontiguous_time_grid_is_rejected() -> None:
    """Publication-facing half-day periods require a regular grid."""
    with pytest.raises(
        ValueError,
        match="contiguous half-day",
    ):
        build_periodic_corridor_transport_legs(
            time_periods=(0, 1, 2, 4, 5),
            service_family="service_family_1",
            capacity_teu=10,
        )
