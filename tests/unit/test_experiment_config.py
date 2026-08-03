"""Tests for experiment configuration loading and validation."""

from pathlib import Path

import pytest

from barge_rerouting.config import (
    ConfigurationError,
    CustomerMix,
    load_experiment_config,
)
from barge_rerouting.domain import CustomerCategory


def test_toy_configuration_loads_successfully() -> None:
    """The committed toy experiment must be valid."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))

    assert config.experiment_name == "toy-baseline"
    assert config.random_seed == 20260802

    assert config.network.terminals == ("A", "B", "C")
    assert config.network.horizon_start == 0
    assert config.network.horizon_end == 6
    assert len(config.network.transport_legs) == 6

    assert config.demand_generation.number_of_demands == 20
    assert config.solver.time_limit_seconds == pytest.approx(60.0)


def test_customer_mix_returns_category_probabilities() -> None:
    """Customer mix must expose probabilities by domain category."""
    mix = CustomerMix(
        regular_probability=0.30,
        partially_spot_probability=0.40,
        fully_spot_probability=0.30,
    )

    assert mix.probability_for(CustomerCategory.REGULAR) == pytest.approx(0.30)

    assert mix.probability_for(CustomerCategory.PARTIALLY_SPOT) == pytest.approx(0.40)

    assert mix.probability_for(CustomerCategory.FULLY_SPOT) == pytest.approx(0.30)


def test_customer_mix_must_sum_to_one() -> None:
    """Category generation probabilities must form a distribution."""
    with pytest.raises(ValueError, match="sum to one"):
        CustomerMix(
            regular_probability=0.20,
            partially_spot_probability=0.20,
            fully_spot_probability=0.20,
        )


def test_missing_configuration_file_is_rejected() -> None:
    """A nonexistent configuration path must produce a clear error."""
    with pytest.raises(ConfigurationError, match="does not exist"):
        load_experiment_config("configs/does-not-exist.yaml")


def test_missing_required_section_is_rejected(
    tmp_path: Path,
) -> None:
    """Every top-level configuration section is required."""
    config_path = tmp_path / "missing-solver.yaml"
    config_path.write_text(
        """
experiment:
  name: invalid
  random_seed: 1
network: {}
demand_generation: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="solver"):
        load_experiment_config(config_path)


def test_invalid_yaml_is_rejected(tmp_path: Path) -> None:
    """Malformed YAML must produce a configuration error."""
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(
        "experiment: [unterminated",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Invalid YAML"):
        load_experiment_config(config_path)


def test_ranges_cannot_generate_due_time_beyond_horizon(
    tmp_path: Path,
) -> None:
    """Generation ranges must remain within the configured horizon."""
    source = Path("configs/toy_experiment.yaml").read_text(encoding="utf-8")
    invalid = source.replace(
        "maximum_due_slack: 3",
        "maximum_due_slack: 10",
    )

    config_path = tmp_path / "invalid-horizon.yaml"
    config_path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="beyond the network horizon"):
        load_experiment_config(config_path)


def test_unknown_service_terminal_is_rejected(
    tmp_path: Path,
) -> None:
    """Every service terminal must belong to the configured network."""
    source = Path("configs/toy_experiment.yaml").read_text(encoding="utf-8")
    invalid = source.replace(
        "origin: A",
        "origin: Z",
        1,
    )

    config_path = tmp_path / "unknown-terminal.yaml"
    config_path.write_text(invalid, encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown configured leg origin"):
        load_experiment_config(config_path)
