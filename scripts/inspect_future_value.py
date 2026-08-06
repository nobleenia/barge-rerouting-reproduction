"""Display printed and capped future-demand value functions."""

from barge_rerouting.domain import (
    CustomerCategory,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)


def main() -> None:
    """Display one controlled discrete value table."""
    forecast = FutureDemandForecast(
        forecast_id="FUTURE_HIGH",
        origin="A",
        destination="C",
        availability_time=1,
        due_time=3,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10.0,
        outcomes=(
            VolumeProbability(0, 0.25),
            VolumeProbability(2, 0.25),
            VolumeProbability(4, 0.50),
        ),
    )

    printed = forecast.protection_value_table(interpretation=FutureValueInterpretation.PRINTED)
    capped = forecast.protection_value_table(interpretation=FutureValueInterpretation.CAPPED)

    print("Phase 8A future-demand value functions")
    print(f"Forecast:          {forecast.forecast_id}")
    print(f"Support:           {forecast.support}")
    print(f"Expected volume:   {forecast.expected_volume:.2f}")
    print(f"Expected revenue:  {forecast.expected_full_revenue:.2f}")
    print()
    print("Level  Prefix volume  Capped volume  Prefix revenue  Capped revenue")

    for printed_value, capped_value in zip(
        printed,
        capped,
        strict=True,
    ):
        print(
            f"{printed_value.protection_level:>5}"
            f"{printed_value.expected_volume:>15.2f}"
            f"{capped_value.expected_volume:>15.2f}"
            f"{printed_value.expected_revenue:>16.2f}"
            f"{capped_value.expected_revenue:>16.2f}"
        )


if __name__ == "__main__":
    main()
