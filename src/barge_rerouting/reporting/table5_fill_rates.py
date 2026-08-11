"""Candidate Table-5 AFR/NFR reconstructions.

The publication provides verbal AFR/NFR definitions but does not give
the complete aggregation formula. This module therefore computes
explicitly named candidate definitions from the same raw transport
evidence. No candidate is silently treated as the publication formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum
from statistics import fmean

from barge_rerouting.reporting.table5_sailing_occurrences import (
    Table5SailingOccurrence,
    build_table5_sailing_occurrences,
)
from barge_rerouting.reporting.table5_service_capacity import (
    SERVICE_CAPACITY_TOLERANCE,
    Table5ServiceCapacitySnapshot,
)


def _percentage(
    numerator: float,
    denominator: float,
) -> float:
    """Return a percentage with explicit zero-denominator handling."""
    if denominator <= SERVICE_CAPACITY_TOLERANCE:
        return 0.0

    return float(100.0 * numerator / denominator)


def _mean_percentage(
    ratios: list[float],
) -> float:
    """Return mean ratio as a percentage."""
    if not ratios:
        return 0.0

    return float(100.0 * fmean(ratios))


@dataclass(frozen=True, slots=True)
class Table5FillRateCandidates:
    """Explicit alternative AFR/NFR aggregation candidates."""

    transport_arc_count: int
    sailing_occurrence_count: int

    mean_arc_actual_pct: float
    mean_arc_nominal_pct: float

    capacity_weighted_actual_pct: float
    capacity_weighted_nominal_pct: float

    mean_sailing_peak_actual_pct: float
    mean_sailing_peak_nominal_pct: float

    @property
    def mean_arc_standard_water_residual(self) -> float:
        """Return AFR-NFR residual for mean-arc candidate."""
        return float(self.mean_arc_actual_pct - self.mean_arc_nominal_pct)

    @property
    def capacity_weighted_standard_water_residual(
        self,
    ) -> float:
        """Return AFR-NFR residual for capacity-weighted candidate."""
        return float(self.capacity_weighted_actual_pct - self.capacity_weighted_nominal_pct)

    @property
    def sailing_peak_standard_water_residual(
        self,
    ) -> float:
        """Return AFR-NFR residual for sailing-peak candidate."""
        return float(self.mean_sailing_peak_actual_pct - self.mean_sailing_peak_nominal_pct)


def _sailing_peak_actual_ratio(
    occurrence: Table5SailingOccurrence,
) -> float:
    """Return maximum final utilisation ratio across sailing legs."""
    ratios = [
        arc.final_load / arc.actual_capacity
        for arc in occurrence.arcs
        if (arc.actual_capacity > SERVICE_CAPACITY_TOLERANCE)
    ]

    if not ratios:
        return 0.0

    return float(max(ratios))


def _sailing_peak_nominal_ratio(
    occurrence: Table5SailingOccurrence,
) -> float:
    """Return maximum nominal-capacity utilisation over the sailing."""
    ratios = [
        arc.final_load / arc.nominal_capacity
        for arc in occurrence.arcs
        if (arc.nominal_capacity > SERVICE_CAPACITY_TOLERANCE)
    ]

    if not ratios:
        return 0.0

    return float(max(ratios))


def build_table5_fill_rate_candidates(
    snapshot: Table5ServiceCapacitySnapshot,
) -> Table5FillRateCandidates:
    """Compute named fill-rate candidates from raw evidence."""
    if not isinstance(
        snapshot,
        Table5ServiceCapacitySnapshot,
    ):
        raise TypeError("snapshot must be Table5ServiceCapacitySnapshot.")

    occurrences = build_table5_sailing_occurrences(snapshot)

    mean_arc_actual = _mean_percentage(
        [
            arc.final_load / arc.actual_capacity
            for arc in snapshot.arcs
            if (arc.actual_capacity > SERVICE_CAPACITY_TOLERANCE)
        ]
    )

    mean_arc_nominal = _mean_percentage(
        [
            arc.final_load / arc.nominal_capacity
            for arc in snapshot.arcs
            if (arc.nominal_capacity > SERVICE_CAPACITY_TOLERANCE)
        ]
    )

    weighted_actual = _percentage(
        fsum(arc.final_load for arc in snapshot.arcs),
        fsum(arc.actual_capacity for arc in snapshot.arcs),
    )

    weighted_nominal = _percentage(
        fsum(arc.final_load for arc in snapshot.arcs),
        fsum(arc.nominal_capacity for arc in snapshot.arcs),
    )

    sailing_actual = _mean_percentage(
        [_sailing_peak_actual_ratio(occurrence) for occurrence in occurrences]
    )

    sailing_nominal = _mean_percentage(
        [_sailing_peak_nominal_ratio(occurrence) for occurrence in occurrences]
    )

    return Table5FillRateCandidates(
        transport_arc_count=len(snapshot.arcs),
        sailing_occurrence_count=len(occurrences),
        mean_arc_actual_pct=(mean_arc_actual),
        mean_arc_nominal_pct=(mean_arc_nominal),
        capacity_weighted_actual_pct=(weighted_actual),
        capacity_weighted_nominal_pct=(weighted_nominal),
        mean_sailing_peak_actual_pct=(sailing_actual),
        mean_sailing_peak_nominal_pct=(sailing_nominal),
    )
