"""Generate the five pre-registered Phase 11 forecast catalogues."""

from pathlib import Path

from barge_rerouting.experiments import (
    DEFAULT_TABLE4_DEMAND_SEEDS,
    build_table4_forecast_catalogue,
    write_table4_forecast_catalogue,
)


def main() -> None:
    """Generate every ex-ante Table 4 forecast catalogue."""
    output_directory = Path("results/phase11/table4/forecasts")

    print("Phase 11 Table 4 forecast catalogues")
    print()

    for index, seed in enumerate(
        DEFAULT_TABLE4_DEMAND_SEEDS,
        start=1,
    ):
        demand_set_id = f"demand_set_{index:02d}"

        catalogue = build_table4_forecast_catalogue(seed=seed)

        write_table4_forecast_catalogue(
            catalogue,
            output_directory=output_directory,
            demand_set_id=demand_set_id,
        )

        print(demand_set_id)
        print(f"  seed:        {seed}")
        print(f"  forecast seed: {catalogue.forecast_seed}")
        print(f"  entries:       {catalogue.entry_count}")
        print(f"  fingerprint:   {catalogue.catalogue_fingerprint}")
        print()


if __name__ == "__main__":
    main()
