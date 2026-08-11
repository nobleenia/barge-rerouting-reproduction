"""Complete candidate indicator snapshot for Phase-11 Table 5.

The publication does not disclose complete mathematical formulas for
all reported indicators. This module therefore bundles explicitly named
candidate reconstructions together with directly observed economic and
timing quantities.

It does not silently promote any candidate to the publication's exact
undisclosed definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.reporting.table5_fill_rates import (
    Table5FillRateCandidates,
    build_table5_fill_rate_candidates,
)
from barge_rerouting.reporting.table5_ledger import (
    LEDGER_TOLERANCE,
    Table5VolumeLedger,
)
from barge_rerouting.reporting.table5_service_capacity import (
    SERVICE_CAPACITY_TOLERANCE,
    Table5ServiceCapacitySnapshot,
)
from barge_rerouting.reporting.table5_volume_indicators import (
    Table5VolumeIndicatorCandidates,
    build_table5_volume_indicator_candidates,
)

TABLE5_INDICATOR_SCHEMA_VERSION = "table5-indicators-v1"


@dataclass(frozen=True, slots=True)
class Table5IndicatorSnapshot:
    """Complete denominator-explicit Table-5 reporting snapshot."""

    indicator_schema_version: str

    fill_rate_candidates: Table5FillRateCandidates
    volume_indicator_candidates: Table5VolumeIndicatorCandidates

    gross_revenue: float
    truck_penalty: float
    net_realised_value: float

    solving_time_seconds: float

    standard_water: bool

    def __post_init__(self) -> None:
        """Validate one complete reporting snapshot."""
        if self.indicator_schema_version != TABLE5_INDICATOR_SCHEMA_VERSION:
            raise ValueError("Unsupported Table-5 indicator schema.")

        gross = float(self.gross_revenue)

        penalty = float(self.truck_penalty)

        net = float(self.net_realised_value)

        runtime = float(self.solving_time_seconds)

        for name, value in (
            ("gross_revenue", gross),
            ("truck_penalty", penalty),
            ("net_realised_value", net),
            ("solving_time_seconds", runtime),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

        if penalty < -LEDGER_TOLERANCE:
            raise ValueError("truck_penalty cannot be negative.")

        if runtime < 0.0:
            raise ValueError("solving_time_seconds cannot be negative.")

        economic_residual = gross - penalty - net

        if abs(economic_residual) > LEDGER_TOLERANCE:
            raise ValueError("Indicator economic quantities are inconsistent.")

        if not isinstance(
            self.standard_water,
            bool,
        ):
            raise TypeError("standard_water must be a bool.")

        if self.standard_water:
            residuals = (
                self.fill_rate_candidates.mean_arc_standard_water_residual,
                self.fill_rate_candidates.capacity_weighted_standard_water_residual,
                self.fill_rate_candidates.sailing_peak_standard_water_residual,
            )

            if any(abs(residual) > SERVICE_CAPACITY_TOLERANCE for residual in residuals):
                raise ValueError(
                    "Standard-water reporting requires AFR=NFR for every retained candidate."
                )

        object.__setattr__(
            self,
            "gross_revenue",
            gross,
        )
        object.__setattr__(
            self,
            "truck_penalty",
            penalty,
        )
        object.__setattr__(
            self,
            "net_realised_value",
            net,
        )
        object.__setattr__(
            self,
            "solving_time_seconds",
            runtime,
        )


def build_table5_indicator_snapshot(
    *,
    volume_ledger: Table5VolumeLedger,
    service_capacity_snapshot: Table5ServiceCapacitySnapshot,
    solving_time_seconds: float,
) -> Table5IndicatorSnapshot:
    """Build the complete candidate indicator bundle."""
    if not isinstance(
        volume_ledger,
        Table5VolumeLedger,
    ):
        raise TypeError("volume_ledger must be Table5VolumeLedger.")

    if not isinstance(
        service_capacity_snapshot,
        Table5ServiceCapacitySnapshot,
    ):
        raise TypeError("service_capacity_snapshot must be Table5ServiceCapacitySnapshot.")

    fill_rates = build_table5_fill_rate_candidates(service_capacity_snapshot)

    volume_indicators = build_table5_volume_indicator_candidates(volume_ledger)

    return Table5IndicatorSnapshot(
        indicator_schema_version=(TABLE5_INDICATOR_SCHEMA_VERSION),
        fill_rate_candidates=fill_rates,
        volume_indicator_candidates=(volume_indicators),
        gross_revenue=(volume_ledger.gross_revenue),
        truck_penalty=(volume_ledger.truck_penalty),
        net_realised_value=(volume_ledger.net_value),
        solving_time_seconds=float(solving_time_seconds),
        standard_water=(service_capacity_snapshot.standard_water),
    )
