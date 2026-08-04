"""Run and export the canonical Phase 7 comparison."""

from dataclasses import replace
from pathlib import Path

from barge_rerouting.config import load_experiment_config
from barge_rerouting.instance import assemble_experiment_instance
from barge_rerouting.rerouting import (
    evaluate_full_reroute_against_sequential,
    write_phase7_evaluation,
)


def main() -> None:
    """Evaluate the canonical seeded experiment twice."""
    config = load_experiment_config(Path("configs/toy_experiment.yaml"))
    config = replace(
        config,
        solver=replace(
            config.solver,
            log_output=False,
        ),
    )

    instance = assemble_experiment_instance(config)

    first = evaluate_full_reroute_against_sequential(instance)
    second = evaluate_full_reroute_against_sequential(instance)

    if first != second:
        raise RuntimeError("Canonical Full-Reroute evaluation is not deterministic.")

    paths = write_phase7_evaluation(
        first,
        output_directory=Path("results/phase7"),
        report_path=Path("docs/phase7_canonical_results.md"),
    )

    summary = first.summary

    print("Phase 7 canonical evaluation")
    print(f"Instance fingerprint:       {summary.instance_fingerprint}")
    print(f"Booking events:             {summary.total_booking_events}")
    print(f"Ordinary completed:         {summary.ordinary_completed}")
    print(f"Full-Reroute completed:     {summary.full_reroute_completed}")
    print(f"Ordinary processed events:  {summary.ordinary_processed_events}")
    print(f"Full-Reroute processed:     {summary.full_reroute_processed_events}")
    print(f"Ordinary accepted volume:   {summary.ordinary_accepted_volume:.2f}")
    print(f"Full-Reroute volume:        {summary.full_reroute_accepted_volume:.2f}")
    print(f"Accepted-volume delta:      {summary.accepted_volume_delta:+.2f}")
    print(f"Ordinary revenue:           {summary.ordinary_revenue:.2f}")
    print(f"Full-Reroute revenue:       {summary.full_reroute_revenue:.2f}")
    print(f"Revenue delta:              {summary.revenue_delta:+.2f}")
    print(f"Paired acceptance gains:    {summary.paired_acceptance_improvement_count}")
    print(f"Ordinary failure recovered: {summary.ordinary_failure_recovered}")
    print(f"Additional processed events: {summary.additional_processed_events}")
    print(f"Failure-sequence shift:     {summary.failure_sequence_shift}")
    print(f"Common-prefix revenue delta: {summary.common_prefix_revenue_delta:+.2f}")
    print(f"Common-prefix volume delta: {summary.common_prefix_accepted_volume_delta:+.2f}")
    print(f"Continuation revenue:       {summary.continuation_revenue_after_ordinary_failure:+.2f}")
    print(f"Continuation volume:        {summary.continuation_volume_after_ordinary_failure:+.2f}")
    print(f"Prior-reoptimising events:  {summary.events_reoptimising_prior_commitments}")
    print(f"Ordinary failure:           {summary.ordinary_failure_event_id or 'none'}")
    print(f"Full-Reroute failure:       {summary.full_reroute_failure_event_id or 'none'}")
    print("Deterministic rerun:        True")
    print(f"Event CSV:                  {paths.event_csv}")
    print(f"Evaluation JSON:            {paths.evaluation_json}")
    print(f"Markdown report:            {paths.report_markdown}")


if __name__ == "__main__":
    main()
