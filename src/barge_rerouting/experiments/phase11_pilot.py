"""First paired four-policy Table 4 pilot for Phase 11.

The pilot cell is fixed as:

- Service Family 1;
- nominal capacity 10 TEU;
- controlled demand set 01 / seed 11001;
- stable capacity;
- truck recourse disabled;
- DCA-RM and DCA-RRM share one ex-ante forecast catalogue.

This module deliberately reuses the validated Phase 6--9 policy runners
rather than implementing separate experimental optimisation models.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Final

from barge_rerouting.config import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    SolverConfig,
)
from barge_rerouting.experiments.phase11_baseline import (
    TABLE4_CONTROLLED_HORIZON_END,
    build_table4_controlled_demand_set,
    default_table4_controlled_demand_process,
    default_table4_controlled_economic_spec,
)
from barge_rerouting.experiments.phase11_forecasts import (
    TABLE4_FORECAST_LOOKAHEAD_PERIODS,
    TABLE4_FORECAST_SELECTION_MODE,
    TABLE4_FORECAST_VALUE_INTERPRETATION,
    Table4ForecastCatalogue,
    build_table4_forecast_catalogue,
    build_table4_forecast_provider,
)
from barge_rerouting.experiments.phase11_services import (
    build_table4_network_config,
)
from barge_rerouting.experiments.phase11_table4 import (
    CONTROLLED_SUBSTITUTE_INPUT,
    Table4PairedComparison,
    Table4PolicyRunRecord,
    build_table4_paired_comparisons,
    experiment_config_fingerprint,
    write_table4_comparisons_csv,
    write_table4_run_records_csv,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.rerouting.run import (
    run_full_reroute,
)
from barge_rerouting.revenue_management.rrm_run import (
    run_time_aware_dca_rrm,
)
from barge_rerouting.revenue_management.run import (
    run_time_aware_dca_rm,
)
from barge_rerouting.rolling_horizon import (
    BookingTimeline,
    build_booking_timeline,
    run_time_aware_sequential_dca,
)

TABLE4_PILOT_SERVICE_FAMILY: Final = "service_family_1"
TABLE4_PILOT_CAPACITY_TEU: Final = 10
TABLE4_PILOT_DEMAND_SET_ID: Final = "demand_set_01"
TABLE4_PILOT_SEED: Final = 11001

TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT: Final = (
    "589ba169d6c553e9ddf049dfdb28af83e89649dc61fd482c32985922004adcbf"
)

TABLE4_PILOT_EXPECTED_FORECAST_FINGERPRINT: Final = (
    "da9fa2508c71cf2ea772c553430b9a17cc8c079288e416177e9b1b49044804be"
)

TABLE4_PILOT_TIME_LIMIT_SECONDS: Final = 60.0
TABLE4_PILOT_RELATIVE_MIP_GAP: Final = 0.0


@dataclass(frozen=True, slots=True)
class Table4PilotInputs:
    """Frozen assembled inputs for the first paired pilot cell."""

    config: ExperimentConfig
    instance: ExperimentInstance
    timeline: BookingTimeline
    forecast_catalogue: Table4ForecastCatalogue
    configuration_fingerprint: str
    demand_fingerprint: str
    forecast_fingerprint: str


@dataclass(frozen=True, slots=True)
class Table4PilotResult:
    """Complete first-run pilot result plus determinism check."""

    inputs: Table4PilotInputs
    records: tuple[Table4PolicyRunRecord, ...]
    comparisons: tuple[Table4PairedComparison, ...]
    deterministic_rerun_verified: bool

    @property
    def all_policies_completed(self) -> bool:
        """Return whether all four policy runs completed."""
        return all(record.completed for record in self.records)


def build_table4_pilot_config() -> ExperimentConfig:
    """Build the controlled publication-facing pilot configuration."""
    demand_process = default_table4_controlled_demand_process()
    economic_spec = default_table4_controlled_economic_spec()

    timing_pools = demand_process.timing_pools

    minimum_availability_lag = min(min(pool.anticipation_lags) for pool in timing_pools)
    maximum_availability_lag = max(max(pool.anticipation_lags) for pool in timing_pools)

    minimum_due_slack = min(min(pool.delivery_slacks) for pool in timing_pools)
    maximum_due_slack = max(max(pool.delivery_slacks) for pool in timing_pools)

    base_fares = tuple(item.base_fare_per_teu for item in economic_spec.distance_inputs)

    maximum_base_fare = max(base_fares)
    maximum_fare = (
        maximum_base_fare
        * economic_spec.fare_rates.late_reservation_rate
        * economic_spec.fare_rates.express_delivery_rate
    )

    network = build_table4_network_config(
        time_periods=tuple(range(TABLE4_CONTROLLED_HORIZON_END + 1)),
        service_family=(TABLE4_PILOT_SERVICE_FAMILY),
        capacity_teu=TABLE4_PILOT_CAPACITY_TEU,
    )

    return ExperimentConfig(
        experiment_name=("phase11_table4_pilot_family1_capacity10_set01"),
        random_seed=TABLE4_PILOT_SEED,
        network=network,
        demand_generation=DemandGenerationConfig(
            number_of_demands=(demand_process.request_count),
            minimum_volume=1,
            maximum_volume=(economic_spec.volume_distribution.maximum_volume),
            minimum_fare_per_teu=min(base_fares),
            maximum_fare_per_teu=(maximum_fare),
            minimum_reservation_time=min(demand_process.request_periods),
            maximum_reservation_time=max(demand_process.request_periods),
            minimum_availability_lag=(minimum_availability_lag),
            maximum_availability_lag=(maximum_availability_lag),
            minimum_due_slack=(minimum_due_slack),
            maximum_due_slack=(maximum_due_slack),
            customer_mix=CustomerMix(
                regular_probability=1.0 / 3.0,
                partially_spot_probability=1.0 / 3.0,
                fully_spot_probability=1.0 / 3.0,
            ),
        ),
        solver=SolverConfig(
            time_limit_seconds=(TABLE4_PILOT_TIME_LIMIT_SECONDS),
            relative_mip_gap=(TABLE4_PILOT_RELATIVE_MIP_GAP),
            log_output=False,
        ),
    )


def build_table4_pilot_inputs() -> Table4PilotInputs:
    """Assemble and verify all frozen pilot inputs."""
    demand_set = build_table4_controlled_demand_set(seed=TABLE4_PILOT_SEED)

    if demand_set.demand_fingerprint != TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT:
        raise RuntimeError("Frozen pilot demand fingerprint changed.")

    catalogue = build_table4_forecast_catalogue(seed=TABLE4_PILOT_SEED)

    if catalogue.catalogue_fingerprint != TABLE4_PILOT_EXPECTED_FORECAST_FINGERPRINT:
        raise RuntimeError("Frozen pilot forecast fingerprint changed.")

    config = build_table4_pilot_config()

    instance = assemble_experiment_instance(
        config,
        demands=demand_set.demands,
    )

    if instance.demand_fingerprint != TABLE4_PILOT_EXPECTED_DEMAND_FINGERPRINT:
        raise RuntimeError("Assembled pilot instance changed the frozen demand fingerprint.")

    timeline = build_booking_timeline(instance)

    return Table4PilotInputs(
        config=config,
        instance=instance,
        timeline=timeline,
        forecast_catalogue=catalogue,
        configuration_fingerprint=(experiment_config_fingerprint(config)),
        demand_fingerprint=(instance.demand_fingerprint),
        forecast_fingerprint=(catalogue.catalogue_fingerprint),
    )


def _record(
    *,
    inputs: Table4PilotInputs,
    policy_key: str,
    completed: bool,
    total_revenue: float,
    accepted_volume: float,
    elapsed_seconds: float,
) -> Table4PolicyRunRecord:
    """Build one raw stable-capacity pilot record."""
    return Table4PolicyRunRecord(
        service_family=(TABLE4_PILOT_SERVICE_FAMILY),
        capacity_teu=TABLE4_PILOT_CAPACITY_TEU,
        demand_set_id=(TABLE4_PILOT_DEMAND_SET_ID),
        seed=TABLE4_PILOT_SEED,
        policy_key=policy_key,
        reproduction_class=(CONTROLLED_SUBSTITUTE_INPUT),
        configuration_fingerprint=(inputs.configuration_fingerprint),
        demand_fingerprint=(inputs.demand_fingerprint),
        completed=completed,
        total_revenue=float(total_revenue),
        # Stable Table 4 contains no truck recourse.
        # Every accepted commitment is therefore a
        # barge-transport commitment.
        transported_volume=float(accepted_volume),
        accepted_volume=float(accepted_volume),
        solver_status=("all_events_solved" if completed else "run_incomplete"),
        solve_time_seconds=float(elapsed_seconds),
        mip_gap=None,
        variable_count=None,
        constraint_count=None,
        solver_node_count=None,
    )


def run_table4_pilot_once(
    inputs: Table4PilotInputs,
) -> tuple[Table4PolicyRunRecord, ...]:
    """Run the four Table 4 mechanisms on identical frozen inputs."""
    if not isinstance(
        inputs,
        Table4PilotInputs,
    ):
        raise TypeError("inputs must be Table4PilotInputs.")

    instance = inputs.instance
    timeline = inputs.timeline

    provider = build_table4_forecast_provider(inputs.forecast_catalogue)

    records: list[Table4PolicyRunRecord] = []

    start = perf_counter()
    dca_run = run_time_aware_sequential_dca(
        instance,
        timeline=timeline,
    )
    elapsed = perf_counter() - start

    records.append(
        _record(
            inputs=inputs,
            policy_key="dca",
            completed=dca_run.completed,
            total_revenue=dca_run.total_revenue,
            accepted_volume=dca_run.accepted_volume,
            elapsed_seconds=elapsed,
        )
    )

    start = perf_counter()
    rm_run = run_time_aware_dca_rm(
        instance,
        provider,
        value_interpretation=(TABLE4_FORECAST_VALUE_INTERPRETATION),
        selection_mode=(TABLE4_FORECAST_SELECTION_MODE),
        timeline=timeline,
        lookahead_periods=(TABLE4_FORECAST_LOOKAHEAD_PERIODS),
    )
    elapsed = perf_counter() - start

    records.append(
        _record(
            inputs=inputs,
            policy_key="dca_rm",
            completed=rm_run.completed,
            total_revenue=(rm_run.total_realised_revenue),
            accepted_volume=(rm_run.accepted_volume),
            elapsed_seconds=elapsed,
        )
    )

    start = perf_counter()
    reroute_run = run_full_reroute(
        instance,
        timeline=timeline,
    )
    elapsed = perf_counter() - start

    records.append(
        _record(
            inputs=inputs,
            policy_key="dca_r",
            completed=(reroute_run.completed),
            total_revenue=(reroute_run.total_revenue),
            accepted_volume=(reroute_run.accepted_volume),
            elapsed_seconds=elapsed,
        )
    )

    start = perf_counter()
    rrm_run = run_time_aware_dca_rrm(
        instance,
        provider,
        value_interpretation=(TABLE4_FORECAST_VALUE_INTERPRETATION),
        selection_mode=(TABLE4_FORECAST_SELECTION_MODE),
        timeline=timeline,
        lookahead_periods=(TABLE4_FORECAST_LOOKAHEAD_PERIODS),
    )
    elapsed = perf_counter() - start

    records.append(
        _record(
            inputs=inputs,
            policy_key="dca_rrm",
            completed=rrm_run.completed,
            total_revenue=(rrm_run.total_realised_revenue),
            accepted_volume=(rrm_run.accepted_volume),
            elapsed_seconds=elapsed,
        )
    )

    return tuple(records)


def _scientific_signature(
    records: tuple[Table4PolicyRunRecord, ...],
) -> tuple[
    tuple[
        str,
        bool,
        float,
        float,
        str,
        str,
    ],
    ...,
]:
    """Return deterministic fields excluding wall-clock timing."""
    return tuple(
        (
            record.policy_key,
            record.completed,
            record.total_revenue,
            record.accepted_volume,
            record.configuration_fingerprint,
            record.demand_fingerprint,
        )
        for record in records
    )


def run_table4_pilot() -> Table4PilotResult:
    """Run the first pilot twice and verify scientific determinism."""
    inputs = build_table4_pilot_inputs()

    first = run_table4_pilot_once(inputs)
    second = run_table4_pilot_once(inputs)

    if _scientific_signature(first) != _scientific_signature(second):
        raise RuntimeError(
            "Phase 11 pilot is not scientifically deterministic across repeated runs."
        )

    all_completed = all(record.completed for record in first)

    comparisons: tuple[
        Table4PairedComparison,
        ...,
    ]

    if all_completed:
        comparisons = build_table4_paired_comparisons(
            first,
            require_completed=True,
        )
    else:
        comparisons = ()

    return Table4PilotResult(
        inputs=inputs,
        records=first,
        comparisons=comparisons,
        deterministic_rerun_verified=True,
    )


def write_table4_pilot(
    result: Table4PilotResult,
    *,
    output_directory: str | Path,
) -> tuple[Path, Path | None, Path]:
    """Persist raw results before derived IR reporting."""
    if not isinstance(
        result,
        Table4PilotResult,
    ):
        raise TypeError("result must be a Table4PilotResult.")

    directory = Path(output_directory)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_path = write_table4_run_records_csv(
        result.records,
        directory / "pilot_policy_runs.csv",
    )

    comparison_path: Path | None

    if result.comparisons:
        comparison_path = write_table4_comparisons_csv(
            result.comparisons,
            directory / "pilot_paired_comparisons.csv",
        )
    else:
        comparison_path = None

    manifest_path = directory / "pilot_manifest.json"

    payload = {
        "experiment": ("phase11_table4_pilot"),
        "service_family": (TABLE4_PILOT_SERVICE_FAMILY),
        "capacity_teu": (TABLE4_PILOT_CAPACITY_TEU),
        "demand_set_id": (TABLE4_PILOT_DEMAND_SET_ID),
        "seed": TABLE4_PILOT_SEED,
        "classification": (CONTROLLED_SUBSTITUTE_INPUT),
        "configuration_fingerprint": (result.inputs.configuration_fingerprint),
        "demand_fingerprint": (result.inputs.demand_fingerprint),
        "forecast_fingerprint": (result.inputs.forecast_fingerprint),
        "booking_event_count": (result.inputs.timeline.event_count),
        "forecast_selection_mode": (TABLE4_FORECAST_SELECTION_MODE.value),
        "future_value_interpretation": (TABLE4_FORECAST_VALUE_INTERPRETATION.value),
        "forecast_lookahead_periods": (TABLE4_FORECAST_LOOKAHEAD_PERIODS),
        "truck_enabled": False,
        "water_factor": 1.0,
        "deterministic_rerun_verified": (result.deterministic_rerun_verified),
        "all_policies_completed": (result.all_policies_completed),
        "raw_records": [asdict(record) for record in result.records],
        "paired_comparisons": [asdict(comparison) for comparison in result.comparisons],
        "timing_note": (
            "solve_time_seconds is external wall-clock "
            "time for the complete policy run; it is "
            "not the paper's per-model CPLEX ST metric."
        ),
        "solver_diagnostics_note": (
            "MIP gap, variable count, constraint count "
            "and node count are not yet propagated by "
            "the existing sequential run APIs and remain "
            "null in this pilot."
        ),
    }

    manifest_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        raw_path,
        comparison_path,
        manifest_path,
    )
