"""Tests for the Phase 11 non-oracle forecast catalogue."""

from barge_rerouting.experiments import (
    TABLE4_FORECAST_LOOKAHEAD_PERIODS,
    TABLE4_FORECAST_SELECTION_MODE,
    TABLE4_FORECAST_VALUE_INTERPRETATION,
    build_table4_controlled_demand_set,
    build_table4_forecast_catalogue,
    forecasts_after_decision_time,
    table4_forecast_seed,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)


def test_forecast_random_stream_is_independent() -> None:
    """Forecast RNG does not reuse structural or economic seeds."""
    assert table4_forecast_seed(11001) == 2011001
    assert table4_forecast_seed(11005) == 2011005


def test_catalogue_contains_ten_forecasts_per_half_day() -> None:
    """One-week baseline creates 14 x 10 ex-ante opportunities."""
    catalogue = build_table4_forecast_catalogue(seed=11001)

    assert catalogue.entry_count == 140

    for reservation_time in range(14):
        entries = tuple(
            entry for entry in catalogue.entries if (entry.reservation_time == reservation_time)
        )

        assert len(entries) == 10
        assert {entry.slot_number for entry in entries} == set(range(1, 11))


def test_catalogue_is_deterministic_and_seed_sensitive() -> None:
    """A registered seed fixes the complete ex-ante catalogue."""
    first = build_table4_forecast_catalogue(seed=11002)
    second = build_table4_forecast_catalogue(seed=11002)
    third = build_table4_forecast_catalogue(seed=11003)

    assert first == second

    assert first.catalogue_fingerprint == second.catalogue_fingerprint

    assert first.catalogue_fingerprint != third.catalogue_fingerprint


def test_forecast_volume_distribution_matches_a032() -> None:
    """Every future class has the pre-registered uncertainty."""
    catalogue = build_table4_forecast_catalogue(seed=11003)

    for entry in catalogue.entries:
        forecast = entry.forecast

        assert forecast.support == (0, 1, 2)
        assert forecast.maximum_volume == 2
        assert forecast.probability_of(0) == 0.40
        assert forecast.probability_of(1) == 0.40
        assert forecast.probability_of(2) == 0.20
        assert forecast.expected_volume == 0.80


def test_provider_boundary_excludes_current_half_day() -> None:
    """Only strictly later reservation periods are forecast."""
    catalogue = build_table4_forecast_catalogue(seed=11004)

    at_zero = forecasts_after_decision_time(
        catalogue,
        decision_time=0,
    )
    at_one = forecasts_after_decision_time(
        catalogue,
        decision_time=1,
    )
    at_twelve = forecasts_after_decision_time(
        catalogue,
        decision_time=12,
    )
    at_thirteen = forecasts_after_decision_time(
        catalogue,
        decision_time=13,
    )

    assert len(at_zero) == 130
    assert len(at_one) == 120
    assert len(at_twelve) == 10
    assert at_thirteen == ()


def test_forecast_catalogue_does_not_equal_realised_future_stream() -> None:
    """Independent forecast attributes are not copied from reality."""
    demand_set = build_table4_controlled_demand_set(seed=11005)
    catalogue = build_table4_forecast_catalogue(seed=11005)

    realised_attributes = tuple(
        (
            demand.origin,
            demand.destination,
            demand.availability_time,
            demand.due_time,
            demand.category,
            demand.fare_per_teu,
        )
        for demand in demand_set.demands
    )

    forecast_attributes = tuple(
        (
            entry.forecast.origin,
            entry.forecast.destination,
            entry.forecast.availability_time,
            entry.forecast.due_time,
            entry.forecast.category,
            entry.forecast.fare_per_teu,
        )
        for entry in catalogue.entries
    )

    assert forecast_attributes != realised_attributes


def test_table4_forecast_policy_settings_are_locked() -> None:
    """Baseline uses printed value and A004 shared-arc selection."""
    assert TABLE4_FORECAST_SELECTION_MODE is FutureDemandSelectionMode.A004_SHARED_ARC

    assert TABLE4_FORECAST_VALUE_INTERPRETATION.value == "printed"

    assert TABLE4_FORECAST_LOOKAHEAD_PERIODS is None


def test_forecast_identifiers_cannot_collide_with_realised_demands() -> None:
    """Forecast IDs use a separate namespace."""
    demand_set = build_table4_controlled_demand_set(seed=11001)
    catalogue = build_table4_forecast_catalogue(seed=11001)

    realised_ids = {demand.demand_id for demand in demand_set.demands}

    forecast_ids = {entry.forecast_id for entry in catalogue.entries}

    assert not realised_ids.intersection(forecast_ids)
