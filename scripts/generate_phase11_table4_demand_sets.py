"""Generate the five pre-registered controlled Table 4 demand sets."""

from pathlib import Path

from barge_rerouting.experiments import (
    DEFAULT_TABLE4_DEMAND_SEEDS,
    build_table4_controlled_demand_set,
    write_table4_controlled_demand_set,
)


def main() -> None:
    """Generate and persist every registered controlled demand set."""
    output_directory = Path("results/phase11/table4/demand_sets")

    print("Phase 11 controlled Table 4 demand sets")
    print()

    for index, seed in enumerate(
        DEFAULT_TABLE4_DEMAND_SEEDS,
        start=1,
    ):
        demand_set_id = f"demand_set_{index:02d}"

        demand_set = build_table4_controlled_demand_set(seed=seed)

        write_table4_controlled_demand_set(
            demand_set,
            output_directory=output_directory,
            demand_set_id=demand_set_id,
        )

        print(demand_set_id)
        print(f"  seed:        {seed}")
        print(f"  opportunities: {demand_set.opportunity_count}")
        print(f"  zero volume:   {demand_set.zero_volume_count}")
        print(f"  positive:      {demand_set.positive_demand_count}")
        print(f"  structural:    {demand_set.structural_fingerprint}")
        print(f"  realised:      {demand_set.demand_fingerprint}")
        print()


if __name__ == "__main__":
    main()
