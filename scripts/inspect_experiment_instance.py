"""Assemble and inspect a canonical optimisation instance."""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import mean

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import (
    assemble_experiment_instance,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Inspect an assembled barge optimisation instance."
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the YAML experiment configuration.",
    )
    parser.add_argument(
        "--demand-id",
        default="K0001",
        help="Demand whose feasible network should be displayed.",
    )
    return parser.parse_args()


def main() -> None:
    """Assemble and summarise one experiment instance."""
    arguments = parse_arguments()
    config = load_experiment_config(arguments.config_path)
    instance = assemble_experiment_instance(config)

    feasible_arc_counts = [
        network_index.feasible_arc_count for network_index in instance.demand_network_indexes
    ]
    feasible_node_counts = [
        network_index.feasible_node_count for network_index in instance.demand_network_indexes
    ]

    full_demand_arc_combinations = instance.demand_count * instance.arc_count
    retained_demand_arc_combinations = instance.total_feasible_demand_arcs

    reduction_percentage = (
        100.0
        * (full_demand_arc_combinations - retained_demand_arc_combinations)
        / full_demand_arc_combinations
    )

    print("Experiment instance assembled successfully")
    print(f"Experiment:          {config.experiment_name}")
    print(f"Fingerprint:         {instance.demand_fingerprint}")
    print(f"Full graph nodes:    {instance.node_count}")
    print(f"Full graph arcs:     {instance.arc_count}")
    print(f"Demands:             {instance.demand_count}")
    print(f"Demand-arc pairs:   {retained_demand_arc_combinations}")
    print(f"Unpruned pairs:      {full_demand_arc_combinations}")
    print(f"Arc-pair reduction:  {reduction_percentage:.2f}%")
    print(f"Average feasible nodes per demand: {mean(feasible_node_counts):.2f}")
    print(f"Average feasible arcs per demand:  {mean(feasible_arc_counts):.2f}")
    print()

    network_index = instance.network_index_for(arguments.demand_id)

    print(f"Demand:              {network_index.demand_id}")
    print(f"Request:             {network_index.demand}")
    print(f"Source:              {network_index.source}")
    print(f"Eligible destinations: {network_index.destination_nodes}")
    print(
        "Feasible dimensions: "
        f"{network_index.feasible_node_count} nodes, "
        f"{network_index.feasible_arc_count} physical/holding arcs"
    )
    print(f"Auxiliary sink:      {network_index.auxiliary_sink_id}")
    print(f"Delivery arcs:       {network_index.sink_arc_ids}")
    print(f"All flow arcs:      {len(network_index.all_flow_arc_ids)}")
    print("Node flow indexes:")

    for node_index in network_index.node_flow_indexes:
        print(
            f"  {node_index.node}: "
            f"in={network_index.incoming_flow_arc_ids(node_index.node)}, "
            f"out={network_index.outgoing_flow_arc_ids(node_index.node)}"
        )


if __name__ == "__main__":
    main()
