"""Tests for discrete future-demand probability distributions."""

import pytest

from barge_rerouting.domain import (
    CustomerCategory,
    FutureDemandForecast,
    VolumeProbability,
)


def make_forecast() -> FutureDemandForecast:
    """Create a standard future-demand forecast."""
    return FutureDemandForecast(
        forecast_id="FK001",
        origin="A",
        destination="C",
        availability_time=2,
        due_time=5,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=50.0,
        outcomes=(
            VolumeProbability(volume=0, probability=0.10),
            VolumeProbability(volume=1, probability=0.20),
            VolumeProbability(volume=2, probability=0.30),
            VolumeProbability(volume=3, probability=0.40),
        ),
    )


def test_valid_forecast_exposes_distribution_properties() -> None:
    """A valid forecast must expose support, maximum, and expectation."""
    forecast = make_forecast()

    assert forecast.support == (0, 1, 2, 3)
    assert forecast.maximum_volume == 3
    assert forecast.candidate_protection_levels == (0, 1, 2, 3)
    assert forecast.expected_volume == pytest.approx(2.0)
    assert forecast.expected_full_revenue == pytest.approx(100.0)


def test_zero_future_volume_is_valid() -> None:
    """A forecast may assign probability to no future demand."""
    forecast = make_forecast()

    assert forecast.probability_of(0) == pytest.approx(0.10)


def test_unsupported_volume_has_zero_probability() -> None:
    """A volume outside the support has probability zero."""
    forecast = make_forecast()

    assert forecast.probability_of(99) == pytest.approx(0.0)


def test_outcomes_are_sorted_by_volume() -> None:
    """Input order must not affect the normalised distribution."""
    forecast = FutureDemandForecast(
        forecast_id="FK001",
        origin="A",
        destination="C",
        availability_time=2,
        due_time=5,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=50.0,
        outcomes=(
            VolumeProbability(volume=3, probability=0.40),
            VolumeProbability(volume=0, probability=0.10),
            VolumeProbability(volume=2, probability=0.30),
            VolumeProbability(volume=1, probability=0.20),
        ),
    )

    assert forecast.support == (0, 1, 2, 3)


def test_paper_prefix_and_capped_expectation_are_distinct() -> None:
    """The printed expression differs from E[min(X,j)] below max volume."""
    forecast = make_forecast()

    assert forecast.paper_prefix_expected_volume(2) == pytest.approx(0.8)
    assert forecast.expected_capped_volume(2) == pytest.approx(1.6)
    assert forecast.tail_probability_above(2) == pytest.approx(0.4)


def test_both_expressions_equal_expected_volume_at_maximum() -> None:
    """At maximum support, neither expression excludes future volume."""
    forecast = make_forecast()

    maximum = forecast.maximum_volume

    assert forecast.paper_prefix_expected_volume(maximum) == pytest.approx(forecast.expected_volume)
    assert forecast.expected_capped_volume(maximum) == pytest.approx(forecast.expected_volume)


def test_zero_protection_has_zero_capped_volume() -> None:
    """Protecting zero TEU gives E[min(X,0)] equal to zero."""
    forecast = make_forecast()

    assert forecast.expected_capped_volume(0) == pytest.approx(0.0)


def test_probabilities_must_sum_to_one() -> None:
    """A malformed probability distribution must be rejected."""
    with pytest.raises(ValueError, match="sum to one"):
        FutureDemandForecast(
            forecast_id="FK001",
            origin="A",
            destination="C",
            availability_time=2,
            due_time=5,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=50.0,
            outcomes=(
                VolumeProbability(volume=0, probability=0.20),
                VolumeProbability(volume=1, probability=0.20),
            ),
        )


def test_duplicate_volume_outcomes_are_rejected() -> None:
    """Each volume may appear only once in a distribution."""
    with pytest.raises(ValueError, match="unique volumes"):
        FutureDemandForecast(
            forecast_id="FK001",
            origin="A",
            destination="C",
            availability_time=2,
            due_time=5,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=50.0,
            outcomes=(
                VolumeProbability(volume=1, probability=0.50),
                VolumeProbability(volume=1, probability=0.50),
            ),
        )


@pytest.mark.parametrize(
    ("volume", "probability"),
    [
        (-1, 1.0),
        (0, -0.1),
        (0, 1.1),
        (0, float("nan")),
        (0, float("inf")),
    ],
)
def test_invalid_outcomes_are_rejected(
    volume: int,
    probability: float,
) -> None:
    """Volumes and probabilities must satisfy their numerical domains."""
    with pytest.raises((TypeError, ValueError)):
        VolumeProbability(
            volume=volume,
            probability=probability,
        )


def test_forecast_requires_at_least_one_outcome() -> None:
    """An empty distribution has no mathematical meaning."""
    with pytest.raises(ValueError, match="At least one"):
        FutureDemandForecast(
            forecast_id="FK001",
            origin="A",
            destination="C",
            availability_time=2,
            due_time=5,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=50.0,
            outcomes=(),
        )


def test_forecast_time_window_must_be_valid() -> None:
    """The due time cannot precede future cargo availability."""
    with pytest.raises(ValueError, match="earlier"):
        FutureDemandForecast(
            forecast_id="FK001",
            origin="A",
            destination="C",
            availability_time=5,
            due_time=2,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=50.0,
            outcomes=(VolumeProbability(volume=0, probability=1.0),),
        )


def test_forecast_requires_distinct_terminals() -> None:
    """A future transport class must require physical movement."""
    with pytest.raises(ValueError, match="must be different"):
        FutureDemandForecast(
            forecast_id="FK001",
            origin="A",
            destination="A",
            availability_time=2,
            due_time=5,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=50.0,
            outcomes=(VolumeProbability(volume=0, probability=1.0),),
        )
