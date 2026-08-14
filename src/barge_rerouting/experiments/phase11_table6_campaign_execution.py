"""Execute and validate one Phase-11C reduced-water PR run."""

from __future__ import annotations

from math import isclose
from pathlib import Path
from time import perf_counter

from barge_rerouting.experiments.phase11_table5_checkpoint import (
    write_table5_prevalidation_artifact,
)
from barge_rerouting.experiments.phase11_table5_execution import (
    run_phase11_table5_pr,
)
from barge_rerouting.experiments.phase11_table6_campaign import (
    Table6CampaignRunInputs,
)
from barge_rerouting.reporting.table5_campaign_record import (
    Table5CampaignPolicyRecord,
    build_table5_campaign_policy_record,
    build_table5_campaign_prevalidation_payload,
)
from barge_rerouting.reporting.table5_service_capacity import (
    build_table5_service_capacity_snapshot,
)

_TABLE6_INDICATOR_TOLERANCE = 1.0e-6
_TABLE6_CAPACITY_TOLERANCE = 1.0e-9


def _validate_table6_fill_identity(
    record: Table5CampaignPolicyRecord,
    water_factor: float,
) -> None:
    """Enforce NFR = lambda * AFR for all retained candidates."""
    fill = record.indicator_snapshot.fill_rate_candidates

    pairs = (
        (
            fill.mean_arc_actual_pct,
            fill.mean_arc_nominal_pct,
            "mean-arc",
        ),
        (
            fill.capacity_weighted_actual_pct,
            fill.capacity_weighted_nominal_pct,
            "capacity-weighted",
        ),
        (
            fill.mean_sailing_peak_actual_pct,
            fill.mean_sailing_peak_nominal_pct,
            "sailing-peak",
        ),
    )

    for afr, nfr, name in pairs:
        expected_nfr = water_factor * afr

        if not isclose(
            nfr,
            expected_nfr,
            rel_tol=0.0,
            abs_tol=_TABLE6_INDICATOR_TOLERANCE,
        ):
            raise RuntimeError(
                "Table-6 fill-rate invariant failed for "
                f"{name}: NFR={nfr}, "
                f"water_factor*AFR={expected_nfr}."
            )


def execute_table6_campaign_run(
    inputs: Table6CampaignRunInputs,
    *,
    prevalidation_path: str | Path | None = None,
) -> Table5CampaignPolicyRecord:
    """Run one reduced-water PR scenario and persist evidence."""
    run_spec = inputs.run_spec

    started = perf_counter()

    run = run_phase11_table5_pr(
        inputs.base_inputs.instance,
        status_updates=inputs.status_updates,
        truck_penalty_per_teu_by_demand=(inputs.base_inputs.truck_penalty_per_teu_by_demand),
        timeline=inputs.timeline,
    )

    runtime_seconds = perf_counter() - started

    service_capacity_snapshot = build_table5_service_capacity_snapshot(
        instance=inputs.base_inputs.instance,
        final_state=run.final_state,
        reporting_time=inputs.spec.horizon_end,
        status_updates=inputs.status_updates,
        historical_actual_capacity=True,
    )

    for arc in service_capacity_snapshot.arcs:
        if not isclose(
            arc.water_level_factor,
            run_spec.water_factor,
            rel_tol=0.0,
            abs_tol=_TABLE6_CAPACITY_TOLERANCE,
        ):
            raise RuntimeError(
                "Historical Table-6 capacity reporting does not preserve the scenario water factor."
            )

    prevalidation_payload: dict[str, object] | None = None

    if prevalidation_path is not None:
        prevalidation_payload = build_table5_campaign_prevalidation_payload(
            run_key=run_spec.run_key,
            cell_key=run_spec.cell_key,
            service_family=run_spec.service_family,
            capacity_teu=run_spec.capacity_teu,
            configuration_fingerprint=(inputs.scenario_fingerprint),
            demand_fingerprint=(inputs.demand_fingerprint),
            requested_booking_count=(inputs.requested_booking_count),
            requested_volume=(inputs.requested_volume),
            runtime_seconds=runtime_seconds,
            service_capacity_snapshot=(service_capacity_snapshot),
            run=run,
        )

        write_table5_prevalidation_artifact(
            prevalidation_payload,
            prevalidation_path,
        )

    record = build_table5_campaign_policy_record(
        run_key=run_spec.run_key,
        cell_key=run_spec.cell_key,
        service_family=run_spec.service_family,
        capacity_teu=run_spec.capacity_teu,
        configuration_fingerprint=(inputs.scenario_fingerprint),
        demand_fingerprint=inputs.demand_fingerprint,
        requested_booking_count=(inputs.requested_booking_count),
        requested_volume=inputs.requested_volume,
        runtime_seconds=runtime_seconds,
        service_capacity_snapshot=(service_capacity_snapshot),
        run=run,
    )

    if not record.completed:
        raise RuntimeError(f"Table-6 run {run_spec.run_key} did not complete.")

    if record.solver_failure_count != 0:
        raise RuntimeError(f"Table-6 run {run_spec.run_key} contains a solver failure.")

    if record.processed_booking_count != 800:
        raise RuntimeError("Table-6 run did not process all 800 bookings.")

    if record.processed_status_count != 20:
        raise RuntimeError("Table-6 run did not process all 20 status updates.")

    if record.indicator_snapshot.standard_water:
        raise RuntimeError("Reduced-water Table-6 run was reported as standard water.")

    _validate_table6_fill_identity(
        record,
        run_spec.water_factor,
    )

    if prevalidation_path is not None:
        if prevalidation_payload is None:
            raise AssertionError("Prevalidation payload was not created.")

        validated_payload = dict(prevalidation_payload)
        validated_payload["status"] = "validated"

        write_table5_prevalidation_artifact(
            validated_payload,
            prevalidation_path,
        )

    return record
