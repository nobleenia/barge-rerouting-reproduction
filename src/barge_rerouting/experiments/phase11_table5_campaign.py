"""Deterministic Phase-11 Table-5 campaign construction.

This module constructs the frozen 8 structural cells and 24 policy runs
required by the controlled Table-5 reproduction.

Execution/checkpointing is intentionally added separately after the campaign
input contract and rich reporting persistence have been validated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import fsum

from barge_rerouting.config import ExperimentConfig
from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.disruption.timeline import (
    OperationalTimeline,
    build_operational_timeline,
)
from barge_rerouting.experiments.phase11_services import (
    build_periodic_corridor_network_config,
)
from barge_rerouting.experiments.phase11_table4 import (
    experiment_config_fingerprint,
)
from barge_rerouting.experiments.phase11_table5 import (
    Table5ExperimentSpec,
    build_table5_pr_forecast_updates,
    default_table5_experiment_spec,
)
from barge_rerouting.experiments.phase11_table5_pilot import (
    build_frozen_table5_controlled_demand_set,
    build_table5_pilot_config,
    build_table5_truck_penalties,
    verify_table5_standard_water,
    verify_table5_structural_feasibility,
)
from barge_rerouting.instance import (
    ExperimentInstance,
    assemble_experiment_instance,
)
from barge_rerouting.reporting.table5_campaign_record import (
    TABLE5_CAMPAIGN_RECORD_SCHEMA,
)
from barge_rerouting.rolling_horizon import (
    BookingTimeline,
    build_booking_timeline,
)

TABLE5_REPORTING_SCHEMA_VERSION = TABLE5_CAMPAIGN_RECORD_SCHEMA


@dataclass(frozen=True, slots=True)
class Table5CampaignCell:
    """One structural Table-5 service-family/capacity cell."""

    service_family: str
    capacity_teu: int
    reproduction_class: str

    @property
    def cell_key(self) -> str:
        """Return stable cell identifier."""
        return f"{self.service_family}__capacity_{self.capacity_teu}"


@dataclass(frozen=True, slots=True)
class Table5CampaignRunSpec:
    """One policy run inside one structural Table-5 cell."""

    service_family: str
    capacity_teu: int
    policy_key: str
    reproduction_class: str

    @property
    def cell_key(self) -> str:
        """Return stable structural cell identifier."""
        return f"{self.service_family}__capacity_{self.capacity_teu}"

    @property
    def run_key(self) -> str:
        """Return stable policy-run identifier."""
        return f"{self.cell_key}__{self.policy_key}"


@dataclass(frozen=True, slots=True)
class Table5CampaignCellInputs:
    """Fully assembled frozen inputs for one structural campaign cell."""

    cell: Table5CampaignCell
    spec: Table5ExperimentSpec

    config: ExperimentConfig
    instance: ExperimentInstance

    booking_timeline: BookingTimeline
    pr_timeline: OperationalTimeline

    pr_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ]
    truck_penalty_per_teu_by_demand: dict[str, float]

    configuration_fingerprint: str
    demand_fingerprint: str

    reporting_schema_version: str = TABLE5_REPORTING_SCHEMA_VERSION

    @property
    def requested_booking_count(self) -> int:
        """Return frozen request count."""
        return len(self.instance.demands)

    @property
    def requested_volume(self) -> float:
        """Return total frozen requested cargo volume."""
        return float(fsum(float(demand.volume) for demand in self.instance.demands))


def build_default_table5_campaign_cells(
    spec: Table5ExperimentSpec | None = None,
) -> tuple[Table5CampaignCell, ...]:
    """Build the frozen eight structural Table-5 cells."""
    selected = default_table5_experiment_spec() if spec is None else spec

    cells = tuple(
        Table5CampaignCell(
            service_family=service_family,
            capacity_teu=capacity_teu,
            reproduction_class=(selected.reproduction_class),
        )
        for service_family in selected.service_families
        for capacity_teu in selected.capacities_teu
    )

    expected = len(selected.service_families) * len(selected.capacities_teu)

    if len(cells) != expected:
        raise RuntimeError("Table-5 structural campaign cardinality changed.")

    return cells


def build_default_table5_run_plan(
    spec: Table5ExperimentSpec | None = None,
) -> tuple[Table5CampaignRunSpec, ...]:
    """Build the frozen 24-policy-run Table-5 plan."""
    selected = default_table5_experiment_spec() if spec is None else spec

    runs = tuple(
        Table5CampaignRunSpec(
            service_family=service_family,
            capacity_teu=capacity_teu,
            policy_key=policy_key,
            reproduction_class=(selected.reproduction_class),
        )
        for service_family in selected.service_families
        for capacity_teu in selected.capacities_teu
        for policy_key in selected.policy_keys
    )

    expected = (
        len(selected.service_families) * len(selected.capacities_teu) * len(selected.policy_keys)
    )

    if len(runs) != expected:
        raise RuntimeError("Table-5 policy-run campaign cardinality changed.")

    return runs


def _validate_cell(
    cell: Table5CampaignCell,
    spec: Table5ExperimentSpec,
) -> None:
    """Reject cells outside the frozen Table-5 contract."""
    if cell.service_family not in spec.service_families:
        raise ValueError(f"Unknown Table-5 service family: {cell.service_family}.")

    if cell.capacity_teu not in spec.capacities_teu:
        raise ValueError(f"Unknown Table-5 capacity: {cell.capacity_teu}.")

    if cell.reproduction_class != spec.reproduction_class:
        raise ValueError("Table-5 reproduction class changed.")


def build_table5_campaign_cell_inputs(
    cell: Table5CampaignCell,
    *,
    spec: Table5ExperimentSpec | None = None,
) -> Table5CampaignCellInputs:
    """Assemble one structural Table-5 campaign cell.

    All cells use the same frozen realised demand set. Only the service
    family and nominal barge capacity change.
    """
    selected = default_table5_experiment_spec() if spec is None else spec

    _validate_cell(
        cell,
        selected,
    )

    base_config = build_table5_pilot_config()

    time_periods = tuple(range(selected.horizon_end + 1))

    network = build_periodic_corridor_network_config(
        time_periods=time_periods,
        service_family=cell.service_family,
        capacity_teu=cell.capacity_teu,
        allowed_capacities_teu=(selected.capacities_teu),
        capacity_context="Table 5",
    )

    config = replace(
        base_config,
        experiment_name=(f"phase11_table5_{cell.service_family}_capacity{cell.capacity_teu}"),
        network=network,
    )

    demand_set = build_frozen_table5_controlled_demand_set()

    if len(demand_set.demands) != selected.demand_count:
        raise RuntimeError("Frozen Table-5 demand count changed.")

    instance = assemble_experiment_instance(
        config,
        demands=demand_set.demands,
    )

    if instance.demand_fingerprint != demand_set.demand_fingerprint:
        raise RuntimeError("Campaign assembly changed the frozen Table-5 demand fingerprint.")

    booking_timeline = build_booking_timeline(instance)

    pr_updates = build_table5_pr_forecast_updates(horizon_end=(selected.horizon_end))

    pr_timeline = build_operational_timeline(
        instance,
        status_updates=pr_updates,
    )

    truck_penalties = build_table5_truck_penalties(instance)

    verify_table5_structural_feasibility(instance)

    verify_table5_standard_water(
        instance,
        pr_updates,
    )

    result = Table5CampaignCellInputs(
        cell=cell,
        spec=selected,
        config=config,
        instance=instance,
        booking_timeline=booking_timeline,
        pr_timeline=pr_timeline,
        pr_updates=pr_updates,
        truck_penalty_per_teu_by_demand=(truck_penalties),
        configuration_fingerprint=(experiment_config_fingerprint(config)),
        demand_fingerprint=(instance.demand_fingerprint),
    )

    if result.requested_booking_count != selected.demand_count:
        raise RuntimeError("Assembled campaign request count changed.")

    return result
