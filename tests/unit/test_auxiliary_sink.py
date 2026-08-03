"""Tests for demand-specific auxiliary destination sinks."""

from pathlib import Path

import pytest

from barge_rerouting.config import load_experiment_config
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
)
from barge_rerouting.instance import (
    AuxiliarySinkArc,
    assemble_experiment_instance,
    auxiliary_sink_id_for,
    build_auxiliary_sink_arcs,
)


def load_toy_config():
    """Load the committed toy experiment configuration."""
    return load_experiment_config(Path("configs/toy_experiment.yaml"))


def test_sink_identifier_is_demand_specific() -> None:
    """Every demand must receive a separate logical sink."""
    assert auxiliary_sink_id_for("K0001") == "sink::K0001"
    assert auxiliary_sink_id_for("K0002") == "sink::K0002"


def test_one_sink_arc_is_created_per_destination_node() -> None:
    """Each eligible arrival time must connect to the logical sink."""
    sink_arcs = build_auxiliary_sink_arcs(
        demand_id="KTEST",
        destination_nodes=(
            ("C", 2),
            ("C", 3),
            ("C", 4),
        ),
    )

    assert len(sink_arcs) == 3
    assert {sink_arc.tail for sink_arc in sink_arcs} == {
        ("C", 2),
        ("C", 3),
        ("C", 4),
    }
    assert {sink_arc.sink_id for sink_arc in sink_arcs} == {"sink::KTEST"}


def test_k0001_has_one_delivery_arc_from_a2() -> None:
    """The canonical first demand has one eligible arrival node."""
    instance = assemble_experiment_instance(load_toy_config())
    network_index = instance.network_index_for("K0001")

    assert network_index.auxiliary_sink_id == "sink::K0001"
    assert network_index.destination_nodes == (("A", 2),)
    assert len(network_index.sink_arcs) == 1

    sink_arc = network_index.sink_arcs[0]

    assert sink_arc.tail == ("A", 2)
    assert sink_arc.head == "sink::K0001"
    assert sink_arc.arc_id in network_index.outgoing_flow_arc_ids(("A", 2))


def test_multiple_arrival_times_share_one_logical_sink() -> None:
    """All acceptable destination times must feed one demand-specific sink."""
    demand = Demand(
        demand_id="KMULTI",
        volume=5.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=4,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=30.0,
    )

    instance = assemble_experiment_instance(
        load_toy_config(),
        demands=(demand,),
    )
    network_index = instance.network_index_for("KMULTI")

    assert network_index.destination_nodes == (
        ("C", 2),
        ("C", 3),
        ("C", 4),
    )
    assert len(network_index.sink_arcs) == 3
    assert {sink_arc.sink_id for sink_arc in network_index.sink_arcs} == {"sink::KMULTI"}

    for destination_node in network_index.destination_nodes:
        sink_arc = network_index.sink_arc_for_destination(destination_node)

        assert sink_arc.tail == destination_node
        assert sink_arc.arc_id in network_index.outgoing_flow_arc_ids(destination_node)


def test_all_flow_arcs_include_physical_and_delivery_arcs() -> None:
    """The future model must create variables for both arc classes."""
    instance = assemble_experiment_instance(load_toy_config())
    network_index = instance.network_index_for("K0001")

    assert set(network_index.all_flow_arc_ids) == {
        *network_index.feasible_arc_ids,
        *network_index.sink_arc_ids,
    }

    assert len(network_index.all_flow_arc_ids) == (
        network_index.feasible_arc_count + len(network_index.sink_arcs)
    )


def test_sink_arc_rejects_mismatched_sink_identifier() -> None:
    """A delivery arc cannot terminate at another demand's sink."""
    with pytest.raises(ValueError, match="deterministic"):
        AuxiliarySinkArc(
            arc_id="delivery::K0001::A@2->sink",
            demand_id="K0001",
            tail=("A", 2),
            sink_id="sink::K9999",
        )
