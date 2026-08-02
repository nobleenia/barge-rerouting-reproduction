"""Validated discrete future-demand probability distributions."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite

from barge_rerouting.domain.demand import CustomerCategory

PROBABILITY_TOLERANCE = 1e-9


def _validate_nonnegative_integer(name: str, value: object) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_nonnegative_finite_number(
    name: str,
    value: object,
) -> float:
    """Validate and return a nonnegative finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class VolumeProbability:
    """One possible future volume and its probability."""

    volume: int
    probability: float

    def __post_init__(self) -> None:
        """Validate and normalise the outcome."""
        volume = _validate_nonnegative_integer("volume", self.volume)
        probability = _validate_nonnegative_finite_number(
            "probability",
            self.probability,
        )

        if probability > 1.0:
            raise ValueError("probability must not exceed one.")

        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "probability", probability)


@dataclass(frozen=True, slots=True)
class FutureDemandForecast:
    """Discrete probability distribution for one future demand class.

    Attributes:
        forecast_id:
            Unique identifier for the future demand class.
        origin:
            Physical origin terminal.
        destination:
            Physical destination terminal.
        availability_time:
            Earliest possible cargo availability time.
        due_time:
            Latest permitted destination-arrival time.
        category:
            Customer category associated with the forecast.
        fare_per_teu:
            Revenue per realised and accepted TEU.
        outcomes:
            Discrete future-volume probability distribution.
    """

    forecast_id: str
    origin: str
    destination: str
    availability_time: int
    due_time: int
    category: CustomerCategory
    fare_per_teu: float
    outcomes: tuple[VolumeProbability, ...]

    def __post_init__(self) -> None:
        """Validate and normalise the forecast."""
        if not isinstance(self.forecast_id, str):
            raise TypeError("forecast_id must be a string.")
        if not isinstance(self.origin, str):
            raise TypeError("origin must be a string.")
        if not isinstance(self.destination, str):
            raise TypeError("destination must be a string.")
        if not isinstance(self.category, CustomerCategory):
            raise TypeError("category must be a CustomerCategory.")
        if not isinstance(self.outcomes, tuple):
            raise TypeError("outcomes must be a tuple.")

        forecast_id = self.forecast_id.strip()
        origin = self.origin.strip()
        destination = self.destination.strip()

        if not forecast_id:
            raise ValueError("forecast_id must be non-empty.")
        if not origin:
            raise ValueError("origin must be non-empty.")
        if not destination:
            raise ValueError("destination must be non-empty.")
        if origin == destination:
            raise ValueError("origin and destination must be different.")

        availability_time = _validate_nonnegative_integer(
            "availability_time",
            self.availability_time,
        )
        due_time = _validate_nonnegative_integer(
            "due_time",
            self.due_time,
        )

        if due_time < availability_time:
            raise ValueError("due_time must not be earlier than availability_time.")

        fare_per_teu = _validate_nonnegative_finite_number(
            "fare_per_teu",
            self.fare_per_teu,
        )

        if not self.outcomes:
            raise ValueError("At least one future-volume outcome is required.")

        for outcome in self.outcomes:
            if not isinstance(outcome, VolumeProbability):
                raise TypeError("Every forecast outcome must be a VolumeProbability object.")

        ordered_outcomes = tuple(
            sorted(
                self.outcomes,
                key=lambda outcome: outcome.volume,
            )
        )

        volumes = [outcome.volume for outcome in ordered_outcomes]

        if len(set(volumes)) != len(volumes):
            raise ValueError("Future-volume outcomes must have unique volumes.")

        total_probability: float = 0.0

        for outcome in ordered_outcomes:
            total_probability += float(outcome.probability)

        if not isclose(
            total_probability,
            1.0,
            rel_tol=0.0,
            abs_tol=PROBABILITY_TOLERANCE,
        ):
            raise ValueError(
                f"Future-demand probabilities must sum to one; received {total_probability}."
            )

        object.__setattr__(self, "forecast_id", forecast_id)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "availability_time", availability_time)
        object.__setattr__(self, "due_time", due_time)
        object.__setattr__(self, "fare_per_teu", fare_per_teu)
        object.__setattr__(self, "outcomes", ordered_outcomes)

    @property
    def support(self) -> tuple[int, ...]:
        """Return possible future-volume values in ascending order."""
        return tuple(outcome.volume for outcome in self.outcomes)

    @property
    def maximum_volume(self) -> int:
        """Return the largest possible future volume."""
        return int(self.outcomes[-1].volume)

    @property
    def candidate_protection_levels(self) -> tuple[int, ...]:
        """Return candidate protection levels from zero to maximum volume."""
        return tuple(range(self.maximum_volume + 1))

    @property
    def expected_volume(self) -> float:
        """Return the ordinary expected future volume E[X]."""
        expectation: float = 0.0

        for outcome in self.outcomes:
            expectation += float(outcome.volume) * float(outcome.probability)

        return expectation

    @property
    def expected_full_revenue(self) -> float:
        """Return expected revenue if all realised volume can be accepted."""
        return self.expected_volume * self.fare_per_teu

    def probability_of(self, volume: int) -> float:
        """Return the probability of one volume, or zero when unsupported."""
        validated_volume = _validate_nonnegative_integer("volume", volume)

        for outcome in self.outcomes:
            if outcome.volume == validated_volume:
                return float(outcome.probability)

        return 0.0

    def tail_probability_above(self, protection_level: int) -> float:
        """Return P(X > j) for protection level j."""
        level = _validate_nonnegative_integer(
            "protection_level",
            protection_level,
        )
        probability: float = 0.0

        for outcome in self.outcomes:
            if outcome.volume > level:
                probability += float(outcome.probability)

        return probability

    def paper_prefix_expected_volume(
        self,
        protection_level: int,
    ) -> float:
        """Return the paper's printed prefix expression.

        This computes:

            sum_{x=0}^{j} x P(X=x).

        Outcomes above j contribute zero to this expression.
        """
        level = _validate_nonnegative_integer(
            "protection_level",
            protection_level,
        )
        value: float = 0.0

        for outcome in self.outcomes:
            if outcome.volume <= level:
                value += float(outcome.volume) * float(outcome.probability)

        return value

    def expected_capped_volume(
        self,
        protection_level: int,
    ) -> float:
        """Return E[min(X, j)] for protection level j."""
        level = _validate_nonnegative_integer(
            "protection_level",
            protection_level,
        )
        value: float = 0.0

        for outcome in self.outcomes:
            capped_volume = min(outcome.volume, level)
            value += float(capped_volume) * float(outcome.probability)

        return value
