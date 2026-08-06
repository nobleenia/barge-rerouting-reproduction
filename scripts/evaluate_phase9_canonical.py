"""Run and export the canonical Phase 9 evaluation."""

from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import (
    load_experiment_config,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management.rrm_evaluation import (
    evaluate_phase9_canonical,
    write_phase9_evaluation,
)


def main() -> None:
    """Evaluate all default forecast regimes twice and export."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )
    instance = assemble_experiment_instance(config)

    first = evaluate_phase9_canonical(instance)
    second = evaluate_phase9_canonical(instance)

    if first != second:
        raise RuntimeError("Phase 9 canonical evaluation is not deterministic.")

    paths = write_phase9_evaluation(
        first,
        output_directory=Path("results/phase9"),
        report_path=Path("docs/phase9_canonical_results.md"),
    )

    print("Phase 9 canonical four-mechanism evaluation")
    print(f"Instance fingerprint: {first.instance_fingerprint}")
    print(f"Booking events:       {first.total_booking_events}")
    print(f"Forecast regimes:     {len(first.regimes)}")
    print()

    header = (
        f"{'Policy':<31} "
        f"{'Done':<5} "
        f"{'Proc.':>5} "
        f"{'Volume':>8} "
        f"{'Revenue':>10} "
        f"{'Objective':>11} "
        f"{'Future':>10} "
        f"{'Reroute':>7} "
        f"{'Failure':<20}"
    )
    print(header)
    print("-" * len(header))

    for summary in first.summaries:
        print(
            f"{summary.policy_label:<31} "
            f"{str(summary.completed):<5} "
            f"{summary.processed_events:>5} "
            f"{summary.accepted_volume:>8.2f} "
            f"{summary.realised_revenue:>10.2f} "
            f"{summary.summed_optimisation_objectives:>11.2f} "
            f"{summary.summed_expected_future_contribution:>10.2f} "
            f"{summary.events_reoptimising_prior_commitments:>7} "
            f"{summary.failure_event_id or 'none':<20}"
        )

    print()
    print("Deterministic rerun: True")
    print()
    print("Revenue columns contain realised current-request revenue only.")
    print(
        "Objective and future columns are diagnostic and must not be interpreted as earned revenue."
    )
    print()
    print(f"Summary CSV:      {paths.policy_summary_csv}")
    print(f"Event CSV:        {paths.event_results_csv}")
    print(f"Evaluation JSON:  {paths.evaluation_json}")
    print(f"Markdown report:  {paths.report_markdown}")


if __name__ == "__main__":
    main()
