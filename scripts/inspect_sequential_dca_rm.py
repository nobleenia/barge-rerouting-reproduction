"""Compare myopic DCA with sequential DCA-RM."""

from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    FutureValueInterpretation,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
)
from barge_rerouting.revenue_management.run import (
    run_time_aware_dca_rm,
)
from barge_rerouting.rolling_horizon import (
    run_time_aware_sequential_dca,
)


def build_instance():
    """Build the controlled two-event instance."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    return assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "CURRENT",
                4,
                "A",
                "C",
                0,
                0,
                2,
                CustomerCategory.PARTIALLY_SPOT,
                10,
            ),
            Demand(
                "FUTURE",
                4,
                "B",
                "C",
                1,
                1,
                2,
                CustomerCategory.FULLY_SPOT,
                100,
            ),
        ),
    )


def provider(probability_four: float):
    """Provide one forecast before the future arrival."""
    forecast = FutureDemandForecast(
        forecast_id="FUTURE",
        origin="B",
        destination="C",
        availability_time=1,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=(
            VolumeProbability(
                0,
                1.0 - probability_four,
            ),
            VolumeProbability(
                4,
                probability_four,
            ),
        ),
    )

    def provide(event, state):
        del state
        return (forecast,) if event.demand_id == "CURRENT" else ()

    return provide


def run_rm(probability: float):
    """Run one probability case."""
    return run_time_aware_dca_rm(
        build_instance(),
        provider(probability),
        value_interpretation=(FutureValueInterpretation.PRINTED),
        selection_mode=(FutureDemandSelectionMode.EXPLICIT),
    )


def main() -> None:
    """Display the complete opportunity-cost gate."""
    baseline = run_time_aware_sequential_dca(build_instance())
    high = run_rm(0.50)
    low = run_rm(0.05)

    first_high = high.results[0]
    bottleneck = first_high.capacity_transition_for("transport::1::S_BOTTLENECK")

    print("Phase 8E sequential DCA-RM evaluation")
    print()
    print("Policy                  Realised revenue  Accepted demands")
    print(
        f"Myopic DCA              "
        f"{baseline.total_revenue:>16.2f}  "
        f"{baseline.final_state.accepted_demand_ids}"
    )
    print(
        f"DCA-RM high probability "
        f"{high.total_realised_revenue:>16.2f}  "
        f"{high.final_state.accepted_demand_ids}"
    )
    print(
        f"DCA-RM low probability  "
        f"{low.total_realised_revenue:>16.2f}  "
        f"{low.final_state.accepted_demand_ids}"
    )
    print()
    print(
        "High-probability event-one protection: "
        f"{first_high.protection_for('FUTURE').protected_volume:.2f} TEU"
    )
    print(f"Persisted residual capacity after event one: {bottleneck.residual_after:.2f} TEU")
    print(f"High-probability summed event objectives: {high.summed_event_objectives:.2f}")
    print(f"High-probability realised revenue: {high.total_realised_revenue:.2f}")
    print()
    print("Tentative future flow protected the decision but was not persisted as a commitment.")


if __name__ == "__main__":
    main()
