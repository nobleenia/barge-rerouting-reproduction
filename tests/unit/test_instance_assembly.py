"""Tests for canonical optimisation-instance assembly."""

from pathlib import Path

import networkx as nx
import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)

CANONICAL_TOY_FINGERPRINT = "8a4b689e039dab9337ea335a62d79c57abe1ace9dfb48d431154eb9aca72abfc"


def load_toy_config():
    """Load the committed toy experiment configuration."""
    return load_experiment_config(Path("configs/toy_experiment.yaml"))


def test_toy_instance_has_expected_global_counts() -> None:
    """The canonical toy instance must retain its known dimensions."""
    instance = assemble_experiment_instance(load_toy_config())

    assert instance.node_count == 21
    assert instance.arc_count == 24
    assert instance.demand_count == 20
    assert len(instance.demand_network_indexes) == 20

    assert instance.demand_fingerprint == CANONICAL_TOY_FINGERPRINT


def test_every_demand_has_one_matching_network_index() -> None:
    """Each realised demand requires exactly one feasible network index."""
    instance = assemble_experiment_instance(load_toy_config())

    demand_ids = {demand.demand_id for demand in instance.demands}
    indexed_demand_ids = {
        network_index.demand_id for network_index in instance.demand_network_indexes
    }

    assert indexed_demand_ids == demand_ids


def test_demand_sources_and_destinations_match_original_requests() -> None:
    """Demand-specific source and destination nodes must be consistent."""
    instance = assemble_experiment_instance(load_toy_config())

    for network_index in instance.demand_network_indexes:
        demand = network_index.demand

        assert network_index.source == (
            demand.origin,
            demand.availability_time,
        )

        assert network_index.destination_nodes

        for destination_node in network_index.destination_nodes:
            assert destination_node[0] == demand.destination
            assert destination_node[1] <= demand.due_time


def test_all_feasible_arcs_belong_to_global_arc_index() -> None:
    """Pruned demand networks may not invent new transport arcs."""
    instance = assemble_experiment_instance(load_toy_config())

    global_arc_ids = {arc.arc_id for arc in instance.arcs}

    for network_index in instance.demand_network_indexes:
        assert set(network_index.feasible_arc_ids).issubset(global_arc_ids)


def test_node_flow_indexes_cover_every_feasible_arc_once() -> None:
    """Each feasible arc must have exactly one tail and one head index."""
    instance = assemble_experiment_instance(load_toy_config())

    for network_index in instance.demand_network_indexes:
        incoming_arc_ids: list[str] = []
        outgoing_arc_ids: list[str] = []

        for node_index in network_index.node_flow_indexes:
            incoming_arc_ids.extend(node_index.incoming_arc_ids)
            outgoing_arc_ids.extend(node_index.outgoing_arc_ids)

        assert len(incoming_arc_ids) == len(set(incoming_arc_ids))
        assert len(outgoing_arc_ids) == len(set(outgoing_arc_ids))

        assert set(incoming_arc_ids) == set(network_index.feasible_arc_ids)
        assert set(outgoing_arc_ids) == set(network_index.feasible_arc_ids)


def test_instance_lookup_methods_return_expected_objects() -> None:
    """Arc, demand, and network-index lookups must use stable IDs."""
    instance = assemble_experiment_instance(load_toy_config())

    first_demand = instance.demands[0]
    first_arc = instance.arcs[0]

    assert instance.demand_by_id(first_demand.demand_id) is first_demand
    assert instance.arc_by_id(first_arc.arc_id) is first_arc

    assert instance.network_index_for(first_demand.demand_id).demand is first_demand

    with pytest.raises(KeyError):
        instance.demand_by_id("DOES-NOT-EXIST")

    with pytest.raises(KeyError):
        instance.arc_by_id("DOES-NOT-EXIST")


def test_repeated_assembly_is_deterministic() -> None:
    """Repeated assembly from one configuration must be reproducible."""
    config = load_toy_config()

    first = assemble_experiment_instance(config)
    second = assemble_experiment_instance(config)

    assert first.demand_fingerprint == second.demand_fingerprint
    assert first.demands == second.demands
    assert first.arcs == second.arcs
    assert first.demand_network_indexes == second.demand_network_indexes


def test_explicit_infeasible_demand_is_rejected() -> None:
    """Assembly must reject a demand with no route by its deadline."""
    config = load_toy_config()

    infeasible_demand = Demand(
        demand_id="INFEASIBLE",
        volume=1.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=4,
        due_time=5,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=20.0,
    )

    with pytest.raises(ValueError, match="has no feasible path"):
        assemble_experiment_instance(
            config,
            demands=(infeasible_demand,),
        )


def test_explicit_demands_cannot_be_combined_with_seed_override() -> None:
    """Explicit demands already determine the instance content."""
    config = load_toy_config()

    demand = Demand(
        demand_id="KTEST",
        volume=1.0,
        origin="A",
        destination="B",
        reservation_time=0,
        availability_time=0,
        due_time=1,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=20.0,
    )

    with pytest.raises(ValueError, match="cannot be supplied"):
        assemble_experiment_instance(
            config,
            demands=(demand,),
            random_seed=123,
        )


def test_instance_graph_is_frozen_after_assembly() -> None:
    """The canonical graph must not be modified after indexes are prepared."""
    instance = assemble_experiment_instance(load_toy_config())

    assert instance.graph.frozen

    with pytest.raises(nx.NetworkXError):
        instance.graph.add_node(("Z", 99))


def test_seed_override_changes_instance_fingerprint() -> None:
    """Controlled replications may use a documented alternative seed."""
    config = load_toy_config()

    baseline = assemble_experiment_instance(config)
    alternative = assemble_experiment_instance(
        config,
        random_seed=config.random_seed + 1,
    )

    assert baseline.demand_fingerprint != alternative.demand_fingerprint
