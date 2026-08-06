"""Tests for future-demand distributions and value functions."""

import pytest

from barge_rerouting.domain import (
    CustomerCategory,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)


def build_forecast() -> FutureDemandForecast:
    """Build a controlled sparse future-volume distribution."""
    return FutureDemandForecast(
        forecast_id="FUTURE_HIGH",
        origin="A",
        destination="C",
        availability_time=1,
        due_time=3,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10.0,
        outcomes=(
            VolumeProbability(4, 0.50),
            VolumeProbability(0, 0.25),
            VolumeProbability(2, 0.25),
        ),
    )


def test_probability_outcomes_are_sorted() -> None:
    """Forecast outcomes must have deterministic volume order."""
    forecast = build_forecast()

    assert forecast.support == (0, 2, 4)
    assert forecast.maximum_volume == 4
    assert forecast.candidate_protection_levels == (
        0,
        1,
        2,
        3,
        4,
    )
    assert forecast.positive_protection_levels == (
        1,
        2,
        3,
        4,
    )


def test_sparse_support_has_zero_probability_between_outcomes() -> None:
    """Missing integer outcomes represent zero probability mass."""
    forecast = build_forecast()

    assert forecast.probability_of(0) == pytest.approx(0.25)
    assert forecast.probability_of(1) == pytest.approx(0.0)
    assert forecast.probability_of(2) == pytest.approx(0.25)
    assert forecast.probability_of(3) == pytest.approx(0.0)
    assert forecast.probability_of(4) == pytest.approx(0.50)


def test_expected_volume_and_full_revenue() -> None:
    """Ordinary expectation must use the complete distribution."""
    forecast = build_forecast()

    assert forecast.expected_volume == pytest.approx(2.5)
    assert forecast.expected_full_revenue == pytest.approx(25.0)


def test_printed_prefix_expression() -> None:
    """Outcomes above j contribute nothing to the printed term."""
    forecast = build_forecast()

    assert forecast.paper_prefix_expected_volume(0) == pytest.approx(0.0)

    assert forecast.paper_prefix_expected_volume(1) == pytest.approx(0.0)

    assert forecast.paper_prefix_expected_volume(2) == pytest.approx(0.5)

    assert forecast.paper_prefix_expected_volume(4) == pytest.approx(2.5)


def test_capped_expected_volume() -> None:
    """The capped sensitivity must credit min(X, j)."""
    forecast = build_forecast()

    assert forecast.expected_capped_volume(0) == pytest.approx(0.0)

    assert forecast.expected_capped_volume(1) == pytest.approx(0.75)

    assert forecast.expected_capped_volume(2) == pytest.approx(1.5)

    assert forecast.expected_capped_volume(4) == pytest.approx(2.5)


@pytest.mark.parametrize(
    "protection_level",
    (0, 1, 2, 3, 4),
)
def test_capped_value_matches_prefix_plus_tail_identity(
    protection_level: int,
) -> None:
    """Verify E[min(X,j)] = prefix(j) + j P(X>j)."""
    forecast = build_forecast()

    expected = forecast.paper_prefix_expected_volume(
        protection_level
    ) + protection_level * forecast.tail_probability_above(protection_level)

    assert forecast.expected_capped_volume(protection_level) == pytest.approx(expected)


def test_interpretation_selects_the_correct_value_function() -> None:
    """Printed and capped interpretations must remain distinct."""
    forecast = build_forecast()

    printed = forecast.protected_expected_volume(
        2,
        interpretation=FutureValueInterpretation.PRINTED,
    )
    capped = forecast.protected_expected_volume(
        2,
        interpretation=FutureValueInterpretation.CAPPED,
    )

    assert printed == pytest.approx(0.5)
    assert capped == pytest.approx(1.5)
    assert capped > printed


def test_protected_expected_revenue_uses_fare_per_teu() -> None:
    """Future revenue equals credited volume multiplied by fare."""
    forecast = build_forecast()

    assert forecast.protected_expected_revenue(
        2,
        interpretation=FutureValueInterpretation.PRINTED,
    ) == pytest.approx(5.0)

    assert forecast.protected_expected_revenue(
        2,
        interpretation=FutureValueInterpretation.CAPPED,
    ) == pytest.approx(15.0)


def test_value_table_is_piecewise_and_deterministic() -> None:
    """The model coefficient table must cover every candidate level."""
    forecast = build_forecast()

    printed = forecast.protection_value_table(interpretation=FutureValueInterpretation.PRINTED)
    capped = forecast.protection_value_table(interpretation=FutureValueInterpretation.CAPPED)

    assert tuple(value.protection_level for value in printed) == (0, 1, 2, 3, 4)

    assert tuple(value.expected_volume for value in printed) == pytest.approx(
        (0.0, 0.0, 0.5, 0.5, 2.5)
    )

    assert tuple(value.expected_volume for value in capped) == pytest.approx(
        (0.0, 0.75, 1.5, 2.0, 2.5)
    )

    assert printed == forecast.protection_value_table(
        interpretation=FutureValueInterpretation.PRINTED
    )


def test_invalid_probability_mass_is_rejected() -> None:
    """A future distribution must have total probability one."""
    with pytest.raises(
        ValueError,
        match="probabilities must sum to one",
    ):
        FutureDemandForecast(
            forecast_id="INVALID",
            origin="A",
            destination="C",
            availability_time=1,
            due_time=3,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=10.0,
            outcomes=(
                VolumeProbability(0, 0.25),
                VolumeProbability(2, 0.25),
            ),
        )


def test_duplicate_volume_outcomes_are_rejected() -> None:
    """Each possible volume must occur at most once."""
    with pytest.raises(
        ValueError,
        match="unique volumes",
    ):
        FutureDemandForecast(
            forecast_id="DUPLICATE",
            origin="A",
            destination="C",
            availability_time=1,
            due_time=3,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=10.0,
            outcomes=(
                VolumeProbability(0, 0.25),
                VolumeProbability(2, 0.25),
                VolumeProbability(2, 0.50),
            ),
        )


def test_interpretation_type_is_validated() -> None:
    """Value construction must not silently accept arbitrary strings."""
    forecast = build_forecast()

    with pytest.raises(
        TypeError,
        match="FutureValueInterpretation",
    ):
        forecast.protected_expected_volume(
            2,
            interpretation="printed",  # type: ignore[arg-type]
        )
