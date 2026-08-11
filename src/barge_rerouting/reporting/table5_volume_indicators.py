"""Candidate Table-5 demand-volume indicator reconstructions.

The publication defines VTR, VFB, VOB and VOA verbally but does not
provide their complete mathematical equations or denominators.

This module therefore exposes explicitly named candidate definitions.
The candidates are reporting interpretations, not claims that the
publication used exactly these formulas.
"""

from __future__ import annotations

from dataclasses import dataclass

from barge_rerouting.reporting.table5_ledger import (
    LEDGER_TOLERANCE,
    Table5VolumeLedger,
)


def _percentage(
    numerator: float,
    denominator: float,
) -> float:
    """Return one percentage with explicit zero-denominator handling."""
    if denominator <= LEDGER_TOLERANCE:
        return 0.0

    return float(100.0 * numerator / denominator)


@dataclass(frozen=True, slots=True)
class Table5VolumeIndicatorCandidates:
    """Explicit candidate interpretations for Table-5 volume indicators."""

    requested_volume: float
    accepted_volume: float
    truck_volume: float
    final_barge_volume: float

    requested_request_count: int
    accepted_request_count: int

    vtr_requested_volume_pct: float
    vfb_requested_volume_pct: float
    vob_requested_volume_pct: float

    voa_request_count_pct: float
    voa_requested_volume_pct: float

    @property
    def vob_conservation_residual_pct(self) -> float:
        """Return VOB - VFB - VTR under the shared-volume candidate."""
        return float(
            self.vob_requested_volume_pct
            - self.vfb_requested_volume_pct
            - self.vtr_requested_volume_pct
        )

    @property
    def accepted_volume_conservation_residual(self) -> float:
        """Return accepted - final-barge - truck in raw TEU."""
        return float(self.accepted_volume - self.final_barge_volume - self.truck_volume)


def build_table5_volume_indicator_candidates(
    ledger: Table5VolumeLedger,
) -> Table5VolumeIndicatorCandidates:
    """Compute explicit volume/request-count indicator candidates."""
    if not isinstance(
        ledger,
        Table5VolumeLedger,
    ):
        raise TypeError("ledger must be Table5VolumeLedger.")

    requested_volume = float(ledger.requested_volume)

    accepted_volume = float(ledger.accepted_volume)

    truck_volume = float(ledger.truck_volume)

    final_barge_volume = float(ledger.final_barge_volume)

    requested_count = ledger.requested_request_count

    accepted_count = ledger.accepted_request_count

    vtr = _percentage(
        truck_volume,
        requested_volume,
    )

    vfb = _percentage(
        final_barge_volume,
        requested_volume,
    )

    vob = _percentage(
        accepted_volume,
        requested_volume,
    )

    voa_request = _percentage(
        float(accepted_count),
        float(requested_count),
    )

    # This candidate is intentionally retained even though it is
    # numerically identical to the current VOB requested-volume
    # candidate. Its presence documents the unresolved publication
    # ambiguity rather than silently choosing one interpretation.
    voa_volume = _percentage(
        accepted_volume,
        requested_volume,
    )

    result = Table5VolumeIndicatorCandidates(
        requested_volume=requested_volume,
        accepted_volume=accepted_volume,
        truck_volume=truck_volume,
        final_barge_volume=final_barge_volume,
        requested_request_count=(requested_count),
        accepted_request_count=(accepted_count),
        vtr_requested_volume_pct=vtr,
        vfb_requested_volume_pct=vfb,
        vob_requested_volume_pct=vob,
        voa_request_count_pct=(voa_request),
        voa_requested_volume_pct=(voa_volume),
    )

    if abs(result.accepted_volume_conservation_residual) > LEDGER_TOLERANCE:
        raise ValueError("Volume-indicator candidates violate accepted-volume conservation.")

    if abs(result.vob_conservation_residual_pct) > 100.0 * LEDGER_TOLERANCE:
        raise ValueError(
            "Candidate VOB/VFB/VTR percentages violate the shared-denominator identity."
        )

    return result
