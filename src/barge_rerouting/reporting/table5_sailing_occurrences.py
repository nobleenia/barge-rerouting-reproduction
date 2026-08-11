"""Reconstruct unique scheduled sailing occurrences for Table 5.

A recurring ``service_id`` identifies a service pattern, not one unique
physical sailing. Each physical A--E or E--A occurrence consists of four
connected transport legs.

This module reconstructs those occurrences from the raw transport-arc
evidence without introducing a publication-facing fill-rate formula.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from barge_rerouting.reporting.table5_service_capacity import (
    SERVICE_CAPACITY_TOLERANCE,
    Table5ServiceCapacitySnapshot,
    Table5TransportArcEvidence,
)


@dataclass(frozen=True, slots=True)
class Table5SailingOccurrence:
    """One unique scheduled A--E or E--A sailing occurrence."""

    occurrence_key: str
    service_id: str
    departure_time: int
    arrival_time: int
    arcs: tuple[
        Table5TransportArcEvidence,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate one connected physical sailing."""
        if not self.occurrence_key:
            raise ValueError("occurrence_key cannot be empty.")

        if not self.service_id:
            raise ValueError("service_id cannot be empty.")

        if not self.arcs:
            raise ValueError("A sailing occurrence must contain arcs.")

        if self.departure_time != self.arcs[0].departure_time:
            raise ValueError("Occurrence departure time disagrees with its first transport leg.")

        if self.arrival_time != self.arcs[-1].arrival_time:
            raise ValueError("Occurrence arrival time disagrees with its last transport leg.")

        for arc in self.arcs:
            if arc.service_id != self.service_id:
                raise ValueError("All occurrence arcs must share one recurring service_id.")

        for previous, current in zip(
            self.arcs[:-1],
            self.arcs[1:],
            strict=True,
        ):
            if previous.destination != current.origin:
                raise ValueError("Sailing occurrence transport legs are not terminal-connected.")

            if previous.arrival_time != current.departure_time:
                raise ValueError("Sailing occurrence transport legs are not time-connected.")

        nominal_capacities = {
            round(
                arc.nominal_capacity,
                12,
            )
            for arc in self.arcs
        }

        if len(nominal_capacities) != 1:
            raise ValueError(
                "A scheduled sailing must retain one nominal barge capacity across its legs."
            )

    @property
    def leg_count(self) -> int:
        """Return number of physical transport legs."""
        return len(self.arcs)

    @property
    def nominal_capacity(self) -> float:
        """Return scheduled nominal barge capacity."""
        return float(self.arcs[0].nominal_capacity)

    @property
    def minimum_actual_capacity(self) -> float:
        """Return minimum realised capacity over the sailing."""
        return float(min(arc.actual_capacity for arc in self.arcs))

    @property
    def maximum_actual_capacity(self) -> float:
        """Return maximum realised capacity over the sailing."""
        return float(max(arc.actual_capacity for arc in self.arcs))

    @property
    def original_peak_load(self) -> float:
        """Return maximum original booking load on any leg."""
        return float(max(arc.original_load for arc in self.arcs))

    @property
    def final_peak_load(self) -> float:
        """Return maximum final operational load on any leg."""
        return float(max(arc.final_load for arc in self.arcs))

    @property
    def standard_water(self) -> bool:
        """Return whether actual equals nominal capacity on all legs."""
        return all(
            abs(arc.actual_capacity - arc.nominal_capacity) <= SERVICE_CAPACITY_TOLERANCE
            for arc in self.arcs
        )


def _finish_occurrence(
    *,
    service_id: str,
    arcs: list[Table5TransportArcEvidence],
    expected_legs_per_occurrence: int,
) -> Table5SailingOccurrence:
    """Validate and construct one connected occurrence."""
    if len(arcs) != expected_legs_per_occurrence:
        raise ValueError(
            "Unexpected number of transport legs "
            "for reconstructed sailing: "
            f"service_id={service_id}, "
            f"departure={arcs[0].departure_time}, "
            f"legs={len(arcs)}, "
            f"expected={expected_legs_per_occurrence}."
        )

    first = arcs[0]
    last = arcs[-1]

    occurrence_key = f"{service_id}::departure_{first.departure_time}"

    return Table5SailingOccurrence(
        occurrence_key=occurrence_key,
        service_id=service_id,
        departure_time=first.departure_time,
        arrival_time=last.arrival_time,
        arcs=tuple(arcs),
    )


def build_table5_sailing_occurrences(
    snapshot: Table5ServiceCapacitySnapshot,
    *,
    expected_legs_per_occurrence: int = 4,
) -> tuple[
    Table5SailingOccurrence,
    ...,
]:
    """Reconstruct unique physical sailings from transport arcs."""
    if not isinstance(
        snapshot,
        Table5ServiceCapacitySnapshot,
    ):
        raise TypeError("snapshot must be Table5ServiceCapacitySnapshot.")

    if isinstance(
        expected_legs_per_occurrence,
        bool,
    ) or not isinstance(
        expected_legs_per_occurrence,
        int,
    ):
        raise TypeError("expected_legs_per_occurrence must be an integer.")

    if expected_legs_per_occurrence <= 0:
        raise ValueError("expected_legs_per_occurrence must be positive.")

    grouped: dict[
        str,
        list[Table5TransportArcEvidence],
    ] = defaultdict(list)

    for arc in snapshot.arcs:
        grouped[arc.service_id].append(arc)

    occurrences: list[Table5SailingOccurrence] = []

    for service_id, service_arcs in grouped.items():
        ordered = sorted(
            service_arcs,
            key=lambda arc: (
                arc.departure_time,
                arc.arrival_time,
                arc.arc_id,
            ),
        )

        current: list[Table5TransportArcEvidence] = []

        for arc in ordered:
            if not current:
                current = [arc]
                continue

            previous = current[-1]

            connected = (
                previous.destination == arc.origin and previous.arrival_time == arc.departure_time
            )

            if connected:
                current.append(arc)
                continue

            occurrences.append(
                _finish_occurrence(
                    service_id=service_id,
                    arcs=current,
                    expected_legs_per_occurrence=(expected_legs_per_occurrence),
                )
            )

            current = [arc]

        if current:
            occurrences.append(
                _finish_occurrence(
                    service_id=service_id,
                    arcs=current,
                    expected_legs_per_occurrence=(expected_legs_per_occurrence),
                )
            )

    result = tuple(
        sorted(
            occurrences,
            key=lambda occurrence: (
                occurrence.departure_time,
                occurrence.service_id,
                occurrence.occurrence_key,
            ),
        )
    )

    occurrence_keys = [occurrence.occurrence_key for occurrence in result]

    if len(set(occurrence_keys)) != len(occurrence_keys):
        raise ValueError("Reconstructed sailing occurrence keys must be unique.")

    return result
