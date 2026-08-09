"""Frozen controlled demand instance for Phase 11 Table 5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from random import Random
from typing import Final

from barge_rerouting.domain import Demand
from barge_rerouting.experiments.phase11_baseline import (
    _draw_volume,
    _fare_for_template,
    default_table4_controlled_economic_spec,
    table4_economic_seed,
)
from barge_rerouting.experiments.phase11_demands import (
    Table4RequestTemplate,
    generate_table4_request_templates,
    request_template_fingerprint,
)
from barge_rerouting.experiments.phase11_economics import (
    Table4EconomicInputSpec,
    table4_economic_input_fingerprint,
)
from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_DEMAND_COUNT,
    TABLE5_REPRODUCTION_CLASS,
    build_table5_demand_process,
)
from barge_rerouting.generation import demand_fingerprint

TABLE5_CONTROLLED_SEED: Final = 12001

TABLE5_EXPECTED_STRUCTURAL_FINGERPRINT: Final = (
    "ddd8cb2cc7616fc67f94ccd62a97cb8e34dc7c8d6d011297ea7b4b27cb8be860"
)

TABLE5_EXPECTED_ECONOMIC_FINGERPRINT: Final = (
    "1ed9142dbe3c001087cccc2b782b37dce1161896d5f94736332ec491da8238b9"
)

TABLE5_EXPECTED_DEMAND_FINGERPRINT: Final = (
    "9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944"
)

TABLE5_EXPECTED_TOTAL_REQUESTED_TEU: Final = 1076.0


TABLE5_POSITIVE_VOLUME_PROBABILITIES: Final[tuple[tuple[int, float], ...]] = (
    (1, 2.0 / 3.0),
    (2, 1.0 / 3.0),
)

TABLE5_VOLUME_CONDITIONING: Final = "positive_volume_q_gt_0"


def _validate_seed(value: object) -> int:
    """Validate one non-negative deterministic seed."""
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise TypeError("seed must be an integer.")

    if value < 0:
        raise ValueError("seed must be non-negative.")

    return value


def _draw_positive_volume(
    random_generator: Random,
    economic_spec: Table4EconomicInputSpec,
) -> int:
    """Draw from A032 conditional on strictly positive volume."""
    while True:
        volume = _draw_volume(
            random_generator,
            economic_spec.volume_distribution,
        )

        if volume > 0:
            return int(volume)


def default_table5_controlled_economic_spec() -> Table4EconomicInputSpec:
    """Return the frozen A032 economics underlying Table 5.

    The stored volume distribution remains the valid A032 distribution
    on support {0, 1, 2}. Table 5 positivity is implemented by conditional
    sampling in `_draw_positive_volume`, not by redefining the published
    distribution support.
    """
    baseline = default_table4_controlled_economic_spec()

    return Table4EconomicInputSpec(
        volume_distribution=(baseline.volume_distribution),
        fare_rates=baseline.fare_rates,
        distance_inputs=baseline.distance_inputs,
        reproduction_class=(TABLE5_REPRODUCTION_CLASS),
    )


def table5_economic_input_fingerprint(
    spec: Table4EconomicInputSpec,
) -> str:
    """Fingerprint economics plus the A040 positive conditioning rule."""
    payload = {
        "base_economic_fingerprint": (table4_economic_input_fingerprint(spec)),
        "volume_conditioning": (TABLE5_VOLUME_CONDITIONING),
        "conditional_positive_probabilities": [
            {
                "volume": volume,
                "probability": probability,
            }
            for (
                volume,
                probability,
            ) in TABLE5_POSITIVE_VOLUME_PROBABILITIES
        ],
        "reproduction_class": (TABLE5_REPRODUCTION_CLASS),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Table5ControlledDemandSet:
    """Frozen 800-demand controlled substitute instance."""

    seed: int
    economic_seed: int
    structural_fingerprint: str
    economic_fingerprint: str
    demand_fingerprint: str
    request_count: int
    templates: tuple[
        Table4RequestTemplate,
        ...,
    ]
    demands: tuple[
        Demand,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate frozen demand-set consistency."""
        if self.request_count != TABLE5_DEMAND_COUNT:
            raise ValueError(f"Table 5 demand set must contain {TABLE5_DEMAND_COUNT} requests.")

        if len(self.templates) != self.request_count:
            raise ValueError("Template count must equal request count.")

        if len(self.demands) != self.request_count:
            raise ValueError("Every Table 5 request must become a positive-volume Demand.")

        if any(demand.volume <= 0.0 for demand in self.demands):
            raise ValueError("Table 5 demands must have positive volume.")


def build_table5_controlled_demand_set(
    *,
    seed: int = TABLE5_CONTROLLED_SEED,
) -> Table5ControlledDemandSet:
    """Generate the deterministic controlled 800-demand instance."""
    selected_seed = _validate_seed(seed)

    process_spec = build_table5_demand_process()

    economic_spec = default_table5_controlled_economic_spec()

    templates = generate_table4_request_templates(
        process_spec,
        seed=selected_seed,
    )

    if len(templates) != TABLE5_DEMAND_COUNT:
        raise RuntimeError(
            "Table 5 structural generator did not produce exactly 800 request templates."
        )

    economic_seed = table4_economic_seed(selected_seed)

    random_generator = Random(economic_seed)

    demands: list[Demand] = []

    for template in templates:
        volume = _draw_positive_volume(
            random_generator,
            economic_spec,
        )

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

    return Table5ControlledDemandSet(
        seed=selected_seed,
        economic_seed=economic_seed,
        structural_fingerprint=(request_template_fingerprint(templates)),
        economic_fingerprint=(table5_economic_input_fingerprint(economic_spec)),
        demand_fingerprint=(demand_fingerprint(realised_demands)),
        request_count=len(realised_demands),
        templates=templates,
        demands=realised_demands,
    )


def build_frozen_table5_controlled_demand_set() -> Table5ControlledDemandSet:
    """Return and verify the publication-facing controlled Table 5 input."""
    demand_set = build_table5_controlled_demand_set(
        seed=TABLE5_CONTROLLED_SEED,
    )

    if demand_set.structural_fingerprint != TABLE5_EXPECTED_STRUCTURAL_FINGERPRINT:
        raise RuntimeError("Frozen Table 5 structural fingerprint changed.")

    if demand_set.economic_fingerprint != TABLE5_EXPECTED_ECONOMIC_FINGERPRINT:
        raise RuntimeError("Frozen Table 5 economic fingerprint changed.")

    if demand_set.demand_fingerprint != TABLE5_EXPECTED_DEMAND_FINGERPRINT:
        raise RuntimeError("Frozen Table 5 demand fingerprint changed.")

    total_requested_teu = float(sum(demand.volume for demand in demand_set.demands))

    if total_requested_teu != TABLE5_EXPECTED_TOTAL_REQUESTED_TEU:
        raise RuntimeError("Frozen Table 5 requested TEU changed.")

    return demand_set
