"""Frozen structural contract for Phase-11C Table-6 reproduction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from typing import Final

from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_CAPACITIES_TEU,
    TABLE5_CONTROLLED_HORIZON_END,
    TABLE5_DEMAND_COUNT,
    TABLE5_PR_TRIGGER_INTERVAL_PERIODS,
    TABLE5_PR_TRIGGER_TIMES,
    TABLE5_REQUEST_PERIODS,
    TABLE5_REQUESTS_PER_PERIOD,
    TABLE5_SERVICE_FAMILIES,
    build_table5_pr_forecast_updates,
)

TABLE6_REPRODUCTION_CLASS: Final = "controlled_substitute_input"

TABLE6_POLICY_KEY: Final = "pr"

TABLE6_WATER_FACTORS: Final[tuple[float, ...]] = (
    1.0,
    0.9,
    0.8,
    0.7,
)

# The standard-water 1.0 rows are reused from
# the validated Table-5 PR campaign.
TABLE6_NEW_WATER_FACTORS: Final[tuple[float, ...]] = (
    0.9,
    0.8,
    0.7,
)


@dataclass(frozen=True, slots=True)
class Table6ExperimentSpec:
    """Frozen controlled Table-6 experiment structure."""

    service_families: tuple[str, ...]
    capacities_teu: tuple[int, ...]
    water_factors: tuple[float, ...]
    new_water_factors: tuple[float, ...]
    policy_key: str

    demand_count: int
    requests_per_period: int
    request_periods: tuple[int, ...]
    horizon_end: int

    pr_trigger_interval_periods: int
    pr_trigger_times: tuple[int, ...]

    reproduction_class: str


def default_table6_experiment_spec() -> Table6ExperimentSpec:
    """Return the frozen Phase-11C structure."""
    return Table6ExperimentSpec(
        service_families=TABLE5_SERVICE_FAMILIES,
        capacities_teu=TABLE5_CAPACITIES_TEU,
        water_factors=TABLE6_WATER_FACTORS,
        new_water_factors=(TABLE6_NEW_WATER_FACTORS),
        policy_key=TABLE6_POLICY_KEY,
        demand_count=TABLE5_DEMAND_COUNT,
        requests_per_period=(TABLE5_REQUESTS_PER_PERIOD),
        request_periods=TABLE5_REQUEST_PERIODS,
        horizon_end=TABLE5_CONTROLLED_HORIZON_END,
        pr_trigger_interval_periods=(TABLE5_PR_TRIGGER_INTERVAL_PERIODS),
        pr_trigger_times=TABLE5_PR_TRIGGER_TIMES,
        reproduction_class=(TABLE6_REPRODUCTION_CLASS),
    )


def _validated_water_factor(
    water_factor: float,
) -> float:
    """Validate one frozen Table-6 water factor."""
    if isinstance(
        water_factor,
        bool,
    ) or not isinstance(
        water_factor,
        (int, float),
    ):
        raise TypeError("water_factor must be numeric.")

    factor = float(water_factor)

    if not any(
        isclose(
            factor,
            expected,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        for expected in TABLE6_WATER_FACTORS
    ):
        raise ValueError("water_factor must be one of 1.0, 0.9, 0.8, or 0.7.")

    return factor


def build_table6_pr_forecast_updates(
    water_factor: float,
    *,
    horizon_end: int = TABLE5_CONTROLLED_HORIZON_END,
) -> tuple[
    ServiceStatusUpdateEvent,
    ...,
]:
    """Build constant-factor Table-6 PR forecast windows.

    The update epochs and validity windows are inherited
    from the frozen Table-5 PR timing contract.

    For one Table-6 scenario, the same water factor is
    issued at all 20 forecast epochs.
    """
    factor = _validated_water_factor(water_factor)

    base = build_table5_pr_forecast_updates(horizon_end=horizon_end)

    return tuple(
        replace(
            update,
            water_level_factor=factor,
        )
        for update in base
    )
