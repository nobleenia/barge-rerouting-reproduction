"""Tests for deterministic synthetic-demand generation."""

from dataclasses import replace
from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.generation import (
    demand_fingerprint,
    enumerate_feasible_demand_templates,
    generate_demands,
    write_demands_csv,
)
from barge_rerouting.network.feasibility import (
    extract_demand_feasible_network,
)
from barge_rerouting.network.time_space import build_time_space_network


def load_toy_config():
    """Load the committed toy configuration."""
    return load_experiment_config(Path("configs/toy_experiment.yaml"))


def test_same_configuration_and_seed_produce_identical_demands() -> None:
    """Repeated generation with one seed must be exactly reproducible."""
    config = load_toy_config()

    first = generate_demands(config)
    second = generate_demands(config)

    assert first == second
    assert demand_fingerprint(first) == demand_fingerprint(second)


def test_different_seed_changes_generated_instance() -> None:
    """A controlled seed change should produce a different instance."""
    config = load_toy_config()

    baseline = generate_demands(config)
    alternative = generate_demands(
        config,
        random_seed=config.random_seed + 1,
    )

    assert baseline != alternative
    assert demand_fingerprint(baseline) != demand_fingerprint(alternative)


def test_generator_creates_requested_count_and_unique_identifiers() -> None:
    """Generated demand IDs must be unique and deterministically ordered."""
    config = load_toy_config()
    demands = generate_demands(config)

    assert len(demands) == config.demand_generation.number_of_demands
    assert demands[0].demand_id == "K0001"
    assert demands[-1].demand_id == "K0020"

    identifiers = [demand.demand_id for demand in demands]

    assert len(set(identifiers)) == len(identifiers)


def test_generated_values_respect_configured_ranges() -> None:
    """Every generated value must satisfy the configured generation ranges."""
    config = load_toy_config()
    generation = config.demand_generation
    demands = generate_demands(config)

    for demand in demands:
        assert generation.minimum_volume <= demand.volume
        assert demand.volume <= generation.maximum_volume

        assert generation.minimum_fare_per_teu <= demand.fare_per_teu
        assert demand.fare_per_teu <= generation.maximum_fare_per_teu

        assert (
            generation.minimum_reservation_time
            <= demand.reservation_time
            <= generation.maximum_reservation_time
        )

        availability_lag = demand.availability_time - demand.reservation_time

        assert (
            generation.minimum_availability_lag
            <= availability_lag
            <= generation.maximum_availability_lag
        )

        due_slack = demand.due_time - demand.availability_time

        assert generation.minimum_due_slack <= due_slack <= generation.maximum_due_slack


def test_every_generated_demand_has_a_time_feasible_route() -> None:
    """The generator must not create structurally infeasible demands."""
    config = load_toy_config()
    demands = generate_demands(config)

    graph = build_time_space_network(
        terminals=config.network.terminals,
        time_periods=config.network.time_periods,
        transport_legs=config.network.transport_legs,
        add_holding_arcs=config.network.add_holding_arcs,
    )

    for demand in demands:
        result = extract_demand_feasible_network(
            graph,
            origin=demand.origin,
            destination=demand.destination,
            availability_time=demand.availability_time,
            due_time=demand.due_time,
        )

        assert result.is_feasible, demand.demand_id


def test_feasible_template_enumeration_is_deterministic() -> None:
    """Candidate templates must have stable content and ordering."""
    config = load_toy_config()

    first = enumerate_feasible_demand_templates(config)
    second = enumerate_feasible_demand_templates(config)

    assert first
    assert first == second


def test_generator_rejects_network_without_feasible_templates() -> None:
    """A network without transport movements cannot generate OD demands."""
    config = load_toy_config()

    empty_network = replace(
        config.network,
        transport_legs=(),
    )
    invalid_experiment = replace(
        config,
        network=empty_network,
    )

    with pytest.raises(ValueError, match="No feasible demand templates"):
        generate_demands(invalid_experiment)


def test_generated_csv_contains_header_and_all_demands(
    tmp_path: Path,
) -> None:
    """CSV output must contain one header and one row per demand."""
    config = load_toy_config()
    demands = generate_demands(config)

    output_path = write_demands_csv(
        demands,
        tmp_path / "demands.csv",
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()

    assert lines[0].startswith("demand_id,volume,origin,destination")
    assert len(lines) == len(demands) + 1


def test_fingerprint_is_a_sha256_hexadecimal_string() -> None:
    """The instance fingerprint must be a 64-character SHA-256 value."""
    config = load_toy_config()
    fingerprint = demand_fingerprint(generate_demands(config))

    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
