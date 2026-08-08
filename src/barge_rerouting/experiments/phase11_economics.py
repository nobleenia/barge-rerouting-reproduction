"""Economic and stochastic input contract for Phase 11.

The 2024 paper specifies the structure of the demand-volume and fare
generation process but does not disclose all numerical parameters.

This module encodes that published structure without selecting substitute
VMAX values, probability masses, base fares, timing thresholds, or premium
fare multipliers.

Numerical baseline values belong to a separately documented experiment
configuration and must not be tuned to reproduce Table 4.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isclose, isfinite

from barge_rerouting.domain import (
    PROBABILITY_TOLERANCE,
    VolumeProbability,
)
from barge_rerouting.experiments.phase11_table4 import (
    CONTROLLED_SUBSTITUTE_INPUT,
)

PUBLISHED_STRUCTURE: str = "strict_publication_structure"


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate one non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    """Validate one strictly positive integer."""
    validated = _validate_nonnegative_integer(
        name,
        value,
    )

    if validated == 0:
        raise ValueError(f"{name} must be strictly positive.")

    return validated


def _validate_positive_float(
    name: str,
    value: object,
) -> float:
    """Validate one finite strictly positive number."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric


@dataclass(frozen=True, slots=True)
class DiscreteVolumeDistribution:
    """One explicit probability mass over 0, ..., VMAX."""

    outcomes: tuple[VolumeProbability, ...]

    def __post_init__(self) -> None:
        """Validate contiguous support and total probability."""
        if not isinstance(self.outcomes, tuple):
            raise TypeError("outcomes must be a tuple.")

        if len(self.outcomes) < 2:
            raise ValueError(
                "A volume distribution must contain zero and at least one positive volume."
            )

        for outcome in self.outcomes:
            if not isinstance(
                outcome,
                VolumeProbability,
            ):
                raise TypeError("Every outcome must be a VolumeProbability.")

        ordered = tuple(
            sorted(
                self.outcomes,
                key=lambda outcome: outcome.volume,
            )
        )

        support = tuple(outcome.volume for outcome in ordered)

        if len(set(support)) != len(support):
            raise ValueError("Volume outcomes must be unique.")

        maximum_volume = support[-1]

        if maximum_volume <= 0:
            raise ValueError("VMAX must be strictly positive.")

        expected_support = tuple(range(maximum_volume + 1))

        if support != expected_support:
            raise ValueError("Published volume support must be contiguous from 0 through VMAX.")

        probability_sum = sum(float(outcome.probability) for outcome in ordered)

        if not isclose(
            probability_sum,
            1.0,
            rel_tol=0.0,
            abs_tol=PROBABILITY_TOLERANCE,
        ):
            raise ValueError(f"Volume probabilities must sum to one; received {probability_sum}.")

        object.__setattr__(
            self,
            "outcomes",
            ordered,
        )

    @property
    def support(self) -> tuple[int, ...]:
        """Return 0, ..., VMAX."""
        return tuple(outcome.volume for outcome in self.outcomes)

    @property
    def maximum_volume(self) -> int:
        """Return VMAX."""
        return int(self.outcomes[-1].volume)

    @property
    def zero_probability(self) -> float:
        """Return P(X=0)."""
        return float(self.outcomes[0].probability)

    @property
    def expected_volume(self) -> float:
        """Return E[X]."""
        return float(sum(outcome.volume * float(outcome.probability) for outcome in self.outcomes))


@dataclass(frozen=True, slots=True)
class FareClassRates:
    """Published fare-rate structure for timing classes.

    The source fixes:

    - early reservation rate = 1;
    - standard delivery rate = 1;
    - late reservation rate > 1;
    - express delivery rate > 1.

    The two premium values remain numerical inputs.
    """

    early_reservation_rate: float
    late_reservation_rate: float
    standard_delivery_rate: float
    express_delivery_rate: float

    def __post_init__(self) -> None:
        """Validate the published fare-rate relationships."""
        early = _validate_positive_float(
            "early_reservation_rate",
            self.early_reservation_rate,
        )
        late = _validate_positive_float(
            "late_reservation_rate",
            self.late_reservation_rate,
        )
        standard = _validate_positive_float(
            "standard_delivery_rate",
            self.standard_delivery_rate,
        )
        express = _validate_positive_float(
            "express_delivery_rate",
            self.express_delivery_rate,
        )

        if not isclose(
            early,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("The paper fixes the early-reservation rate to 1.")

        if not isclose(
            standard,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("The paper fixes the standard-delivery rate to 1.")

        if late <= 1.0:
            raise ValueError("The late-reservation rate must be strictly greater than one.")

        if express <= 1.0:
            raise ValueError("The express-delivery rate must be strictly greater than one.")

        object.__setattr__(
            self,
            "early_reservation_rate",
            early,
        )
        object.__setattr__(
            self,
            "late_reservation_rate",
            late,
        )
        object.__setattr__(
            self,
            "standard_delivery_rate",
            standard,
        )
        object.__setattr__(
            self,
            "express_delivery_rate",
            express,
        )


@dataclass(frozen=True, slots=True)
class DistanceEconomicInput:
    """Undisclosed economic/timing inputs for one OD distance."""

    distance: int
    base_fare_per_teu: float
    anticipation_threshold: int
    delivery_threshold: int

    def __post_init__(self) -> None:
        """Validate one corridor-distance economic record."""
        distance = _validate_positive_integer(
            "distance",
            self.distance,
        )

        if distance not in {1, 2, 3, 4}:
            raise ValueError("distance must be one of 1, 2, 3, 4.")

        base_fare = _validate_positive_float(
            "base_fare_per_teu",
            self.base_fare_per_teu,
        )

        anticipation_threshold = _validate_nonnegative_integer(
            "anticipation_threshold",
            self.anticipation_threshold,
        )

        delivery_threshold = _validate_positive_integer(
            "delivery_threshold",
            self.delivery_threshold,
        )

        object.__setattr__(
            self,
            "distance",
            distance,
        )
        object.__setattr__(
            self,
            "base_fare_per_teu",
            base_fare,
        )
        object.__setattr__(
            self,
            "anticipation_threshold",
            anticipation_threshold,
        )
        object.__setattr__(
            self,
            "delivery_threshold",
            delivery_threshold,
        )


@dataclass(frozen=True, slots=True)
class Table4EconomicInputSpec:
    """Complete numerical economic input set needed before Table 4 solving."""

    volume_distribution: DiscreteVolumeDistribution
    fare_rates: FareClassRates
    distance_inputs: tuple[DistanceEconomicInput, ...]
    reproduction_class: str = CONTROLLED_SUBSTITUTE_INPUT

    def __post_init__(self) -> None:
        """Validate one complete Table 4 economic specification."""
        if not isinstance(
            self.volume_distribution,
            DiscreteVolumeDistribution,
        ):
            raise TypeError("volume_distribution must be a DiscreteVolumeDistribution.")

        if not isinstance(
            self.fare_rates,
            FareClassRates,
        ):
            raise TypeError("fare_rates must be FareClassRates.")

        if not isinstance(
            self.distance_inputs,
            tuple,
        ):
            raise TypeError("distance_inputs must be a tuple.")

        if len(self.distance_inputs) != 4:
            raise ValueError("Economic inputs are required for corridor distances 1, 2, 3 and 4.")

        by_distance: dict[
            int,
            DistanceEconomicInput,
        ] = {}

        for item in self.distance_inputs:
            if not isinstance(
                item,
                DistanceEconomicInput,
            ):
                raise TypeError("Every distance input must be a DistanceEconomicInput.")

            if item.distance in by_distance:
                raise ValueError("Distance economic inputs must be unique.")

            by_distance[item.distance] = item

        if set(by_distance) != {1, 2, 3, 4}:
            raise ValueError("Economic inputs must cover distances 1, 2, 3 and 4.")

        if self.reproduction_class not in {
            CONTROLLED_SUBSTITUTE_INPUT,
            PUBLISHED_STRUCTURE,
        }:
            raise ValueError("Unsupported economic-input reproduction class.")

        object.__setattr__(
            self,
            "distance_inputs",
            tuple(by_distance[distance] for distance in (1, 2, 3, 4)),
        )

    def input_for_distance(
        self,
        distance: int,
    ) -> DistanceEconomicInput:
        """Return the economic inputs for one corridor distance."""
        selected = _validate_positive_integer(
            "distance",
            distance,
        )

        for item in self.distance_inputs:
            if item.distance == selected:
                return item

        raise KeyError(f"No economic input for distance {selected}.")

    def fare_per_teu_for_classes(
        self,
        *,
        distance: int,
        early_reservation: bool,
        standard_delivery: bool,
    ) -> float:
        """Apply the paper's multiplicative fare equation.

        This method deliberately accepts already classified timing
        classes. Mapping numerical timing values into those classes is
        kept separate because the paper does not disclose the thresholds.
        """
        if not isinstance(
            early_reservation,
            bool,
        ):
            raise TypeError("early_reservation must be a boolean.")

        if not isinstance(
            standard_delivery,
            bool,
        ):
            raise TypeError("standard_delivery must be a boolean.")

        distance_input = self.input_for_distance(distance)

        anticipation_rate = (
            self.fare_rates.early_reservation_rate
            if early_reservation
            else self.fare_rates.late_reservation_rate
        )

        delivery_rate = (
            self.fare_rates.standard_delivery_rate
            if standard_delivery
            else self.fare_rates.express_delivery_rate
        )

        return float(distance_input.base_fare_per_teu * anticipation_rate * delivery_rate)


def table4_economic_input_fingerprint(
    spec: Table4EconomicInputSpec,
) -> str:
    """Return deterministic SHA-256 of all economic inputs."""
    if not isinstance(
        spec,
        Table4EconomicInputSpec,
    ):
        raise TypeError("spec must be a Table4EconomicInputSpec.")

    payload = json.dumps(
        asdict(spec),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return sha256(payload.encode("utf-8")).hexdigest()
