"""Run or resume the frozen Phase-11 Table-5 campaign."""

from __future__ import annotations

import argparse
from pathlib import Path

from barge_rerouting.experiments.phase11_table5_campaign_runner import (
    run_table5_campaign,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Run or resume the Phase-11 Table-5 24-policy campaign.")
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("results/phase11/table5/campaign"),
    )

    parser.add_argument(
        "--max-new-runs",
        type=int,
        default=None,
        help=(
            "Stop after this many newly completed "
            "policy runs. Existing checkpointed "
            "runs do not count."
        ),
    )

    args = parser.parse_args()

    run_table5_campaign(
        output_directory=(args.output_directory),
        max_new_runs=(args.max_new_runs),
    )


if __name__ == "__main__":
    main()
