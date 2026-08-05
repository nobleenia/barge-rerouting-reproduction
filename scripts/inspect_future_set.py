"""Demonstrate explicit and inferred future-demand sets."""

from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management import (
    select_a004_interacting_future_set,
    select_explicit_future_set,
)
from barge_rerouting.rolling_horizon import (
    build_booking_timeline,
)


def make_forecast(
    forecast_id: str,
    destination: str,
) -> FutureDemandForecast:
    """Build one controlled future forecast."""
    return FutureDemandForecast(
        forecast_id=forecast_id,
        origin="B",
        destination=destination,
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(0, 0.5),
            VolumeProbability(4, 0.5),
        ),
    )


def main() -> None:
    """Display explicit and A004-selected future sets."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    current = Demand(
        demand_id="CURRENT",
        volume=4,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10,
    )

    instance = assemble_experiment_instance(
        config,
        demands=(current,),
    )
    event = build_booking_timeline(instance).event_at_sequence(1)

    shared = make_forecast("SHARED", "C")
    alternative = make_forecast(
        "ALTERNATIVE",
        "D",
    )

    explicit = select_explicit_future_set(
        instance,
        event,
        (shared, alternative),
    )
    inferred = select_a004_interacting_future_set(
        instance,
        event,
        (shared, alternative),
    )

    print("Phase 8B future-demand set construction")
    print(f"Current event:       {event.event_id}")
    print(f"Explicit K(current): {explicit.forecast_ids}")
    print(f"A004 K(current):     {inferred.forecast_ids}")
    print(f"Excluded forecasts:  {inferred.excluded_forecast_ids}")

    candidate = inferred.candidate_for("SHARED")

    print(f"Shared capacity:     {candidate.shared_transport_arc_ids}")
    print(f"Future source:       {candidate.network_index.source}")
    print(f"Future destinations: {candidate.network_index.destination_nodes}")


if __name__ == "__main__":
    main()
