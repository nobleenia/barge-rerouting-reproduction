"""Load and summarise a validated experiment configuration."""

from __future__ import annotations

import argparse
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.network.time_space import build_time_space_network


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Inspect a barge-rerouting experiment configuration."
    )
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the YAML experiment configuration.",
    )
    return parser.parse_args()


def main() -> None:
    """Load, validate, and summarise the experiment."""
    arguments = parse_arguments()
    config = load_experiment_config(arguments.config_path)

    graph = build_time_space_network(
        terminals=config.network.terminals,
        time_periods=config.network.time_periods,
        transport_legs=config.network.transport_legs,
        add_holding_arcs=config.network.add_holding_arcs,
    )

    print("Configuration valid")
    print(f"Experiment:       {config.experiment_name}")
    print(f"Random seed:      {config.random_seed}")
    print(f"Terminals:        {config.network.terminals}")
    print(f"Horizon:          {config.network.horizon_start} to {config.network.horizon_end}")
    print(f"Scheduled legs:   {len(config.network.transport_legs)}")
    print(f"Generated demands:{config.demand_generation.number_of_demands:>4}")
    print(f"Graph nodes:      {graph.number_of_nodes()}")
    print(f"Graph arcs:       {graph.number_of_edges()}")
    print(f"Solver limit:     {config.solver.time_limit_seconds} seconds")
    print(f"Relative MIP gap: {config.solver.relative_mip_gap}")


if __name__ == "__main__":
    main()
