"""Validated experiment-configuration domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite

from barge_rerouting.domain import CustomerCategory, ScheduledTransportLeg

PROBABILITY_TOLERANCE = 1e-9


def _validate_integer(
    name: str,
    value: object,
    *,
    minimum: int = 0,
) -> int:
    """Validate and return an integer with a lower bound."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")

    return value


def _validate_number(
    name: str,
    value: object,
    *,
    minimum: float = 0.0,
) -> float:
    """Validate and return a finite number with a lower bound."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")

    numeric_value = float(value)

    if not isfinite(numeric_value):
        raise ValueError(f"{name} must be finite.")

    if numeric_value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")

    return numeric_value


@dataclass(frozen=True, slots=True)
class CustomerMix:
    """Probabilities used to generate customer categories."""

    regular_probability: float
    partially_spot_probability: float
    fully_spot_probability: float

    def __post_init__(self) -> None:
        """Validate and normalise category probabilities."""
        regular = _validate_number(
            "regular_probability",
            self.regular_probability,
        )
        partially_spot = _validate_number(
            "partially_spot_probability",
            self.partially_spot_probability,
        )
        fully_spot = _validate_number(
            "fully_spot_probability",
            self.fully_spot_probability,
        )

        probabilities = (regular, partially_spot, fully_spot)

        if any(probability > 1.0 for probability in probabilities):
            raise ValueError("Customer-category probabilities cannot exceed one.")

        total_probability = regular + partially_spot + fully_spot

        if not isclose(
            total_probability,
            1.0,
            rel_tol=0.0,
            abs_tol=PROBABILITY_TOLERANCE,
        ):
            raise ValueError(
                f"Customer-category probabilities must sum to one; received {total_probability}."
            )

        object.__setattr__(self, "regular_probability", regular)
        object.__setattr__(
            self,
            "partially_spot_probability",
            partially_spot,
        )
        object.__setattr__(self, "fully_spot_probability", fully_spot)

    def probability_for(self, category: CustomerCategory) -> float:
        """Return the generation probability for one customer category."""
        if category is CustomerCategory.REGULAR:
            return self.regular_probability

        if category is CustomerCategory.PARTIALLY_SPOT:
            return self.partially_spot_probability

        if category is CustomerCategory.FULLY_SPOT:
            return self.fully_spot_probability

        raise ValueError(f"Unsupported customer category: {category}")


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    """Physical and scheduled-network experiment configuration."""

    terminals: tuple[str, ...]
    time_periods: tuple[int, ...]
    transport_legs: tuple[ScheduledTransportLeg, ...]
    add_holding_arcs: bool = True

    def __post_init__(self) -> None:
        """Validate the configured network."""
        if not isinstance(self.terminals, tuple):
            raise TypeError("terminals must be a tuple.")

        if not isinstance(self.time_periods, tuple):
            raise TypeError("time_periods must be a tuple.")

        if not isinstance(self.transport_legs, tuple):
            raise TypeError("transport_legs must be a tuple.")

        if not isinstance(self.add_holding_arcs, bool):
            raise TypeError("add_holding_arcs must be a boolean.")

        terminals: list[str] = []

        for terminal in self.terminals:
            if not isinstance(terminal, str):
                raise TypeError("Every terminal must be a string.")

            normalised_terminal = terminal.strip()

            if not normalised_terminal:
                raise ValueError("Terminal names must be non-empty.")

            terminals.append(normalised_terminal)

        if len(terminals) < 2:
            raise ValueError("At least two terminals are required.")

        if len(set(terminals)) != len(terminals):
            raise ValueError("Terminal names must be unique.")

        time_periods = tuple(_validate_integer("time_period", value) for value in self.time_periods)

        if len(time_periods) < 2:
            raise ValueError("At least two time periods are required.")

        if len(set(time_periods)) != len(time_periods):
            raise ValueError("Time periods must be unique.")

        if tuple(sorted(time_periods)) != time_periods:
            raise ValueError("Time periods must be sorted in ascending order.")

        terminal_set = set(terminals)
        time_set = set(time_periods)

        for leg in self.transport_legs:
            if not isinstance(leg, ScheduledTransportLeg):
                raise TypeError("Every transport leg must be a ScheduledTransportLeg.")

            if leg.origin not in terminal_set:
                raise ValueError(f"Unknown configured leg origin: {leg.origin}")

            if leg.destination not in terminal_set:
                raise ValueError(f"Unknown configured leg destination: {leg.destination}")

            if leg.departure_time not in time_set:
                raise ValueError(f"Unknown configured departure time: {leg.departure_time}")

            if leg.arrival_time not in time_set:
                raise ValueError(f"Unknown configured arrival time: {leg.arrival_time}")

        object.__setattr__(self, "terminals", tuple(terminals))
        object.__setattr__(self, "time_periods", time_periods)

    @property
    def horizon_start(self) -> int:
        """Return the first configured time point."""
        return int(self.time_periods[0])

    @property
    def horizon_end(self) -> int:
        """Return the final configured time point."""
        return int(self.time_periods[-1])


@dataclass(frozen=True, slots=True)
class DemandGenerationConfig:
    """Rules for deterministic synthetic-demand generation."""

    number_of_demands: int
    minimum_volume: int
    maximum_volume: int
    minimum_fare_per_teu: float
    maximum_fare_per_teu: float
    minimum_reservation_time: int
    maximum_reservation_time: int
    minimum_availability_lag: int
    maximum_availability_lag: int
    minimum_due_slack: int
    maximum_due_slack: int
    customer_mix: CustomerMix

    def __post_init__(self) -> None:
        """Validate all demand-generation ranges."""
        number_of_demands = _validate_integer(
            "number_of_demands",
            self.number_of_demands,
            minimum=1,
        )
        minimum_volume = _validate_integer(
            "minimum_volume",
            self.minimum_volume,
            minimum=1,
        )
        maximum_volume = _validate_integer(
            "maximum_volume",
            self.maximum_volume,
            minimum=1,
        )
        minimum_fare = _validate_number(
            "minimum_fare_per_teu",
            self.minimum_fare_per_teu,
        )
        maximum_fare = _validate_number(
            "maximum_fare_per_teu",
            self.maximum_fare_per_teu,
        )
        minimum_reservation = _validate_integer(
            "minimum_reservation_time",
            self.minimum_reservation_time,
        )
        maximum_reservation = _validate_integer(
            "maximum_reservation_time",
            self.maximum_reservation_time,
        )
        minimum_availability_lag = _validate_integer(
            "minimum_availability_lag",
            self.minimum_availability_lag,
        )
        maximum_availability_lag = _validate_integer(
            "maximum_availability_lag",
            self.maximum_availability_lag,
        )
        minimum_due_slack = _validate_integer(
            "minimum_due_slack",
            self.minimum_due_slack,
            minimum=1,
        )
        maximum_due_slack = _validate_integer(
            "maximum_due_slack",
            self.maximum_due_slack,
            minimum=1,
        )

        if maximum_volume < minimum_volume:
            raise ValueError("maximum_volume must not be below minimum_volume.")

        if maximum_fare < minimum_fare:
            raise ValueError("maximum_fare_per_teu must not be below minimum_fare_per_teu.")

        if maximum_reservation < minimum_reservation:
            raise ValueError("maximum_reservation_time must not be below minimum_reservation_time.")

        if maximum_availability_lag < minimum_availability_lag:
            raise ValueError("maximum_availability_lag must not be below minimum_availability_lag.")

        if maximum_due_slack < minimum_due_slack:
            raise ValueError("maximum_due_slack must not be below minimum_due_slack.")

        if not isinstance(self.customer_mix, CustomerMix):
            raise TypeError("customer_mix must be a CustomerMix object.")

        object.__setattr__(self, "number_of_demands", number_of_demands)
        object.__setattr__(self, "minimum_volume", minimum_volume)
        object.__setattr__(self, "maximum_volume", maximum_volume)
        object.__setattr__(self, "minimum_fare_per_teu", minimum_fare)
        object.__setattr__(self, "maximum_fare_per_teu", maximum_fare)
        object.__setattr__(
            self,
            "minimum_reservation_time",
            minimum_reservation,
        )
        object.__setattr__(
            self,
            "maximum_reservation_time",
            maximum_reservation,
        )
        object.__setattr__(
            self,
            "minimum_availability_lag",
            minimum_availability_lag,
        )
        object.__setattr__(
            self,
            "maximum_availability_lag",
            maximum_availability_lag,
        )
        object.__setattr__(
            self,
            "minimum_due_slack",
            minimum_due_slack,
        )
        object.__setattr__(
            self,
            "maximum_due_slack",
            maximum_due_slack,
        )


@dataclass(frozen=True, slots=True)
class SolverConfig:
    """Solver controls that affect experiment execution."""

    time_limit_seconds: float
    relative_mip_gap: float
    log_output: bool

    def __post_init__(self) -> None:
        """Validate solver controls."""
        time_limit = _validate_number(
            "time_limit_seconds",
            self.time_limit_seconds,
            minimum=0.001,
        )
        relative_mip_gap = _validate_number(
            "relative_mip_gap",
            self.relative_mip_gap,
        )

        if relative_mip_gap > 1.0:
            raise ValueError("relative_mip_gap must not exceed one.")

        if not isinstance(self.log_output, bool):
            raise TypeError("log_output must be a boolean.")

        object.__setattr__(self, "time_limit_seconds", time_limit)
        object.__setattr__(self, "relative_mip_gap", relative_mip_gap)


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Complete validated experiment configuration."""

    experiment_name: str
    random_seed: int
    network: NetworkConfig
    demand_generation: DemandGenerationConfig
    solver: SolverConfig

    def __post_init__(self) -> None:
        """Validate experiment-level and cross-section consistency."""
        if not isinstance(self.experiment_name, str):
            raise TypeError("experiment_name must be a string.")

        experiment_name = self.experiment_name.strip()

        if not experiment_name:
            raise ValueError("experiment_name must be non-empty.")

        random_seed = _validate_integer("random_seed", self.random_seed)

        if not isinstance(self.network, NetworkConfig):
            raise TypeError("network must be a NetworkConfig.")

        if not isinstance(
            self.demand_generation,
            DemandGenerationConfig,
        ):
            raise TypeError("demand_generation must be a DemandGenerationConfig.")

        if not isinstance(self.solver, SolverConfig):
            raise TypeError("solver must be a SolverConfig.")

        generation = self.demand_generation

        latest_possible_due_time = (
            generation.maximum_reservation_time
            + generation.maximum_availability_lag
            + generation.maximum_due_slack
        )

        if generation.minimum_reservation_time < self.network.horizon_start:
            raise ValueError("Demand reservation times cannot precede the network horizon.")

        if latest_possible_due_time > self.network.horizon_end:
            raise ValueError(
                "Demand-generation ranges can produce a due time beyond the network horizon."
            )

        object.__setattr__(self, "experiment_name", experiment_name)
        object.__setattr__(self, "random_seed", random_seed)
