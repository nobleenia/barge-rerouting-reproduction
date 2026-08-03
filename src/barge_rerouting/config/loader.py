"""Loading and validation of YAML experiment configurations."""

from __future__ import annotations

from pathlib import Path

import yaml

from barge_rerouting.config.model import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    NetworkConfig,
    SolverConfig,
)
from barge_rerouting.domain import ScheduledTransportLeg


class ConfigurationError(ValueError):
    """Raised when a configuration file cannot be interpreted."""


def _as_mapping(value: object, context: str) -> dict[str, object]:
    """Validate and return a string-keyed mapping."""
    if not isinstance(value, dict):
        raise ConfigurationError(f"{context} must be a mapping.")

    result: dict[str, object] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise ConfigurationError(f"Every key in {context} must be a string.")

        result[key] = item

    return result


def _as_sequence(value: object, context: str) -> tuple[object, ...]:
    """Validate and return a sequence that is not text."""
    if not isinstance(value, (list, tuple)):
        raise ConfigurationError(f"{context} must be a sequence.")

    return tuple(value)


def _required(
    mapping: dict[str, object],
    key: str,
    context: str,
) -> object:
    """Return one required configuration value."""
    if key not in mapping:
        raise ConfigurationError(f"Missing required key '{key}' in {context}.")

    return mapping[key]


def _as_string(value: object, context: str) -> str:
    """Validate and return a string."""
    if not isinstance(value, str):
        raise ConfigurationError(f"{context} must be a string.")

    return value


def _as_integer(value: object, context: str) -> int:
    """Validate and return an integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{context} must be an integer.")

    return value


def _as_number(value: object, context: str) -> float:
    """Validate and return a real number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{context} must be a real number.")

    return float(value)


def _as_boolean(value: object, context: str) -> bool:
    """Validate and return a boolean."""
    if not isinstance(value, bool):
        raise ConfigurationError(f"{context} must be a boolean.")

    return value


def _parse_transport_legs(
    value: object,
) -> tuple[ScheduledTransportLeg, ...]:
    """Parse scheduled transport legs from YAML values."""
    raw_legs = _as_sequence(value, "network.transport_legs")
    legs: list[ScheduledTransportLeg] = []

    for index, raw_leg in enumerate(raw_legs):
        context = f"network.transport_legs[{index}]"
        leg = _as_mapping(raw_leg, context)

        legs.append(
            ScheduledTransportLeg(
                service_id=_as_string(
                    _required(leg, "service_id", context),
                    f"{context}.service_id",
                ),
                origin=_as_string(
                    _required(leg, "origin", context),
                    f"{context}.origin",
                ),
                destination=_as_string(
                    _required(leg, "destination", context),
                    f"{context}.destination",
                ),
                departure_time=_as_integer(
                    _required(leg, "departure_time", context),
                    f"{context}.departure_time",
                ),
                arrival_time=_as_integer(
                    _required(leg, "arrival_time", context),
                    f"{context}.arrival_time",
                ),
                capacity=_as_number(
                    _required(leg, "capacity", context),
                    f"{context}.capacity",
                ),
                direction=_as_string(
                    leg.get("direction", "unspecified"),
                    f"{context}.direction",
                ),
            )
        )

    return tuple(legs)


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load and validate one YAML experiment configuration."""
    config_path = Path(path)

    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {config_path}")

    try:
        raw_data: object = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in configuration file: {config_path}") from error

    root = _as_mapping(raw_data, "configuration root")

    experiment = _as_mapping(
        _required(root, "experiment", "configuration root"),
        "experiment",
    )
    network = _as_mapping(
        _required(root, "network", "configuration root"),
        "network",
    )
    generation = _as_mapping(
        _required(root, "demand_generation", "configuration root"),
        "demand_generation",
    )
    solver = _as_mapping(
        _required(root, "solver", "configuration root"),
        "solver",
    )
    customer_mix = _as_mapping(
        _required(
            generation,
            "customer_mix",
            "demand_generation",
        ),
        "demand_generation.customer_mix",
    )

    terminal_values = _as_sequence(
        _required(network, "terminals", "network"),
        "network.terminals",
    )
    time_values = _as_sequence(
        _required(network, "time_periods", "network"),
        "network.time_periods",
    )

    return ExperimentConfig(
        experiment_name=_as_string(
            _required(experiment, "name", "experiment"),
            "experiment.name",
        ),
        random_seed=_as_integer(
            _required(experiment, "random_seed", "experiment"),
            "experiment.random_seed",
        ),
        network=NetworkConfig(
            terminals=tuple(
                _as_string(value, "network.terminals item") for value in terminal_values
            ),
            time_periods=tuple(
                _as_integer(value, "network.time_periods item") for value in time_values
            ),
            transport_legs=_parse_transport_legs(_required(network, "transport_legs", "network")),
            add_holding_arcs=_as_boolean(
                network.get("add_holding_arcs", True),
                "network.add_holding_arcs",
            ),
        ),
        demand_generation=DemandGenerationConfig(
            number_of_demands=_as_integer(
                _required(
                    generation,
                    "number_of_demands",
                    "demand_generation",
                ),
                "demand_generation.number_of_demands",
            ),
            minimum_volume=_as_integer(
                _required(
                    generation,
                    "minimum_volume",
                    "demand_generation",
                ),
                "demand_generation.minimum_volume",
            ),
            maximum_volume=_as_integer(
                _required(
                    generation,
                    "maximum_volume",
                    "demand_generation",
                ),
                "demand_generation.maximum_volume",
            ),
            minimum_fare_per_teu=_as_number(
                _required(
                    generation,
                    "minimum_fare_per_teu",
                    "demand_generation",
                ),
                "demand_generation.minimum_fare_per_teu",
            ),
            maximum_fare_per_teu=_as_number(
                _required(
                    generation,
                    "maximum_fare_per_teu",
                    "demand_generation",
                ),
                "demand_generation.maximum_fare_per_teu",
            ),
            minimum_reservation_time=_as_integer(
                _required(
                    generation,
                    "minimum_reservation_time",
                    "demand_generation",
                ),
                "demand_generation.minimum_reservation_time",
            ),
            maximum_reservation_time=_as_integer(
                _required(
                    generation,
                    "maximum_reservation_time",
                    "demand_generation",
                ),
                "demand_generation.maximum_reservation_time",
            ),
            minimum_availability_lag=_as_integer(
                _required(
                    generation,
                    "minimum_availability_lag",
                    "demand_generation",
                ),
                "demand_generation.minimum_availability_lag",
            ),
            maximum_availability_lag=_as_integer(
                _required(
                    generation,
                    "maximum_availability_lag",
                    "demand_generation",
                ),
                "demand_generation.maximum_availability_lag",
            ),
            minimum_due_slack=_as_integer(
                _required(
                    generation,
                    "minimum_due_slack",
                    "demand_generation",
                ),
                "demand_generation.minimum_due_slack",
            ),
            maximum_due_slack=_as_integer(
                _required(
                    generation,
                    "maximum_due_slack",
                    "demand_generation",
                ),
                "demand_generation.maximum_due_slack",
            ),
            customer_mix=CustomerMix(
                regular_probability=_as_number(
                    _required(customer_mix, "R", "customer_mix"),
                    "demand_generation.customer_mix.R",
                ),
                partially_spot_probability=_as_number(
                    _required(customer_mix, "P", "customer_mix"),
                    "demand_generation.customer_mix.P",
                ),
                fully_spot_probability=_as_number(
                    _required(customer_mix, "F", "customer_mix"),
                    "demand_generation.customer_mix.F",
                ),
            ),
        ),
        solver=SolverConfig(
            time_limit_seconds=_as_number(
                _required(
                    solver,
                    "time_limit_seconds",
                    "solver",
                ),
                "solver.time_limit_seconds",
            ),
            relative_mip_gap=_as_number(
                _required(
                    solver,
                    "relative_mip_gap",
                    "solver",
                ),
                "solver.relative_mip_gap",
            ),
            log_output=_as_boolean(
                _required(solver, "log_output", "solver"),
                "solver.log_output",
            ),
        ),
    )
