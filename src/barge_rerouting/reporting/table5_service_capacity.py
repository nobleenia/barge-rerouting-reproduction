"""Raw transport-arc capacity and load evidence for Table 5 reporting.

This module deliberately persists physical arc-level evidence before
choosing a publication-facing AFR/NFR aggregation formula.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isfinite

from barge_rerouting.disruption.capacity import (
    ActualCapacityProfile,
    build_actual_capacity_profile,
)
from barge_rerouting.disruption.operational_execution import (
    build_operational_execution_snapshot,
)
from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.disruption.status import (
    ServiceStatusUpdateEvent,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)

SERVICE_CAPACITY_TOLERANCE = 1.0e-5


def _nonnegative(
    name: str,
    value: float,
) -> float:
    value = float(value)

    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if value < -SERVICE_CAPACITY_TOLERANCE:
        raise ValueError(f"{name} cannot be negative: {value}.")

    if abs(value) <= SERVICE_CAPACITY_TOLERANCE:
        return 0.0

    return value


@dataclass(frozen=True, slots=True)
class Table5TransportArcEvidence:
    """Raw reporting evidence for one scheduled transport arc."""

    arc_id: str
    service_id: str

    origin: str
    destination: str

    departure_time: int
    arrival_time: int

    nominal_capacity: float
    actual_capacity: float

    original_load: float
    final_load: float

    source_update_event_id: str | None = None

    def __post_init__(self) -> None:
        """Validate one transport-arc reporting record."""
        for name, value in (
            ("arc_id", self.arc_id),
            ("service_id", self.service_id),
            ("origin", self.origin),
            ("destination", self.destination),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string.")

            if not value.strip():
                raise ValueError(f"{name} cannot be empty.")

        if isinstance(self.departure_time, bool) or not isinstance(
            self.departure_time,
            int,
        ):
            raise TypeError("departure_time must be an integer.")

        if isinstance(self.arrival_time, bool) or not isinstance(
            self.arrival_time,
            int,
        ):
            raise TypeError("arrival_time must be an integer.")

        if self.departure_time < 0:
            raise ValueError("departure_time cannot be negative.")

        if self.arrival_time <= self.departure_time:
            raise ValueError("arrival_time must be after departure_time.")

        nominal = _nonnegative(
            "nominal_capacity",
            self.nominal_capacity,
        )
        actual = _nonnegative(
            "actual_capacity",
            self.actual_capacity,
        )
        original = _nonnegative(
            "original_load",
            self.original_load,
        )
        final = _nonnegative(
            "final_load",
            self.final_load,
        )

        if nominal <= SERVICE_CAPACITY_TOLERANCE:
            raise ValueError("nominal_capacity must be positive.")

        if actual <= SERVICE_CAPACITY_TOLERANCE:
            raise ValueError("actual_capacity must be positive.")

        if actual - nominal > SERVICE_CAPACITY_TOLERANCE:
            raise ValueError("actual_capacity cannot exceed nominal_capacity.")

        if self.source_update_event_id is not None:
            if not isinstance(
                self.source_update_event_id,
                str,
            ):
                raise TypeError("source_update_event_id must be a string or None.")

            if not self.source_update_event_id.strip():
                raise ValueError("source_update_event_id cannot be empty.")

        object.__setattr__(
            self,
            "arc_id",
            self.arc_id.strip(),
        )
        object.__setattr__(
            self,
            "service_id",
            self.service_id.strip(),
        )
        object.__setattr__(
            self,
            "origin",
            self.origin.strip(),
        )
        object.__setattr__(
            self,
            "destination",
            self.destination.strip(),
        )
        object.__setattr__(
            self,
            "nominal_capacity",
            nominal,
        )
        object.__setattr__(
            self,
            "actual_capacity",
            actual,
        )
        object.__setattr__(
            self,
            "original_load",
            original,
        )
        object.__setattr__(
            self,
            "final_load",
            final,
        )

    @property
    def water_level_factor(self) -> float:
        """Return actual-to-nominal capacity ratio."""
        return float(self.actual_capacity / self.nominal_capacity)

    @property
    def final_actual_capacity_violation(self) -> float:
        """Return final load above actual capacity, if any."""
        return float(
            max(
                0.0,
                self.final_load - self.actual_capacity,
            )
        )


@dataclass(frozen=True, slots=True)
class Table5ServiceCapacitySnapshot:
    """Raw arc-level transport load/capacity reporting evidence."""

    reporting_time: int
    instance_fingerprint: str
    arcs: tuple[
        Table5TransportArcEvidence,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate arc evidence identity."""
        if isinstance(self.reporting_time, bool) or not isinstance(
            self.reporting_time,
            int,
        ):
            raise TypeError("reporting_time must be an integer.")

        if self.reporting_time < 0:
            raise ValueError("reporting_time cannot be negative.")

        if not isinstance(
            self.instance_fingerprint,
            str,
        ):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(
            self.arcs,
            tuple,
        ):
            raise TypeError("arcs must be a tuple.")

        for arc in self.arcs:
            if not isinstance(
                arc,
                Table5TransportArcEvidence,
            ):
                raise TypeError("Every arc must be Table5TransportArcEvidence.")

        arc_ids = [arc.arc_id for arc in self.arcs]

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Transport arc identifiers must be unique.")

        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )

        object.__setattr__(
            self,
            "arcs",
            tuple(
                sorted(
                    self.arcs,
                    key=lambda arc: (
                        arc.departure_time,
                        arc.service_id,
                        arc.arc_id,
                    ),
                )
            ),
        )

    @property
    def transport_arc_count(self) -> int:
        """Return scheduled transport-arc count."""
        return len(self.arcs)

    @property
    def recurring_service_ids(
        self,
    ) -> tuple[str, ...]:
        """Return recurring service-pattern identifiers."""
        return tuple(sorted({arc.service_id for arc in self.arcs}))

    @property
    def standard_water(self) -> bool:
        """Return whether actual equals nominal capacity everywhere."""
        return all(
            abs(arc.actual_capacity - arc.nominal_capacity) <= SERVICE_CAPACITY_TOLERANCE
            for arc in self.arcs
        )

    @property
    def total_original_arc_load(self) -> float:
        """Return original transport work in TEU-arc units."""
        return float(fsum(arc.original_load for arc in self.arcs))

    @property
    def total_final_arc_load(self) -> float:
        """Return final transport work in TEU-arc units."""
        return float(fsum(arc.final_load for arc in self.arcs))

    @property
    def total_nominal_arc_capacity(self) -> float:
        """Return nominal capacity summed over transport arcs."""
        return float(fsum(arc.nominal_capacity for arc in self.arcs))

    @property
    def total_actual_arc_capacity(self) -> float:
        """Return actual capacity summed over transport arcs."""
        return float(fsum(arc.actual_capacity for arc in self.arcs))

    @property
    def max_final_actual_capacity_violation(
        self,
    ) -> float:
        """Return largest final arc overload."""
        return float(
            max(
                (arc.final_actual_capacity_violation for arc in self.arcs),
                default=0.0,
            )
        )


def _booking_state(
    state: (RollingBookingState | RecoveryOperationalState),
) -> RollingBookingState:
    if isinstance(
        state,
        RecoveryOperationalState,
    ):
        return state.booking_state

    if isinstance(
        state,
        RollingBookingState,
    ):
        return state

    raise TypeError("state must be RollingBookingState or RecoveryOperationalState.")


def _final_execution_snapshot(
    instance: ExperimentInstance,
    state: (RollingBookingState | RecoveryOperationalState),
    reporting_time: int,
) -> ExecutionSnapshot:
    if isinstance(
        state,
        RecoveryOperationalState,
    ):
        return build_operational_execution_snapshot(
            instance,
            state,
            physical_time=reporting_time,
        )

    return build_execution_snapshot(
        instance,
        state,
        physical_time=reporting_time,
    )


def _load_on_arc(
    snapshot: ExecutionSnapshot,
    arc_id: str,
) -> float:
    """Return cargo load represented on one physical arc."""
    return float(
        fsum(path.volume for path in snapshot.planned_paths if arc_id in path.physical_arc_ids)
    )


def build_table5_service_capacity_snapshot(
    *,
    instance: ExperimentInstance,
    final_state: (RollingBookingState | RecoveryOperationalState),
    reporting_time: int,
    status_updates: Sequence[ServiceStatusUpdateEvent] = (),
    historical_actual_capacity: bool = False,
) -> Table5ServiceCapacitySnapshot:
    """Build raw final transport-load and capacity evidence."""
    booking_state = _booking_state(final_state)

    original_execution = build_execution_snapshot(
        instance,
        booking_state,
        physical_time=reporting_time,
    )

    final_execution = _final_execution_snapshot(
        instance,
        final_state,
        reporting_time,
    )

    if not isinstance(
        historical_actual_capacity,
        bool,
    ):
        raise TypeError("historical_actual_capacity must be a boolean.")

    fingerprint = instance.demand_fingerprint

    for snapshot in (
        original_execution,
        final_execution,
    ):
        if snapshot.instance_fingerprint != fingerprint:
            raise ValueError("Reporting snapshots belong to different instances.")

        if snapshot.physical_time != reporting_time:
            raise ValueError("Reporting snapshots must use the reporting horizon.")

    if historical_actual_capacity:
        profiles_by_departure: dict[
            int,
            ActualCapacityProfile,
        ] = {}

        historical_states = []

        for arc in instance.arcs:
            if not arc.is_transport:
                continue

            departure_time = int(arc.tail[1])

            profile = profiles_by_departure.get(departure_time)

            if profile is None:
                profile = build_actual_capacity_profile(
                    instance,
                    physical_time=departure_time,
                    status_updates=status_updates,
                )

                if profile.instance_fingerprint != fingerprint:
                    raise ValueError("Historical capacity profile belongs to a different instance.")

                profiles_by_departure[departure_time] = profile

            historical_states.append(profile.state_for(arc.arc_id))

        capacity_states = tuple(historical_states)

    else:
        actual_profile = build_actual_capacity_profile(
            instance,
            physical_time=reporting_time,
            status_updates=status_updates,
        )

        if actual_profile.instance_fingerprint != fingerprint:
            raise ValueError("Actual-capacity profile belongs to a different instance.")

        if actual_profile.physical_time != reporting_time:
            raise ValueError("Actual-capacity profile must use the reporting horizon.")

        capacity_states = actual_profile.arc_states

    records: list[Table5TransportArcEvidence] = []

    for capacity in capacity_states:
        tail_terminal, tail_time = capacity.tail
        head_terminal, head_time = capacity.head

        records.append(
            Table5TransportArcEvidence(
                arc_id=capacity.arc_id,
                service_id=capacity.service_id,
                origin=tail_terminal,
                destination=head_terminal,
                departure_time=int(tail_time),
                arrival_time=int(head_time),
                nominal_capacity=float(capacity.nominal_capacity),
                actual_capacity=float(capacity.actual_capacity),
                original_load=_load_on_arc(
                    original_execution,
                    capacity.arc_id,
                ),
                final_load=_load_on_arc(
                    final_execution,
                    capacity.arc_id,
                ),
                source_update_event_id=(capacity.source_update_event_id),
            )
        )

    return Table5ServiceCapacitySnapshot(
        reporting_time=reporting_time,
        instance_fingerprint=fingerprint,
        arcs=tuple(records),
    )
