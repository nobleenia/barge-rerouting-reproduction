"""Run the first real Phase 11 four-policy paired pilot."""

from pathlib import Path

from barge_rerouting.experiments import (
    run_table4_pilot,
    write_table4_pilot,
)


def main() -> None:
    """Execute, validate, persist and report the pilot."""
    print("Phase 11 Table 4 paired pilot")
    print("Cell: Service Family 1 / 10 TEU / demand_set_01")
    print()
    print("Running four policies twice for determinism...")
    print()

    result = run_table4_pilot()

    raw_path, comparison_path, manifest_path = write_table4_pilot(
        result,
        output_directory=(Path("results/phase11/table4/pilot")),
    )

    print(
        "Configuration fingerprint:",
        result.inputs.configuration_fingerprint,
    )
    print(
        "Demand fingerprint:       ",
        result.inputs.demand_fingerprint,
    )
    print(
        "Forecast fingerprint:     ",
        result.inputs.forecast_fingerprint,
    )
    print(
        "Booking events:           ",
        result.inputs.timeline.event_count,
    )
    print()

    header = f"{'Policy':<10} {'Done':<6} {'Revenue':>12} {'Volume':>10} {'Wall time':>12}"

    print(header)
    print("-" * len(header))

    for record in result.records:
        print(
            f"{record.policy_key:<10} "
            f"{str(record.completed):<6} "
            f"{record.total_revenue:>12.2f} "
            f"{record.accepted_volume:>10.2f} "
            f"{record.solve_time_seconds or 0.0:>11.3f}s"
        )

    print()
    print(
        "Deterministic rerun:",
        result.deterministic_rerun_verified,
    )
    print(
        "All policies completed:",
        result.all_policies_completed,
    )

    if result.comparisons:
        print()
        print("DCA-relative pilot IR")

        for comparison in result.comparisons:
            print(
                f"  {comparison.policy_key:<10} "
                f"Revenue {comparison.revenue_ir_percent:+8.3f}% "
                f"Volume {comparison.volume_ir_percent:+8.3f}%"
            )
    else:
        print()
        print("Paired IR was NOT generated because at least one policy did not complete.")

    print()
    print(f"Raw records: {raw_path}")

    if comparison_path is not None:
        print(f"Paired IR:   {comparison_path}")

    print(f"Manifest:    {manifest_path}")


if __name__ == "__main__":
    main()
