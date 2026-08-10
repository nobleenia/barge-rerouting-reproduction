"""Bridge persisted Phase-11 Table-5 summaries into reporting ledgers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from barge_rerouting.reporting.table5_ledger import (
    Table5VolumeLedger,
)

PERSISTED_TOLERANCE = 1.0e-5


def _require_bool(
    record: Mapping[str, Any],
    key: str,
) -> bool:
    value = record.get(key)

    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a bool.")

    return value


def _require_int(
    record: Mapping[str, Any],
    key: str,
) -> int:
    value = record.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise ValueError(f"{key} must be an int.")

    return value


def _require_float(
    record: Mapping[str, Any],
    key: str,
) -> float:
    value = record.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(f"{key} must be numeric.")

    result = float(value)

    if not isfinite(result):
        raise ValueError(f"{key} must be finite.")

    return result


def _require_str(
    record: Mapping[str, Any],
    key: str,
) -> str:
    value = record.get(key)

    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")

    return value


@dataclass(frozen=True, slots=True)
class Table5PersistedSummary:
    """Validated aggregate result retained by one completed pilot."""

    policy_key: str
    demand_fingerprint: str

    requested_booking_count: int
    accepted_request_count: int

    accepted_volume: float
    total_revenue: float

    truck_volume: float
    truck_penalty: float
    net_value: float

    runtime_seconds: float

    @classmethod
    def from_mapping(
        cls,
        record: Mapping[str, Any],
    ) -> Table5PersistedSummary:
        """Parse one successful persisted pilot summary."""
        if not _require_bool(
            record,
            "completed",
        ):
            raise ValueError("Persisted Table-5 summary must be completed.")

        solver_failures = _require_int(
            record,
            "solver_failure_count",
        )

        if solver_failures != 0:
            raise ValueError("Completed reporting summaries require zero solver failures.")

        policy_key = _require_str(
            record,
            "pilot_policy",
        ).lower()

        if policy_key not in {
            "dca",
            "pr",
            "fr",
        }:
            raise ValueError(f"Unsupported Table-5 policy: {policy_key}.")

        requested = _require_int(
            record,
            "requested_booking_count",
        )

        a036 = _require_int(
            record,
            "a036_feasibility_rejection_count",
        )

        ordinary_rejections = _require_int(
            record,
            "ordinary_rejection_count",
        )

        accepted_count = requested - a036 - ordinary_rejections

        if accepted_count < 0:
            raise ValueError("Persisted rejection counts exceed requested booking count.")

        accepted_volume = _require_float(
            record,
            "accepted_volume_teu",
        )

        total_revenue = _require_float(
            record,
            "total_revenue",
        )

        runtime_seconds = _require_float(
            record,
            "runtime_seconds",
        )

        if policy_key == "dca":
            truck_volume = 0.0
            truck_penalty = 0.0
            net_value = total_revenue

        else:
            truck_volume = _require_float(
                record,
                "total_truck_volume_teu",
            )

            truck_penalty = _require_float(
                record,
                "total_truck_penalty",
            )

            persisted_net = _require_float(
                record,
                "net_realised_value",
            )

            computed_net = total_revenue - truck_penalty

            if abs(persisted_net - computed_net) > PERSISTED_TOLERANCE:
                raise ValueError("Persisted net value disagrees with revenue minus truck penalty.")

            net_value = persisted_net

        return cls(
            policy_key=policy_key,
            demand_fingerprint=_require_str(
                record,
                "demand_fingerprint",
            ),
            requested_booking_count=requested,
            accepted_request_count=accepted_count,
            accepted_volume=accepted_volume,
            total_revenue=total_revenue,
            truck_volume=truck_volume,
            truck_penalty=truck_penalty,
            net_value=net_value,
            runtime_seconds=runtime_seconds,
        )

    def build_volume_ledger(
        self,
        *,
        requested_volume: float,
    ) -> Table5VolumeLedger:
        """Construct the denominator-neutral raw ledger."""
        final_barge_volume = self.accepted_volume - self.truck_volume

        return Table5VolumeLedger(
            requested_request_count=(self.requested_booking_count),
            accepted_request_count=(self.accepted_request_count),
            requested_volume=float(requested_volume),
            accepted_volume=self.accepted_volume,
            truck_volume=self.truck_volume,
            final_barge_volume=final_barge_volume,
            gross_revenue=self.total_revenue,
            truck_penalty=self.truck_penalty,
            net_value=self.net_value,
        )
