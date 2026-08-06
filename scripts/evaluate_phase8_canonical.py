"""Run and export the canonical Phase 8 DCA-RM evaluation."""

from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management.evaluation import (
    evaluate_phase8_canonical,
    write_phase8_evaluation,
)


def main() -> None:
    """Run the canonical sensitivity evaluation twice."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(config)

    first = evaluate_phase8_canonical(instance)
    second = evaluate_phase8_canonical(instance)

    if first != second:
        raise RuntimeError("Canonical Phase 8 evaluation is not deterministic.")

    paths = write_phase8_evaluation(
        first,
        output_directory=Path("results/phase8"),
        report_path=Path("docs/phase8_canonical_results.md"),
    )

    print("Phase 8 canonical synthetic DCA-RM evaluation")
    print(f"Instance fingerprint: {first.instance_fingerprint}")
    print(f"Booking events:       {first.total_booking_events}")
    print(f"Forecast VMAX:        {first.maximum_forecast_volume}")
    print(f"Look-ahead periods:   {first.lookahead_periods}")
    print()

    header = (
        f"{'Policy':<30}"
        f"{'Done':>7}"
        f"{'Events':>9}"
        f"{'Volume':>11}"
        f"{'Revenue':>12}"
        f"{'Future':>12}"
        f"{'Protect':>10}"
    )
    print(header)
    print("-" * len(header))

    for summary in first.summaries:
        print(
            f"{summary.policy_key:<30}"
            f"{str(summary.completed):>7}"
            f"{summary.processed_events:>9}"
            f"{summary.accepted_volume:>11.2f}"
            f"{summary.realised_revenue:>12.2f}"
            f"{summary.summed_expected_future_contribution:>12.2f}"
            f"{summary.selected_protection_volume:>10.2f}"
        )

    print()
    print("Deterministic rerun: True")
    print(f"Summary CSV:         {paths.policy_summary_csv}")
    print(f"Event CSV:           {paths.event_results_csv}")
    print(f"Evaluation JSON:     {paths.evaluation_json}")
    print(f"Markdown report:     {paths.report_markdown}")


if __name__ == "__main__":
    main()
