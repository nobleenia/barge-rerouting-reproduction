"""Pre-registered controlled numerical baseline for Phase 11.

These numerical values are not reported by the source paper and are not
calibrated against Table 4. They provide a fixed controlled substitute
baseline so the complete reproduction pipeline can be exercised without
silently inventing parameters inside model code.

If original supplementary parameters are later recovered, those parameters
supersede this baseline for strict numerical reproduction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Final

from barge_rerouting.domain import Demand, VolumeProbability
from barge_rerouting.experiments.phase11_demands import (
    DistanceTimingPool,
    Table4DemandProcessSpec,
    Table4RequestTemplate,
    generate_table4_request_templates,
    request_template_fingerprint,
    write_request_templates_csv,
)
from barge_rerouting.experiments.phase11_economics import (
    DiscreteVolumeDistribution,
    DistanceEconomicInput,
    FareClassRates,
    Table4EconomicInputSpec,
    table4_economic_input_fingerprint,
)
from barge_rerouting.generation import (
    demand_fingerprint,
    write_demands_csv,
)

TABLE4_CONTROLLED_VMAX: Final = 2

TABLE4_CONTROLLED_VOLUME_PROBABILITIES: Final[tuple[float, ...]] = (
    0.40,
    0.40,
    0.20,
)

TABLE4_CONTROLLED_PREMIUM_RATE: Final = 1.25

TABLE4_CONTROLLED_BASE_FARE_PER_DISTANCE: Final = 100.0

TABLE4_CONTROLLED_REQUEST_PERIODS: Final[tuple[int, ...]] = tuple(range(14))

TABLE4_CONTROLLED_HORIZON_END: Final = 32

# Economic random draws use an independent deterministic stream so changes
# to structural request-generation internals do not silently change volume
# realisations.
TABLE4_ECONOMIC_SEED_OFFSET: Final = 1_000_000


def _validate_seed(value: object) -> int:
    """Validate one non-negative experiment seed."""
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError("seed must be an integer.")

    if value < 0:
        raise ValueError("seed must be non-negative.")

    return value


def default_table4_controlled_timing_pools() -> tuple[DistanceTimingPool, ...]:
    """Return pre-registered distance-dependent timing pools."""
    return tuple(
        DistanceTimingPool(
            distance=distance,
            anticipation_lags=(
                distance,
                distance + 1,
                distance + 2,
            ),
            delivery_slacks=(
                distance + 7,
                distance + 8,
                distance + 9,
            ),
        )
        for distance in (1, 2, 3, 4)
    )


def default_table4_controlled_demand_process() -> Table4DemandProcessSpec:
    """Return the one-week controlled request process."""
    return Table4DemandProcessSpec(
        request_periods=(TABLE4_CONTROLLED_REQUEST_PERIODS),
        horizon_end=TABLE4_CONTROLLED_HORIZON_END,
        timing_pools=(default_table4_controlled_timing_pools()),
    )


def default_table4_controlled_economic_spec() -> Table4EconomicInputSpec:
    """Return the pre-registered economic baseline."""
    distribution = DiscreteVolumeDistribution(
        outcomes=tuple(
            VolumeProbability(
                volume=volume,
                probability=probability,
            )
            for volume, probability in enumerate(TABLE4_CONTROLLED_VOLUME_PROBABILITIES)
        )
    )

    fare_rates = FareClassRates(
        early_reservation_rate=1.0,
        late_reservation_rate=(TABLE4_CONTROLLED_PREMIUM_RATE),
        standard_delivery_rate=1.0,
        express_delivery_rate=(TABLE4_CONTROLLED_PREMIUM_RATE),
    )

    distance_inputs = tuple(
        DistanceEconomicInput(
            distance=distance,
            base_fare_per_teu=(TABLE4_CONTROLLED_BASE_FARE_PER_DISTANCE * distance),
            anticipation_threshold=distance + 1,
            delivery_threshold=distance + 8,
        )
        for distance in (1, 2, 3, 4)
    )

    return Table4EconomicInputSpec(
        volume_distribution=distribution,
        fare_rates=fare_rates,
        distance_inputs=distance_inputs,
    )


def table4_economic_seed(seed: int) -> int:
    """Derive an independent deterministic economic random seed."""
    return _validate_seed(seed) + TABLE4_ECONOMIC_SEED_OFFSET


def _draw_volume(
    random_generator: Random,
    distribution: DiscreteVolumeDistribution,
) -> int:
    """Draw one volume from an explicit probability mass."""
    random_value = random_generator.random()
    cumulative_probability = 0.0

    for outcome in distribution.outcomes[:-1]:
        cumulative_probability += float(outcome.probability)

        if random_value < cumulative_probability:
            return int(outcome.volume)

    return int(distribution.outcomes[-1].volume)


def _fare_for_template(
    template: Table4RequestTemplate,
    economic_spec: Table4EconomicInputSpec,
) -> float:
    """Calculate the fare class for one structural request."""
    distance_input = economic_spec.input_for_distance(template.distance)

    # More anticipation means earlier reservation.
    early_reservation = template.anticipation_lag >= distance_input.anticipation_threshold

    # More delivery slack means standard rather than express delivery.
    standard_delivery = template.delivery_slack >= distance_input.delivery_threshold

    fare_per_teu = economic_spec.fare_per_teu_for_classes(
        distance=template.distance,
        early_reservation=early_reservation,
        standard_delivery=standard_delivery,
    )

    return float(fare_per_teu)


@dataclass(frozen=True, slots=True)
class Table4ControlledDemandSet:
    """One complete immutable controlled demand-set realisation."""

    seed: int
    economic_seed: int
    structural_fingerprint: str
    economic_fingerprint: str
    demand_fingerprint: str
    opportunity_count: int
    zero_volume_count: int
    positive_demand_count: int
    templates: tuple[Table4RequestTemplate, ...]
    demands: tuple[Demand, ...]

    def __post_init__(self) -> None:
        """Validate demand-set accounting and fingerprints."""
        selected_seed = _validate_seed(self.seed)
        selected_economic_seed = _validate_seed(self.economic_seed)

        if selected_economic_seed != table4_economic_seed(selected_seed):
            raise ValueError("economic_seed is inconsistent with seed.")

        if self.opportunity_count != len(self.templates):
            raise ValueError("opportunity_count must equal template count.")

        if self.positive_demand_count != len(self.demands):
            raise ValueError("positive_demand_count must equal demand count.")

        if self.zero_volume_count + self.positive_demand_count != self.opportunity_count:
            raise ValueError(
                "Zero- and positive-volume counts must reconcile to opportunity count."
            )

        if request_template_fingerprint(self.templates) != self.structural_fingerprint:
            raise ValueError("structural_fingerprint does not match templates.")

        if demand_fingerprint(self.demands) != self.demand_fingerprint:
            raise ValueError("demand_fingerprint does not match demands.")


def build_table4_controlled_demand_set(
    *,
    seed: int,
) -> Table4ControlledDemandSet:
    """Generate one immutable controlled Table 4 demand set."""
    selected_seed = _validate_seed(seed)

    process_spec = default_table4_controlled_demand_process()
    economic_spec = default_table4_controlled_economic_spec()

    templates = generate_table4_request_templates(
        process_spec,
        seed=selected_seed,
    )

    economic_seed = table4_economic_seed(selected_seed)
    random_generator = Random(economic_seed)

    demands: list[Demand] = []
    zero_volume_count = 0

    for template in templates:
        volume = _draw_volume(
            random_generator,
            economic_spec.volume_distribution,
        )

        if volume == 0:
            zero_volume_count += 1
            continue

        fare_per_teu = _fare_for_template(
            template,
            economic_spec,
        )

        demands.append(
            Demand(
                demand_id=template.demand_id,
                volume=float(volume),
                origin=template.origin,
                destination=template.destination,
                reservation_time=(template.reservation_time),
                availability_time=(template.availability_time),
                due_time=template.due_time,
                category=template.category,
                fare_per_teu=fare_per_teu,
            )
        )

    realised_demands = tuple(demands)

    if not realised_demands:
        raise RuntimeError("Controlled demand set contains no positive-volume bookings.")

    return Table4ControlledDemandSet(
        seed=selected_seed,
        economic_seed=economic_seed,
        structural_fingerprint=(request_template_fingerprint(templates)),
        economic_fingerprint=(table4_economic_input_fingerprint(economic_spec)),
        demand_fingerprint=(demand_fingerprint(realised_demands)),
        opportunity_count=len(templates),
        zero_volume_count=zero_volume_count,
        positive_demand_count=len(realised_demands),
        templates=templates,
        demands=realised_demands,
    )


def write_table4_controlled_demand_set(
    demand_set: Table4ControlledDemandSet,
    *,
    output_directory: str | Path,
    demand_set_id: str,
) -> tuple[Path, Path, Path]:
    """Write templates, positive demands, and traceability manifest."""
    if not isinstance(
        demand_set,
        Table4ControlledDemandSet,
    ):
        raise TypeError("demand_set must be a Table4ControlledDemandSet.")

    if not isinstance(demand_set_id, str):
        raise TypeError("demand_set_id must be a string.")

    selected_id = demand_set_id.strip()

    if not selected_id:
        raise ValueError("demand_set_id must be non-empty.")

    directory = Path(output_directory)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    templates_path = directory / f"{selected_id}_opportunities.csv"
    demands_path = directory / f"{selected_id}_positive_demands.csv"
    manifest_path = directory / f"{selected_id}_manifest.json"

    write_request_templates_csv(
        demand_set.templates,
        templates_path,
    )
    write_demands_csv(
        demand_set.demands,
        demands_path,
    )

    payload = {
        "demand_set_id": selected_id,
        "seed": demand_set.seed,
        "economic_seed": demand_set.economic_seed,
        "classification": ("controlled_substitute_input"),
        "structural_fingerprint": (demand_set.structural_fingerprint),
        "economic_fingerprint": (demand_set.economic_fingerprint),
        "demand_fingerprint": (demand_set.demand_fingerprint),
        "opportunity_count": (demand_set.opportunity_count),
        "zero_volume_count": (demand_set.zero_volume_count),
        "positive_demand_count": (demand_set.positive_demand_count),
        "controlled_baseline": {
            "vmax": TABLE4_CONTROLLED_VMAX,
            "volume_probabilities": list(TABLE4_CONTROLLED_VOLUME_PROBABILITIES),
            "premium_rate": (TABLE4_CONTROLLED_PREMIUM_RATE),
            "base_fare_per_distance": (TABLE4_CONTROLLED_BASE_FARE_PER_DISTANCE),
            "request_periods": list(TABLE4_CONTROLLED_REQUEST_PERIODS),
            "horizon_end": (TABLE4_CONTROLLED_HORIZON_END),
        },
    }

    manifest_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        templates_path,
        demands_path,
        manifest_path,
    )
