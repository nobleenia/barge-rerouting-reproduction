"""CLI for the resumable Phase-11C Table-6 campaign."""

from __future__ import annotations

import argparse

from barge_rerouting.experiments.phase11_table6_campaign_runner import (
    run_table6_campaign,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-directory",
        default=("results/phase11/table6/campaign"),
    )

    parser.add_argument(
        "--max-new-runs",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    run_table6_campaign(
        output_directory=args.output_directory,
        max_new_runs=args.max_new_runs,
    )


if __name__ == "__main__":
    main()
