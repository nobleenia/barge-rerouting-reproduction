"""Run or resume the complete Phase 11 Table 4 campaign."""

from __future__ import annotations

import argparse
from pathlib import Path

from barge_rerouting.experiments.phase11_table4_campaign import (
    run_table4_campaign,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run/resume the 30-cell, 120-run Phase 11 Table 4 campaign.")
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("results/phase11/table4/campaign"),
        help=("Campaign output directory. Existing checkpoint is resumed."),
    )

    parser.add_argument(
        "--max-new-cells",
        type=int,
        default=None,
        help=("Optional safety limit on the number of new cells completed in this invocation."),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_table4_campaign(
        output_directory=args.output_directory,
        max_new_cells=args.max_new_cells,
    )


if __name__ == "__main__":
    main()
