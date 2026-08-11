"""Persistable rich reporting record for one Table-5 policy run."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

from barge_rerouting.experiments.phase11_policy_execution import (
    Phase11PolicyRun,
)
from barge_rerouting.experiments.phase11_table5_execution import (
    Table5OperationalPolicyRun,
)
from barge_rerouting.reporting.table5_allocations import (
    Table5AllocationSnapshot,
    build_table5_allocation_snapshot,
)
from barge_rerouting.reporting.table5_ledger import (
    LEDGER_TOLERANCE,
    Table5VolumeLedger,
    build_table5_volume_ledger,
)

TABLE5_CAMPAIGN_RECORD_SCHEMA = "table5-rich-v1"


@dataclass(frozen=True, slots=True)
class Table5CampaignPolicyRecord:
    """Rich persisted result for one completed Table-5 policy run."""

    reporting_schema_version: str

    run_key: str
    cell_key: str

    service_family: str
    capacity_teu: int
    policy_key: str

    configuration_fingerprint: str
    demand_fingerprint: str

    solver_backend: str
    completed: bool

    requested_booking_count: int
    processed_booking_count: int
    processed_status_count: int

    feasibility_rejection_count: int
    ordinary_rejection_count: int
    solver_failure_count: int

    runtime_seconds: float

    volume_ledger: Table5VolumeLedger
    allocation_snapshot: Table5AllocationSnapshot

    def __post_init__(self) -> None:
        """Validate persisted campaign evidence."""
        if self.reporting_schema_version != TABLE5_CAMPAIGN_RECORD_SCHEMA:
            raise ValueError("Unsupported Table-5 reporting schema.")

        if self.policy_key not in {
            "dca",
            "pr",
            "fr",
        }:
            raise ValueError(f"Unsupported Table-5 policy: {self.policy_key}.")

        if self.capacity_teu <= 0:
            raise ValueError("capacity_teu must be positive.")

        if self.requested_booking_count < 0:
            raise ValueError("requested_booking_count cannot be negative.")

        for name, value in (
            (
                "processed_booking_count",
                self.processed_booking_count,
            ),
            (
                "processed_status_count",
                self.processed_status_count,
            ),
            (
                "feasibility_rejection_count",
                self.feasibility_rejection_count,
            ),
            (
                "ordinary_rejection_count",
                self.ordinary_rejection_count,
            ),
            (
                "solver_failure_count",
                self.solver_failure_count,
            ),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")

        runtime = float(self.runtime_seconds)

        if not isfinite(runtime) or runtime < 0.0:
            raise ValueError("runtime_seconds must be finite and non-negative.")

        if self.volume_ledger.requested_request_count != self.requested_booking_count:
            raise ValueError("Volume ledger request count disagrees with campaign metadata.")

        if (
            self.allocation_snapshot.accepted_request_count
            != self.volume_ledger.accepted_request_count
        ):
            raise ValueError(
                "Allocation snapshot accepted-request count disagrees with volume ledger."
            )

        for name, snapshot_value, ledger_value in (
            (
                "accepted_volume",
                self.allocation_snapshot.accepted_volume,
                self.volume_ledger.accepted_volume,
            ),
            (
                "truck_volume",
                self.allocation_snapshot.truck_volume,
                self.volume_ledger.truck_volume,
            ),
            (
                "truck_penalty",
                self.allocation_snapshot.truck_penalty,
                self.volume_ledger.truck_penalty,
            ),
            (
                "final_barge_volume",
                self.allocation_snapshot.final_barge_volume,
                self.volume_ledger.final_barge_volume,
            ),
        ):
            if abs(snapshot_value - ledger_value) > LEDGER_TOLERANCE:
                raise ValueError(f"{name} disagrees between allocation snapshot and volume ledger.")

        object.__setattr__(
            self,
            "runtime_seconds",
            runtime,
        )

    def to_mapping(self) -> dict[str, Any]:
        """Return JSON-serialisable nested campaign evidence."""
        return asdict(self)


def _solver_backend_name(
    run: (Phase11PolicyRun | Table5OperationalPolicyRun),
) -> str:
    value = run.solver_backend

    enum_value = getattr(
        value,
        "value",
        value,
    )

    return str(enum_value)


def build_table5_campaign_policy_record(
    *,
    run_key: str,
    cell_key: str,
    service_family: str,
    capacity_teu: int,
    configuration_fingerprint: str,
    demand_fingerprint: str,
    requested_booking_count: int,
    requested_volume: float,
    runtime_seconds: float,
    run: (Phase11PolicyRun | Table5OperationalPolicyRun),
) -> Table5CampaignPolicyRecord:
    """Capture rich evidence before the live policy run is discarded."""
    if not run.completed:
        raise ValueError(
            "Only completed Table-5 runs may be persisted as successful campaign records."
        )

    if run.solver_failure_count != 0:
        raise ValueError("Successful Table-5 campaign records require zero solver failures.")

    allocation_snapshot = build_table5_allocation_snapshot(run.final_state)

    if isinstance(
        run,
        Table5OperationalPolicyRun,
    ):
        truck_penalty = float(run.total_truck_penalty)

        processed_booking_count = run.processed_booking_count

        processed_status_count = run.processed_status_count

        feasibility_rejection_count = run.feasibility_rejection_count

    else:
        truck_penalty = 0.0

        processed_booking_count = run.processed_event_count

        processed_status_count = 0

        feasibility_rejection_count = run.feasibility_rejection_count

    volume_ledger = build_table5_volume_ledger(
        final_state=run.final_state,
        gross_revenue=float(run.total_revenue),
        truck_penalty=truck_penalty,
    )

    if volume_ledger.requested_request_count != requested_booking_count:
        raise ValueError(
            "Live final state does not contain the expected number of Table-5 booking decisions."
        )

    if abs(volume_ledger.requested_volume - float(requested_volume)) > LEDGER_TOLERANCE:
        raise ValueError("Live final state requested volume disagrees with frozen campaign inputs.")

    return Table5CampaignPolicyRecord(
        reporting_schema_version=(TABLE5_CAMPAIGN_RECORD_SCHEMA),
        run_key=run_key,
        cell_key=cell_key,
        service_family=service_family,
        capacity_teu=capacity_teu,
        policy_key=run.policy_key,
        configuration_fingerprint=(configuration_fingerprint),
        demand_fingerprint=demand_fingerprint,
        solver_backend=(_solver_backend_name(run)),
        completed=run.completed,
        requested_booking_count=(requested_booking_count),
        processed_booking_count=(processed_booking_count),
        processed_status_count=(processed_status_count),
        feasibility_rejection_count=(feasibility_rejection_count),
        ordinary_rejection_count=(run.ordinary_rejection_count),
        solver_failure_count=(run.solver_failure_count),
        runtime_seconds=runtime_seconds,
        volume_ledger=volume_ledger,
        allocation_snapshot=(allocation_snapshot),
    )
