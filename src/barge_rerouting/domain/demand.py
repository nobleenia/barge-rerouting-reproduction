"""Validated demand and customer-category domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class AcceptanceVariableType(StrEnum):
    """Mathematical type of a customer's acceptance decision."""

    FIXED = "fixed"
    CONTINUOUS = "continuous"
    BINARY = "binary"


class CustomerCategory(StrEnum):
    """Customer categories used by the demand-allocation model."""

    REGULAR = "R"
    PARTIALLY_SPOT = "P"
    FULLY_SPOT = "F"

    @property
    def acceptance_variable_type(self) -> AcceptanceVariableType:
        """Return the required mathematical acceptance-variable type."""
        mapping = {
            CustomerCategory.REGULAR: AcceptanceVariableType.FIXED,
            CustomerCategory.PARTIALLY_SPOT: AcceptanceVariableType.CONTINUOUS,
            CustomerCategory.FULLY_SPOT: AcceptanceVariableType.BINARY,
        }
        return mapping[self]

    @property
    def requires_full_acceptance(self) -> bool:
        """Return whether every requested TEU must be accepted."""
        return self is CustomerCategory.REGULAR

    @property
    def allows_partial_acceptance(self) -> bool:
        """Return whether a fractional acceptance decision is permitted."""
        return self is CustomerCategory.PARTIALLY_SPOT

    @property
    def requires_binary_acceptance(self) -> bool:
        """Return whether acceptance must be zero or one."""
        return self is CustomerCategory.FULLY_SPOT


def _validate_nonnegative_integer(name: str, value: object) -> int:
    """Validate and return a nonnegative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_finite_number(
    name: str,
    value: object,
    *,
    strictly_positive: bool = False,
) -> float:
    """Validate and return a finite floating-point number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if strictly_positive and numeric_value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    if not strictly_positive and numeric_value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class Demand:
    """One transportation request presented to the booking system.

    Attributes:
        demand_id:
            Unique request identifier.
        volume:
            Requested quantity in TEU.
        origin:
            Physical origin terminal.
        destination:
            Physical destination terminal.
        reservation_time:
            Time at which the request becomes known to the operator.
        availability_time:
            Earliest time at which cargo can enter the network.
        due_time:
            Latest acceptable arrival time at the destination.
        category:
            Regular, partially-spot, or fully-spot customer category.
        fare_per_teu:
            Revenue obtained per accepted TEU.
    """

    demand_id: str
    volume: float
    origin: str
    destination: str
    reservation_time: int
    availability_time: int
    due_time: int
    category: CustomerCategory
    fare_per_teu: float

    def __post_init__(self) -> None:
        """Validate and normalise all demand attributes."""
        if not isinstance(self.demand_id, str):
            raise TypeError("demand_id must be a string.")
        if not isinstance(self.origin, str):
            raise TypeError("origin must be a string.")
        if not isinstance(self.destination, str):
            raise TypeError("destination must be a string.")
        if not isinstance(self.category, CustomerCategory):
            raise TypeError("category must be a CustomerCategory.")

        demand_id = self.demand_id.strip()
        origin = self.origin.strip()
        destination = self.destination.strip()

        if not demand_id:
            raise ValueError("demand_id must be non-empty.")
        if not origin:
            raise ValueError("origin must be non-empty.")
        if not destination:
            raise ValueError("destination must be non-empty.")
        if origin == destination:
            raise ValueError("origin and destination must be different.")

        volume = _validate_finite_number(
            "volume",
            self.volume,
            strictly_positive=True,
        )
        fare_per_teu = _validate_finite_number(
            "fare_per_teu",
            self.fare_per_teu,
        )

        reservation_time = _validate_nonnegative_integer(
            "reservation_time",
            self.reservation_time,
        )
        availability_time = _validate_nonnegative_integer(
            "availability_time",
            self.availability_time,
        )
        due_time = _validate_nonnegative_integer(
            "due_time",
            self.due_time,
        )

        if reservation_time > availability_time:
            raise ValueError("reservation_time must not be later than availability_time.")

        if availability_time > due_time:
            raise ValueError("availability_time must not be later than due_time.")

        object.__setattr__(self, "demand_id", demand_id)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "destination", destination)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "fare_per_teu", fare_per_teu)
        object.__setattr__(self, "reservation_time", reservation_time)
        object.__setattr__(self, "availability_time", availability_time)
        object.__setattr__(self, "due_time", due_time)

    @property
    def maximum_revenue(self) -> float:
        """Return revenue obtained if the full request is accepted."""
        return self.volume * self.fare_per_teu

    def normalize_acceptance_fraction(
        self,
        acceptance_fraction: float,
        *,
        tolerance: float = 1e-9,
    ) -> float:
        """Validate an acceptance fraction against the customer category.

        Args:
            acceptance_fraction:
                Proposed accepted proportion between zero and one.
            tolerance:
                Numerical tolerance used near zero and one.

        Returns:
            A validated fraction, normalised to exactly zero or one when it is
            within tolerance of either endpoint.

        Raises:
            ValueError:
                If the fraction violates its numerical bounds or category rule.
        """
        tolerance_value = _validate_finite_number(
            "tolerance",
            tolerance,
            strictly_positive=True,
        )
        fraction = _validate_finite_number(
            "acceptance_fraction",
            acceptance_fraction,
        )

        if fraction > 1.0 + tolerance_value:
            raise ValueError("acceptance_fraction must not exceed one.")

        if abs(fraction) <= tolerance_value:
            fraction = 0.0
        elif abs(fraction - 1.0) <= tolerance_value:
            fraction = 1.0

        if self.category is CustomerCategory.REGULAR and fraction != 1.0:
            raise ValueError("Regular demand must be fully accepted.")

        if self.category is CustomerCategory.FULLY_SPOT and fraction not in {0.0, 1.0}:
            raise ValueError("Fully-spot demand must be either fully accepted or rejected.")

        return fraction

    def accepted_volume(self, acceptance_fraction: float) -> float:
        """Return accepted TEU after validating the acceptance decision."""
        fraction = self.normalize_acceptance_fraction(acceptance_fraction)
        return self.volume * fraction

    def accepted_revenue(self, acceptance_fraction: float) -> float:
        """Return revenue associated with a valid acceptance decision."""
        fraction = self.normalize_acceptance_fraction(acceptance_fraction)
        return self.maximum_revenue * fraction
