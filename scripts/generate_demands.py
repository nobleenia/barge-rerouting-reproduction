"""Generate a deterministic synthetic demand instance."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.generation import (
    demand_fingerprint,
    enumerate_feasible_demand_templates,
    generate_demands,
    write_demands_csv,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic barge demands.")
    parser.add_argument(
        "config_path",
        type=Path,
        help="YAML experiment configuration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/generated/toy_demands.csv"),
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random-seed override.",
    )
    return parser.parse_args()


def main() -> None:
    """Generate, write, and summarise one demand instance."""
    arguments = parse_arguments()
    config = load_experiment_config(arguments.config_path)

    templates = enumerate_feasible_demand_templates(config)
    demands = generate_demands(
        config,
        random_seed=arguments.seed,
    )

    output_path = write_demands_csv(
        demands,
        arguments.output,
    )

    category_counts = Counter(demand.category.value for demand in demands)

    selected_seed = config.random_seed if arguments.seed is None else arguments.seed

    print("Demand generation complete")
    print(f"Experiment:         {config.experiment_name}")
    print(f"Random seed:        {selected_seed}")
    print(f"Feasible templates: {len(templates)}")
    print(f"Generated demands:  {len(demands)}")
    print(f"Regular demands:    {category_counts['R']}")
    print(f"Partial demands:    {category_counts['P']}")
    print(f"Fully-spot demands: {category_counts['F']}")
    print(f"Fingerprint:        {demand_fingerprint(demands)}")
    print(f"Output:             {output_path}")


if __name__ == "__main__":
    main()
