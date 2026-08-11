"""Execute one Phase-11 Table-5 campaign policy run.

The live policy result is converted immediately into rich reporting
evidence so expensive optimisation does not have to be repeated merely
to reconstruct reporting quantities later.
"""

from __future__ import annotations

from time import perf_counter

from barge_rerouting.experiments.phase11_policy_execution import (
    run_phase11_dca,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCellInputs,
    Table5CampaignRunSpec,
)
from barge_rerouting.experiments.phase11_table5_execution import (
    run_phase11_table5_fr,
    run_phase11_table5_pr,
)
from barge_rerouting.reporting.table5_campaign_record import (
    Table5CampaignPolicyRecord,
    build_table5_campaign_policy_record,
)


def execute_table5_campaign_policy(
    inputs: Table5CampaignCellInputs,
    run_spec: Table5CampaignRunSpec,
) -> Table5CampaignPolicyRecord:
    """Execute one frozen Table-5 policy and capture rich evidence."""
    if run_spec.cell_key != inputs.cell.cell_key:
        raise ValueError("Table-5 run specification does not belong to the supplied campaign cell.")

    if run_spec.reproduction_class != inputs.spec.reproduction_class:
        raise ValueError(
            "Table-5 run reproduction class disagrees with the frozen experiment contract."
        )

    if run_spec.policy_key not in inputs.spec.policy_keys:
        raise ValueError(f"Unsupported Table-5 policy: {run_spec.policy_key}.")

    started = perf_counter()

    if run_spec.policy_key == "dca":
        run = run_phase11_dca(
            inputs.instance,
            timeline=inputs.booking_timeline,
        )

    elif run_spec.policy_key == "pr":
        run = run_phase11_table5_pr(
            inputs.instance,
            status_updates=inputs.pr_updates,
            truck_penalty_per_teu_by_demand=(inputs.truck_penalty_per_teu_by_demand),
            timeline=inputs.pr_timeline,
        )

    elif run_spec.policy_key == "fr":
        # A041/A042 contract:
        # Full reroute reacts to every incoming booking request.
        # It must not inherit PR's neutral periodic status updates.
        run = run_phase11_table5_fr(
            inputs.instance,
            truck_penalty_per_teu_by_demand=(inputs.truck_penalty_per_teu_by_demand),
            status_updates=(),
        )

    else:
        raise AssertionError("Validated Table-5 policy dispatch became unreachable.")

    runtime_seconds = perf_counter() - started

    return build_table5_campaign_policy_record(
        run_key=run_spec.run_key,
        cell_key=run_spec.cell_key,
        service_family=run_spec.service_family,
        capacity_teu=run_spec.capacity_teu,
        configuration_fingerprint=(inputs.configuration_fingerprint),
        demand_fingerprint=(inputs.demand_fingerprint),
        requested_booking_count=(inputs.requested_booking_count),
        requested_volume=(inputs.requested_volume),
        runtime_seconds=runtime_seconds,
        run=run,
    )
