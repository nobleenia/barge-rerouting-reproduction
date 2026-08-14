"""Deterministic construction for the Phase-11C Table-6 campaign."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import fsum, isclose

from barge_rerouting.disruption.status import ServiceStatusUpdateEvent
from barge_rerouting.disruption.timeline import (
    OperationalTimeline,
    build_operational_timeline,
)
from barge_rerouting.experiments.phase11_table5_campaign import (
    Table5CampaignCell,
    Table5CampaignCellInputs,
    build_table5_campaign_cell_inputs,
)
from barge_rerouting.experiments.phase11_table6 import (
    TABLE6_NEW_WATER_FACTORS,
    Table6ExperimentSpec,
    build_table6_pr_forecast_updates,
    default_table6_experiment_spec,
)

_FINGERPRINT_TOLERANCE = 1.0e-12


def _water_key(water_factor: float) -> str:
    return f"{water_factor:.1f}".replace(".", "p")


@dataclass(frozen=True, slots=True)
class Table6CampaignRunSpec:
    """One new reduced-water PR policy run."""

    service_family: str
    capacity_teu: int
    water_factor: float
    policy_key: str
    reproduction_class: str

    @property
    def base_cell_key(self) -> str:
        return f"{self.service_family}__capacity_{self.capacity_teu}"

    @property
    def cell_key(self) -> str:
        return f"{self.base_cell_key}__water_{_water_key(self.water_factor)}"

    @property
    def run_key(self) -> str:
        return f"{self.cell_key}__{self.policy_key}"


@dataclass(frozen=True, slots=True)
class Table6CampaignRunInputs:
    """Fully assembled inputs for one reduced-water PR row."""

    run_spec: Table6CampaignRunSpec
    spec: Table6ExperimentSpec
    base_inputs: Table5CampaignCellInputs

    status_updates: tuple[ServiceStatusUpdateEvent, ...]
    timeline: OperationalTimeline

    base_configuration_fingerprint: str
    scenario_fingerprint: str
    demand_fingerprint: str

    @property
    def requested_booking_count(self) -> int:
        return len(self.base_inputs.instance.demands)

    @property
    def requested_volume(self) -> float:
        return float(fsum(float(demand.volume) for demand in self.base_inputs.instance.demands))


def build_default_table6_new_run_plan(
    spec: Table6ExperimentSpec | None = None,
) -> tuple[Table6CampaignRunSpec, ...]:
    """Return exactly the 24 new reduced-water Table-6 rows."""
    selected = default_table6_experiment_spec() if spec is None else spec

    runs = tuple(
        Table6CampaignRunSpec(
            service_family=service_family,
            capacity_teu=capacity_teu,
            water_factor=water_factor,
            policy_key=selected.policy_key,
            reproduction_class=(selected.reproduction_class),
        )
        for service_family in selected.service_families
        for capacity_teu in selected.capacities_teu
        for water_factor in selected.new_water_factors
    )

    expected = (
        len(selected.service_families)
        * len(selected.capacities_teu)
        * len(selected.new_water_factors)
    )

    if expected != 24 or len(runs) != 24:
        raise RuntimeError("Frozen Table-6 new-run matrix must contain exactly 24 PR runs.")

    if len({run.run_key for run in runs}) != 24:
        raise RuntimeError("Table-6 run keys are not unique.")

    return runs


def build_table6_base_inputs(
    run_spec: Table6CampaignRunSpec,
) -> Table5CampaignCellInputs:
    """Build the validated Table-5-derived structural cell."""
    return build_table5_campaign_cell_inputs(
        Table5CampaignCell(
            service_family=run_spec.service_family,
            capacity_teu=run_spec.capacity_teu,
            reproduction_class=(run_spec.reproduction_class),
        )
    )


def _scenario_fingerprint(
    *,
    base_inputs: Table5CampaignCellInputs,
    run_spec: Table6CampaignRunSpec,
    status_updates: tuple[
        ServiceStatusUpdateEvent,
        ...,
    ],
) -> str:
    payload = {
        "experiment": "phase11_table6",
        "service_family": run_spec.service_family,
        "capacity_teu": run_spec.capacity_teu,
        "policy_key": run_spec.policy_key,
        "water_factor": run_spec.water_factor,
        "base_configuration_fingerprint": (base_inputs.configuration_fingerprint),
        "demand_fingerprint": (base_inputs.demand_fingerprint),
        "status_updates": [
            {
                "sequence_number": update.sequence_number,
                "update_time": update.update_time,
                "valid_from": update.valid_from,
                "valid_until": update.valid_until,
                "water_level_factor": update.water_level_factor,
                "affected_service_ids": list(update.affected_service_ids),
            }
            for update in status_updates
        ],
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def build_table6_campaign_run_inputs(
    run_spec: Table6CampaignRunSpec,
    *,
    base_inputs: Table5CampaignCellInputs | None = None,
    spec: Table6ExperimentSpec | None = None,
) -> Table6CampaignRunInputs:
    """Build one frozen reduced-water PR scenario."""
    selected = default_table6_experiment_spec() if spec is None else spec

    if run_spec.service_family not in selected.service_families:
        raise ValueError("Unknown Table-6 service family.")

    if run_spec.capacity_teu not in selected.capacities_teu:
        raise ValueError("Unknown Table-6 capacity.")

    if run_spec.policy_key != selected.policy_key:
        raise ValueError("Table 6 is Partial-Reroute only.")

    if run_spec.reproduction_class != selected.reproduction_class:
        raise ValueError("Table-6 reproduction class changed.")

    if not any(
        isclose(
            run_spec.water_factor,
            expected,
            rel_tol=0.0,
            abs_tol=_FINGERPRINT_TOLERANCE,
        )
        for expected in TABLE6_NEW_WATER_FACTORS
    ):
        raise ValueError("Production Table-6 run must use 0.9, 0.8, or 0.7.")

    base = build_table6_base_inputs(run_spec) if base_inputs is None else base_inputs

    if base.cell.service_family != run_spec.service_family:
        raise ValueError("Supplied base inputs use the wrong service family.")

    if base.cell.capacity_teu != run_spec.capacity_teu:
        raise ValueError("Supplied base inputs use the wrong capacity.")

    updates = build_table6_pr_forecast_updates(
        run_spec.water_factor,
        horizon_end=selected.horizon_end,
    )

    if len(updates) != 20:
        raise RuntimeError("Table-6 PR trigger count changed.")

    timeline = build_operational_timeline(
        base.instance,
        status_updates=updates,
    )

    if timeline.booking_event_count != selected.demand_count:
        raise RuntimeError("Table-6 booking-event count changed.")

    if timeline.status_update_count != 20:
        raise RuntimeError("Table-6 status-update count changed.")

    scenario_fingerprint = _scenario_fingerprint(
        base_inputs=base,
        run_spec=run_spec,
        status_updates=updates,
    )

    return Table6CampaignRunInputs(
        run_spec=run_spec,
        spec=selected,
        base_inputs=base,
        status_updates=updates,
        timeline=timeline,
        base_configuration_fingerprint=(base.configuration_fingerprint),
        scenario_fingerprint=scenario_fingerprint,
        demand_fingerprint=base.demand_fingerprint,
    )
