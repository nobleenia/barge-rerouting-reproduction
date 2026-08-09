"""Frozen structural inputs for the Phase 11 Table 5 experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.experiments.phase11_baseline import (
    default_table4_controlled_timing_pools,
)
from barge_rerouting.experiments.phase11_demands import (
    Table4DemandProcessSpec,
)
from barge_rerouting.experiments.phase11_services import (
    TABLE4_SERVICE_FAMILIES,
)

TABLE5_REPRODUCTION_CLASS: Final = "controlled_substitute_input"

TABLE5_SERVICE_FAMILIES: Final[tuple[str, ...]] = TABLE4_SERVICE_FAMILIES

TABLE5_CAPACITIES_TEU: Final[tuple[int, ...]] = (
    10,
    20,
    30,
    40,
)

TABLE5_POLICY_KEYS: Final[tuple[str, ...]] = (
    "dca",
    "pr",
    "fr",
)

TABLE5_REQUESTS_PER_PERIOD: Final = 10

TABLE5_REQUEST_PERIODS: Final[tuple[int, ...]] = tuple(range(80))

TABLE5_DEMAND_COUNT: Final = 800

# The Table-4 timing pools permit a maximum:
#
# reservation_time
# + anticipation lag 6
# + delivery slack 13
#
# for the longest OD distance.
#
# Final request period = 79, hence:
#
# 79 + 6 + 13 = 98.
TABLE5_CONTROLLED_HORIZON_END: Final = 98

TABLE5_PR_TRIGGER_INTERVAL_PERIODS: Final = 4

TABLE5_PR_TRIGGER_TIMES: Final[tuple[int, ...]] = tuple(
    range(
        0,
        len(TABLE5_REQUEST_PERIODS),
        TABLE5_PR_TRIGGER_INTERVAL_PERIODS,
    )
)

TABLE5_STANDARD_WATER_FACTOR: Final = 1.0


@dataclass(frozen=True, slots=True)
class Table5ExperimentSpec:
    """Frozen structural contract for one Table 5 campaign."""

    service_families: tuple[str, ...]
    capacities_teu: tuple[int, ...]
    policy_keys: tuple[str, ...]
    demand_count: int
    requests_per_period: int
    request_periods: tuple[int, ...]
    horizon_end: int
    pr_trigger_interval_periods: int
    pr_trigger_times: tuple[int, ...]
    water_level_factor: float
    reproduction_class: str


def default_table5_experiment_spec() -> Table5ExperimentSpec:
    """Return the frozen Phase 11B experiment structure."""
    return Table5ExperimentSpec(
        service_families=TABLE5_SERVICE_FAMILIES,
        capacities_teu=TABLE5_CAPACITIES_TEU,
        policy_keys=TABLE5_POLICY_KEYS,
        demand_count=TABLE5_DEMAND_COUNT,
        requests_per_period=TABLE5_REQUESTS_PER_PERIOD,
        request_periods=TABLE5_REQUEST_PERIODS,
        horizon_end=TABLE5_CONTROLLED_HORIZON_END,
        pr_trigger_interval_periods=(TABLE5_PR_TRIGGER_INTERVAL_PERIODS),
        pr_trigger_times=TABLE5_PR_TRIGGER_TIMES,
        water_level_factor=(TABLE5_STANDARD_WATER_FACTOR),
        reproduction_class=(TABLE5_REPRODUCTION_CLASS),
    )


def build_table5_demand_process() -> Table4DemandProcessSpec:
    """Build the controlled 800-request Table 5 process."""
    return Table4DemandProcessSpec(
        request_periods=TABLE5_REQUEST_PERIODS,
        horizon_end=TABLE5_CONTROLLED_HORIZON_END,
        timing_pools=(default_table4_controlled_timing_pools()),
        requests_per_period=(TABLE5_REQUESTS_PER_PERIOD),
        reproduction_class=(TABLE5_REPRODUCTION_CLASS),
    )


def build_table5_pr_forecast_updates(
    *,
    horizon_end: int = TABLE5_CONTROLLED_HORIZON_END,
) -> tuple[ServiceStatusUpdateEvent, ...]:
    """Encode standard-water PR forecast epochs as neutral updates.

    Phase 10 currently represents operational forecast/status updates with
    ServiceStatusUpdateEvent.  For Table 5 these events are deliberately
    neutral: water_level_factor == 1.0.  Their purpose is to trigger PR at
    four-period forecast-update epochs without reducing service capacity.
    """
    if isinstance(horizon_end, bool) or not isinstance(
        horizon_end,
        int,
    ):
        raise TypeError("horizon_end must be an integer.")

    if horizon_end < TABLE5_REQUEST_PERIODS[-1]:
        raise ValueError("horizon_end cannot precede the final request period.")

    triggers: list[ServiceStatusUpdateEvent] = []

    times = TABLE5_PR_TRIGGER_TIMES

    for position, update_time in enumerate(
        times,
        start=1,
    ):
        next_index = position

        if next_index < len(times):
            valid_until = times[next_index]
        else:
            valid_until = horizon_end + 1

        triggers.append(
            ServiceStatusUpdateEvent(
                sequence_number=position,
                update_time=update_time,
                valid_from=update_time,
                valid_until=valid_until,
                water_level_factor=(TABLE5_STANDARD_WATER_FACTOR),
                affected_service_ids=(),
            )
        )

    return tuple(triggers)
