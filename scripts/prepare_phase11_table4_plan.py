"""Write the unsolved Phase 11 Table 4 experiment manifest."""

from pathlib import Path

from barge_rerouting.experiments import (
    build_default_table4_cells,
    build_default_table4_run_plan,
    write_table4_run_plan_json,
)


def main() -> None:
    """Generate and report the deterministic 120-run plan."""
    cells = build_default_table4_cells()
    runs = build_default_table4_run_plan()

    path = write_table4_run_plan_json(Path("results/phase11/table4/experiment_plan.json"))

    print("Phase 11 Table 4 experimental plan")
    print(f"Paired cells: {len(cells)}")
    print(f"Policy runs:  {len(runs)}")
    print("Classification: controlled_substitute_input")
    print(f"Manifest:     {path}")


if __name__ == "__main__":
    main()
