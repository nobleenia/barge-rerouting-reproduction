"""Publication-facing structural demand process for Phase 11.

The source paper supports the following demand-generation structure:

- five terminals A--E;
- ordered origin-destination pairs sampled uniformly;
- ten requests per half-day period;
- customer category selected uniformly from R, P and F;
- anticipation and delivery-time parameters selected from
  distance-dependent pools.

The publication does not disclose the exact distance-dependent timing
pools, realised-demand volume distribution, VMAX, base fares, fare
multipliers, or original random seeds.

This module therefore generates only the structural request templates.
Economic quantities are deliberately attached in a later, separately
documented experiment layer.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from random import Random
from typing import Final

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.experiments.phase11_services import (
    TABLE4_TERMINALS,
)
from barge_rerouting.experiments.phase11_table4 import (
    CONTROLLED_SUBSTITUTE_INPUT,
)

TABLE4_REQUESTS_PER_HALF_DAY: Final = 10

TABLE4_CUSTOMER_CATEGORIES: Final[tuple[CustomerCategory, ...]] = (
    CustomerCategory.REGULAR,
    CustomerCategory.PARTIALLY_SPOT,
    CustomerCategory.FULLY_SPOT,
)

TABLE4_ORDERED_OD_PAIRS: Final[tuple[tuple[str, str], ...]] = tuple(
    (origin, destination)
    for origin in TABLE4_TERMINALS
    for destination in TABLE4_TERMINALS
    if origin != destination
)


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    """Validate a strictly positive integer."""
    value = _validate_nonnegative_integer(
        name,
        value,
    )

    if value == 0:
        raise ValueError(f"{name} must be strictly positive.")

    return value


def corridor_distance(
    origin: str,
    destination: str,
) -> int:
    """Return number of adjacent legs between two corridor terminals."""
    if origin not in TABLE4_TERMINALS:
        raise ValueError(f"Unknown origin terminal: {origin}.")

    if destination not in TABLE4_TERMINALS:
        raise ValueError(f"Unknown destination terminal: {destination}.")

    if origin == destination:
        raise ValueError("Origin and destination must differ.")

    origin_index = int(TABLE4_TERMINALS.index(origin))
    destination_index = int(TABLE4_TERMINALS.index(destination))

    return abs(destination_index - origin_index)


@dataclass(frozen=True, slots=True)
class DistanceTimingPool:
    """Controlled anticipation/deadline choices for one OD distance."""

    distance: int
    anticipation_lags: tuple[int, ...]
    delivery_slacks: tuple[int, ...]

    def __post_init__(self) -> None:
        """Validate a distance-dependent timing pool."""
        distance = _validate_positive_integer(
            "distance",
            self.distance,
        )

        if distance >= len(TABLE4_TERMINALS):
            raise ValueError("distance exceeds the A--E corridor.")

        if not isinstance(
            self.anticipation_lags,
            tuple,
        ):
            raise TypeError("anticipation_lags must be a tuple.")

        if not isinstance(
            self.delivery_slacks,
            tuple,
        ):
            raise TypeError("delivery_slacks must be a tuple.")

        if not self.anticipation_lags:
            raise ValueError("anticipation_lags must be non-empty.")

        if not self.delivery_slacks:
            raise ValueError("delivery_slacks must be non-empty.")

        anticipation = tuple(
            sorted(
                _validate_nonnegative_integer(
                    "anticipation_lag",
                    value,
                )
                for value in self.anticipation_lags
            )
        )

        delivery = tuple(
            sorted(
                _validate_positive_integer(
                    "delivery_slack",
                    value,
                )
                for value in self.delivery_slacks
            )
        )

        if len(set(anticipation)) != len(anticipation):
            raise ValueError("anticipation_lags must be unique.")

        if len(set(delivery)) != len(delivery):
            raise ValueError("delivery_slacks must be unique.")

        object.__setattr__(
            self,
            "distance",
            distance,
        )
        object.__setattr__(
            self,
            "anticipation_lags",
            anticipation,
        )
        object.__setattr__(
            self,
            "delivery_slacks",
            delivery,
        )


@dataclass(frozen=True, slots=True)
class Table4DemandProcessSpec:
    """Structural request-generation specification."""

    request_periods: tuple[int, ...]
    horizon_end: int
    timing_pools: tuple[DistanceTimingPool, ...]
    requests_per_period: int = TABLE4_REQUESTS_PER_HALF_DAY
    reproduction_class: str = CONTROLLED_SUBSTITUTE_INPUT

    def __post_init__(self) -> None:
        """Validate the structural demand-process specification."""
        if not isinstance(
            self.request_periods,
            tuple,
        ):
            raise TypeError("request_periods must be a tuple.")

        if not self.request_periods:
            raise ValueError("request_periods must be non-empty.")

        periods = tuple(
            _validate_nonnegative_integer(
                "request_period",
                period,
            )
            for period in self.request_periods
        )

        if tuple(sorted(periods)) != periods:
            raise ValueError("request_periods must be sorted.")

        if len(set(periods)) != len(periods):
            raise ValueError("request_periods must be unique.")

        horizon_end = _validate_positive_integer(
            "horizon_end",
            self.horizon_end,
        )

        if periods[-1] > horizon_end:
            raise ValueError("request_periods cannot extend beyond horizon_end.")

        requests_per_period = _validate_positive_integer(
            "requests_per_period",
            self.requests_per_period,
        )

        if requests_per_period != TABLE4_REQUESTS_PER_HALF_DAY:
            raise ValueError(
                "The publication-facing baseline requires 10 requests per half-day period."
            )

        if not isinstance(self.timing_pools, tuple):
            raise TypeError("timing_pools must be a tuple.")

        if len(self.timing_pools) != 4:
            raise ValueError("Timing pools are required for corridor distances 1, 2, 3 and 4.")

        by_distance: dict[int, DistanceTimingPool] = {}

        for pool in self.timing_pools:
            if not isinstance(
                pool,
                DistanceTimingPool,
            ):
                raise TypeError("Every timing pool must be a DistanceTimingPool.")

            if pool.distance in by_distance:
                raise ValueError("Timing-pool distances must be unique.")

            by_distance[pool.distance] = pool

        if set(by_distance) != {1, 2, 3, 4}:
            raise ValueError("Timing pools must cover distances 1, 2, 3 and 4.")

        # Avoid implicit truncation or redraw near the horizon.
        # Every published-pool outcome must fit for every configured
        # request period.
        latest_request = periods[-1]

        for pool in by_distance.values():
            latest_due = latest_request + max(pool.anticipation_lags) + max(pool.delivery_slacks)

            if latest_due > horizon_end:
                raise ValueError(
                    "Timing pools extend beyond horizon_end. "
                    "Choose request periods/horizon so every "
                    "configured timing outcome remains admissible."
                )

        if self.reproduction_class != CONTROLLED_SUBSTITUTE_INPUT:
            raise ValueError(
                "Phase 11 structural demand generation "
                "must remain classified as "
                "controlled_substitute_input."
            )

        object.__setattr__(
            self,
            "request_periods",
            periods,
        )
        object.__setattr__(
            self,
            "horizon_end",
            horizon_end,
        )
        object.__setattr__(
            self,
            "requests_per_period",
            requests_per_period,
        )
        object.__setattr__(
            self,
            "timing_pools",
            tuple(by_distance[distance] for distance in (1, 2, 3, 4)),
        )

    @property
    def request_count(self) -> int:
        """Return total structural requests."""
        return len(self.request_periods) * self.requests_per_period

    def timing_pool_for(
        self,
        distance: int,
    ) -> DistanceTimingPool:
        """Return the timing pool for one OD distance."""
        for pool in self.timing_pools:
            if pool.distance == distance:
                return pool

        raise KeyError(f"No timing pool for distance {distance}.")


@dataclass(frozen=True, slots=True)
class Table4RequestTemplate:
    """One structural demand draw before volume/fare realization."""

    demand_id: str
    sequence_number: int
    reservation_time: int
    origin: str
    destination: str
    distance: int
    anticipation_lag: int
    availability_time: int
    delivery_slack: int
    due_time: int
    category: CustomerCategory

    def __post_init__(self) -> None:
        """Validate one request template."""
        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")

        if not self.demand_id.strip():
            raise ValueError("demand_id must be non-empty.")

        sequence = _validate_positive_integer(
            "sequence_number",
            self.sequence_number,
        )

        reservation = _validate_nonnegative_integer(
            "reservation_time",
            self.reservation_time,
        )
        anticipation = _validate_nonnegative_integer(
            "anticipation_lag",
            self.anticipation_lag,
        )
        availability = _validate_nonnegative_integer(
            "availability_time",
            self.availability_time,
        )
        delivery = _validate_positive_integer(
            "delivery_slack",
            self.delivery_slack,
        )
        due = _validate_positive_integer(
            "due_time",
            self.due_time,
        )

        calculated_distance = corridor_distance(
            self.origin,
            self.destination,
        )

        if calculated_distance != self.distance:
            raise ValueError("distance is inconsistent with OD pair.")

        if availability != reservation + anticipation:
            raise ValueError("availability_time must equal reservation_time + anticipation_lag.")

        if due != availability + delivery:
            raise ValueError("due_time must equal availability_time + delivery_slack.")

        if not isinstance(
            self.category,
            CustomerCategory,
        ):
            raise TypeError("category must be a CustomerCategory.")

        object.__setattr__(
            self,
            "sequence_number",
            sequence,
        )


def generate_table4_request_templates(
    spec: Table4DemandProcessSpec,
    *,
    seed: int,
) -> tuple[Table4RequestTemplate, ...]:
    """Generate deterministic publication-structured request templates."""
    if not isinstance(
        spec,
        Table4DemandProcessSpec,
    ):
        raise TypeError("spec must be a Table4DemandProcessSpec.")

    selected_seed = _validate_nonnegative_integer(
        "seed",
        seed,
    )

    random_generator = Random(selected_seed)
    templates: list[Table4RequestTemplate] = []

    sequence = 0

    for reservation_time in spec.request_periods:
        for _ in range(spec.requests_per_period):
            sequence += 1

            origin, destination = random_generator.choice(TABLE4_ORDERED_OD_PAIRS)

            distance = corridor_distance(
                origin,
                destination,
            )

            pool = spec.timing_pool_for(distance)

            anticipation_lag = random_generator.choice(pool.anticipation_lags)
            delivery_slack = random_generator.choice(pool.delivery_slacks)

            availability_time = reservation_time + anticipation_lag
            due_time = availability_time + delivery_slack

            category = random_generator.choice(TABLE4_CUSTOMER_CATEGORIES)

            templates.append(
                Table4RequestTemplate(
                    demand_id=f"K{sequence:04d}",
                    sequence_number=sequence,
                    reservation_time=reservation_time,
                    origin=origin,
                    destination=destination,
                    distance=distance,
                    anticipation_lag=anticipation_lag,
                    availability_time=availability_time,
                    delivery_slack=delivery_slack,
                    due_time=due_time,
                    category=category,
                )
            )

    return tuple(templates)


def request_template_records(
    templates: tuple[Table4RequestTemplate, ...],
) -> tuple[dict[str, object], ...]:
    """Return deterministic serialisable request-template records."""
    return tuple(
        {
            **asdict(template),
            "category": template.category.value,
        }
        for template in templates
    )


def request_template_fingerprint(
    templates: tuple[Table4RequestTemplate, ...],
) -> str:
    """Return deterministic SHA-256 for structural request draws."""
    payload = json.dumps(
        request_template_records(templates),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return sha256(payload.encode("utf-8")).hexdigest()


def write_request_templates_csv(
    templates: tuple[Table4RequestTemplate, ...],
    output_path: str | Path,
) -> Path:
    """Write structural requests to deterministic CSV."""
    records = request_template_records(templates)

    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = (
        "demand_id",
        "sequence_number",
        "reservation_time",
        "origin",
        "destination",
        "distance",
        "anticipation_lag",
        "availability_time",
        "delivery_slack",
        "due_time",
        "category",
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(records)

    return path
