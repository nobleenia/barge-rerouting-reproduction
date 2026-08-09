"""Frozen inputs and structural gates for the Phase 11 Table 5 pilot."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from barge_rerouting.config import ExperimentConfig
from barge_rerouting.disruption.capacity import (
    build_actual_capacity_profile,
)
from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.disruption.timeline import (
    OperationalTimeline,
    build_operational_timeline,
)
from barge_rerouting.experiments.phase11_pilot import (
    build_table4_pilot_config,
)
from barge_rerouting.experiments.phase11_services import (
    build_table4_network_config,
)
from barge_rerouting.experiments.phase11_table4 import (
    experiment_config_fingerprint,
)
from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_CONTROLLED_HORIZON_END,
    TABLE5_DEMAND_COUNT,
    TABLE5_STANDARD_WATER_FACTOR,
    build_table5_pr_forecast_updates,
)
from barge_rerouting.experiments.phase11_table5_demands import (
    TABLE5_CONTROLLED_SEED,
    TABLE5_EXPECTED_DEMAND_FINGERPRINT,
    build_frozen_table5_controlled_demand_set,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingTimeline,
    build_booking_timeline,
)

TABLE5_PILOT_SERVICE_FAMILY: Final = "service_family_1"
TABLE5_PILOT_CAPACITY_TEU: Final = 10

TABLE5_TRUCK_PENALTY_FARE_MULTIPLIER: Final = 1.0

TABLE5_PILOT_REPRODUCTION_CLASS: Final = "controlled_substitute_input"


@dataclass(frozen=True, slots=True)
class Table5PilotInputs:
    """Verified common input shared by DCA, PR, and FR."""

    config: ExperimentConfig
    instance: ExperimentInstance
    booking_timeline: BookingTimeline
    pr_timeline: OperationalTimeline
    pr_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ]
    truck_penalty_per_teu_by_demand: dict[
        str,
        float,
    ]
    configuration_fingerprint: str
    demand_fingerprint: str

    def __post_init__(self) -> None:
        """Validate the publication-facing pilot contract."""
        if len(self.instance.demands) != TABLE5_DEMAND_COUNT:
            raise ValueError("Table 5 pilot must contain exactly 800 demands.")

        if self.demand_fingerprint != TABLE5_EXPECTED_DEMAND_FINGERPRINT:
            raise ValueError("Table 5 pilot demand fingerprint changed.")

        if self.booking_timeline.event_count != 800:
            raise ValueError("Booking timeline must contain exactly 800 events.")

        if self.pr_timeline.booking_event_count != 800:
            raise ValueError("PR timeline must retain all 800 bookings.")

        if self.pr_timeline.status_update_count != 20:
            raise ValueError("PR timeline must contain 20 forecast-update epochs.")

        if self.pr_timeline.event_count != 820:
            raise ValueError("PR timeline must contain 820 operational events.")

        if len(self.truck_penalty_per_teu_by_demand) != TABLE5_DEMAND_COUNT:
            raise ValueError("Every Table 5 demand requires a truck penalty.")


def build_table5_pilot_config() -> ExperimentConfig:
    """Build Service-Family-1 / 10-TEU Table 5 configuration."""
    base = build_table4_pilot_config()

    frozen = build_frozen_table5_controlled_demand_set()

    network = build_table4_network_config(
        time_periods=tuple(range(TABLE5_CONTROLLED_HORIZON_END + 1)),
        service_family=(TABLE5_PILOT_SERVICE_FAMILY),
        capacity_teu=(TABLE5_PILOT_CAPACITY_TEU),
    )

    minimum_fare = min(demand.fare_per_teu for demand in frozen.demands)

    maximum_fare = max(demand.fare_per_teu for demand in frozen.demands)

    minimum_reservation = min(demand.reservation_time for demand in frozen.demands)

    maximum_reservation = max(demand.reservation_time for demand in frozen.demands)

    minimum_availability_lag = min(
        demand.availability_time - demand.reservation_time for demand in frozen.demands
    )

    maximum_availability_lag = max(
        demand.availability_time - demand.reservation_time for demand in frozen.demands
    )

    minimum_due_slack = min(demand.due_time - demand.availability_time for demand in frozen.demands)

    maximum_due_slack = max(demand.due_time - demand.availability_time for demand in frozen.demands)

    demand_generation = replace(
        base.demand_generation,
        number_of_demands=(TABLE5_DEMAND_COUNT),
        minimum_volume=1,
        maximum_volume=2,
        minimum_fare_per_teu=(minimum_fare),
        maximum_fare_per_teu=(maximum_fare),
        minimum_reservation_time=(minimum_reservation),
        maximum_reservation_time=(maximum_reservation),
        minimum_availability_lag=(minimum_availability_lag),
        maximum_availability_lag=(maximum_availability_lag),
        minimum_due_slack=(minimum_due_slack),
        maximum_due_slack=(maximum_due_slack),
    )

    return replace(
        base,
        experiment_name=("phase11_table5_pilot_family1_capacity10"),
        random_seed=TABLE5_CONTROLLED_SEED,
        network=network,
        demand_generation=demand_generation,
    )


def build_table5_truck_penalties(
    instance: ExperimentInstance,
) -> dict[str, float]:
    """Build the pre-registered A044 truck-penalty mapping."""
    if not isinstance(
        instance,
        ExperimentInstance,
    ):
        raise TypeError("instance must be an ExperimentInstance.")

    return {
        demand.demand_id: float(TABLE5_TRUCK_PENALTY_FARE_MULTIPLIER * demand.fare_per_teu)
        for demand in instance.demands
    }


def verify_table5_structural_feasibility(
    instance: ExperimentInstance,
) -> None:
    """Verify the assembled 800-demand path contract."""
    if len(instance.demands) != TABLE5_DEMAND_COUNT:
        raise RuntimeError("Assembled Table 5 instance does not contain 800 demands.")

    if len(instance.demand_network_indexes) != TABLE5_DEMAND_COUNT:
        raise RuntimeError("Every Table 5 demand must have one network index.")

    for index in instance.demand_network_indexes:
        if not index.destination_nodes:
            raise RuntimeError(f"Demand {index.demand_id} has no feasible destination.")

        if not index.feasible_arc_ids:
            raise RuntimeError(f"Demand {index.demand_id} has no feasible arcs.")


def verify_table5_standard_water(
    instance: ExperimentInstance,
    updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ],
) -> None:
    """Verify neutral PR updates do not alter service capacity."""
    for physical_time in (
        0,
        4,
        20,
        40,
        60,
        76,
    ):
        profile = build_actual_capacity_profile(
            instance,
            physical_time=physical_time,
            status_updates=updates,
        )

        for arc_state in profile.arc_states:
            if abs(arc_state.actual_capacity - arc_state.nominal_capacity) > 1e-9:
                raise RuntimeError("Standard-water Table 5 profile changed nominal capacity.")

            if abs(arc_state.water_level_factor - TABLE5_STANDARD_WATER_FACTOR) > 1e-9:
                raise RuntimeError("Table 5 water factor is not 1.0.")


def build_table5_pilot_inputs() -> Table5PilotInputs:
    """Assemble and verify the frozen Table 5 pilot inputs."""
    demand_set = build_frozen_table5_controlled_demand_set()

    config = build_table5_pilot_config()

    instance = assemble_experiment_instance(
        config,
        demands=demand_set.demands,
    )

    if instance.demand_fingerprint != TABLE5_EXPECTED_DEMAND_FINGERPRINT:
        raise RuntimeError("Assembling Table 5 changed the frozen demands.")

    verify_table5_structural_feasibility(instance)

    booking_timeline = build_booking_timeline(instance)

    pr_updates = build_table5_pr_forecast_updates()

    pr_timeline = build_operational_timeline(
        instance,
        status_updates=pr_updates,
    )

    verify_table5_standard_water(
        instance,
        pr_updates,
    )

    penalties = build_table5_truck_penalties(instance)

    return Table5PilotInputs(
        config=config,
        instance=instance,
        booking_timeline=booking_timeline,
        pr_timeline=pr_timeline,
        pr_updates=pr_updates,
        truck_penalty_per_teu_by_demand=(penalties),
        configuration_fingerprint=(experiment_config_fingerprint(config)),
        demand_fingerprint=(instance.demand_fingerprint),
    )
