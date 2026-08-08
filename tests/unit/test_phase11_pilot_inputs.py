"""Pre-solve tests for the first Phase 11 Table 4 pilot."""

from barge_rerouting.experiments import (
    TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT,
    TABLE4_PILOT_EXPECTED_FORECAST_FINGERPRINT,
    build_table4_pilot_config,
    build_table4_pilot_inputs,
)


def test_pilot_configuration_has_published_cell_identity() -> None:
    """The first pilot is Family 1 at 10 TEU."""
    config = build_table4_pilot_config()

    transport_legs = config.network.transport_legs

    assert transport_legs

    assert {float(leg.capacity) for leg in transport_legs} == {10.0}

    assert all("service_family_1" in leg.service_id for leg in transport_legs)


def test_pilot_configuration_records_140_opportunities() -> None:
    """Configuration distinguishes opportunities from positive bookings."""
    config = build_table4_pilot_config()

    generation = config.demand_generation

    assert generation.number_of_demands == 140
    assert generation.minimum_volume == 1
    assert generation.maximum_volume == 2
    assert generation.minimum_reservation_time == 0
    assert generation.maximum_reservation_time == 13


def test_pilot_assembles_the_frozen_positive_demand_set() -> None:
    """Instance assembly cannot silently alter the frozen realization."""
    inputs = build_table4_pilot_inputs()

    assert inputs.demand_fingerprint == TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT

    assert inputs.instance.demand_fingerprint == TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT

    # Frozen set 01 contains 85 positive-volume demands.
    assert len(inputs.instance.demands) == 85
    assert inputs.timeline.event_count == 85


def test_pilot_uses_the_frozen_non_oracle_forecast_catalogue() -> None:
    """The pilot catalogue is fixed independently of realised demands."""
    inputs = build_table4_pilot_inputs()

    assert inputs.forecast_fingerprint == TABLE4_PILOT_EXPECTED_FORECAST_FINGERPRINT

    assert inputs.forecast_catalogue.entry_count == 140


def test_pilot_configuration_fingerprint_is_deterministic() -> None:
    """Repeated assembly produces the exact same cell configuration."""
    first = build_table4_pilot_inputs()
    second = build_table4_pilot_inputs()

    assert first.configuration_fingerprint == second.configuration_fingerprint

    assert first.timeline == second.timeline
