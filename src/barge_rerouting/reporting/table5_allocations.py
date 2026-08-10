"""Per-demand Table-5 contractual and terminal allocation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite

from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.rolling_horizon.commitment import (
    DemandCommitment,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)

ALLOCATION_TOLERANCE = 1.0e-5


def _nonnegative(
    name: str,
    value: float,
) -> float:
    value = float(value)

    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if value < -ALLOCATION_TOLERANCE:
        raise ValueError(f"{name} cannot be negative: {value}.")

    if abs(value) <= ALLOCATION_TOLERANCE:
        return 0.0

    return value


@dataclass(frozen=True, slots=True)
class Table5OriginalArcAllocation:
    """One original booking-time arc-flow record."""

    arc_id: str
    volume: float

    def __post_init__(self) -> None:
        """Validate one original allocation."""
        if not self.arc_id:
            raise ValueError("arc_id cannot be empty.")

        object.__setattr__(
            self,
            "volume",
            _nonnegative(
                "volume",
                self.volume,
            ),
        )


@dataclass(frozen=True, slots=True)
class Table5DemandAllocation:
    """Persist reporting evidence for one accepted demand."""

    demand_id: str

    requested_volume: float
    acceptance_fraction: float
    accepted_volume: float

    decision_sequence: int
    decision_time: int

    original_arc_allocations: tuple[
        Table5OriginalArcAllocation,
        ...,
    ]

    truck_volume: float
    truck_penalty: float
    final_barge_volume: float

    def __post_init__(self) -> None:
        """Validate per-demand terminal conservation."""
        if not self.demand_id:
            raise ValueError("demand_id cannot be empty.")

        requested = _nonnegative(
            "requested_volume",
            self.requested_volume,
        )

        accepted = _nonnegative(
            "accepted_volume",
            self.accepted_volume,
        )

        truck = _nonnegative(
            "truck_volume",
            self.truck_volume,
        )

        truck_penalty = _nonnegative(
            "truck_penalty",
            self.truck_penalty,
        )

        final_barge = _nonnegative(
            "final_barge_volume",
            self.final_barge_volume,
        )

        fraction = float(self.acceptance_fraction)

        if not isfinite(fraction):
            raise ValueError("acceptance_fraction must be finite.")

        if fraction < -ALLOCATION_TOLERANCE or fraction > 1.0 + ALLOCATION_TOLERANCE:
            raise ValueError("acceptance_fraction must lie in [0, 1].")

        expected_accepted = requested * fraction

        if abs(accepted - expected_accepted) > ALLOCATION_TOLERANCE:
            raise ValueError(
                "Accepted volume disagrees with requested volume times acceptance fraction."
            )

        allocation_residual = accepted - truck - final_barge

        if abs(allocation_residual) > ALLOCATION_TOLERANCE:
            raise ValueError(
                "Per-demand terminal allocation is inconsistent: "
                f"demand={self.demand_id}, "
                f"accepted={accepted}, "
                f"truck={truck}, "
                f"final_barge={final_barge}."
            )

        if self.decision_sequence < 0:
            raise ValueError("decision_sequence cannot be negative.")

        if self.decision_time < 0:
            raise ValueError("decision_time cannot be negative.")

        if not isinstance(
            self.original_arc_allocations,
            tuple,
        ):
            raise TypeError("original_arc_allocations must be a tuple.")

        arc_ids = [allocation.arc_id for allocation in self.original_arc_allocations]

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError(
                "Original arc identifiers must be unique within one demand commitment."
            )

        object.__setattr__(
            self,
            "requested_volume",
            requested,
        )
        object.__setattr__(
            self,
            "acceptance_fraction",
            fraction,
        )
        object.__setattr__(
            self,
            "accepted_volume",
            accepted,
        )
        object.__setattr__(
            self,
            "truck_volume",
            truck,
        )
        object.__setattr__(
            self,
            "truck_penalty",
            truck_penalty,
        )
        object.__setattr__(
            self,
            "final_barge_volume",
            final_barge,
        )


@dataclass(frozen=True, slots=True)
class Table5AllocationSnapshot:
    """Per-demand contractual and terminal allocation ledger."""

    demands: tuple[
        Table5DemandAllocation,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate demand identity uniqueness."""
        if not isinstance(
            self.demands,
            tuple,
        ):
            raise TypeError("demands must be a tuple.")

        demand_ids = [demand.demand_id for demand in self.demands]

        if len(set(demand_ids)) != len(demand_ids):
            raise ValueError("Demand identifiers must be unique.")

    @property
    def accepted_request_count(self) -> int:
        """Return positively accepted demand count."""
        return len(self.demands)

    @property
    def accepted_volume(self) -> float:
        """Return accepted cargo volume."""
        return float(fsum(demand.accepted_volume for demand in self.demands))

    @property
    def truck_volume(self) -> float:
        """Return cumulative terminal truck volume."""
        return float(fsum(demand.truck_volume for demand in self.demands))

    @property
    def truck_penalty(self) -> float:
        """Return cumulative terminal truck penalty."""
        return float(fsum(demand.truck_penalty for demand in self.demands))

    @property
    def final_barge_volume(self) -> float:
        """Return accepted cargo remaining on barge."""
        return float(fsum(demand.final_barge_volume for demand in self.demands))


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


def _original_arc_allocations(
    commitment: DemandCommitment,
) -> tuple[
    Table5OriginalArcAllocation,
    ...,
]:
    return tuple(
        Table5OriginalArcAllocation(
            arc_id=flow.arc_id,
            volume=float(flow.volume),
        )
        for flow in commitment.planned_arc_flows
    )


def _truck_totals_by_demand(
    state: (RollingBookingState | RecoveryOperationalState),
) -> dict[
    str,
    tuple[float, float],
]:
    if isinstance(
        state,
        RollingBookingState,
    ):
        return {}

    totals: dict[
        str,
        tuple[float, float],
    ] = {}

    volume_by_demand: dict[
        str,
        list[float],
    ] = {}

    penalty_by_demand: dict[
        str,
        list[float],
    ] = {}

    for transfer in state.truck_transfer_history:
        volume_by_demand.setdefault(
            transfer.demand_id,
            [],
        ).append(float(transfer.volume))

        penalty_by_demand.setdefault(
            transfer.demand_id,
            [],
        ).append(float(transfer.volume * transfer.penalty_per_teu))

    for demand_id in set(volume_by_demand) | set(penalty_by_demand):
        totals[demand_id] = (
            float(
                fsum(
                    volume_by_demand.get(
                        demand_id,
                        (),
                    )
                )
            ),
            float(
                fsum(
                    penalty_by_demand.get(
                        demand_id,
                        (),
                    )
                )
            ),
        )

    return totals


def build_table5_allocation_snapshot(
    final_state: (RollingBookingState | RecoveryOperationalState),
) -> Table5AllocationSnapshot:
    """Build rich reporting evidence from one completed policy state."""
    booking_state = _booking_state(final_state)

    truck_totals = _truck_totals_by_demand(final_state)

    records: list[Table5DemandAllocation] = []

    for commitment in booking_state.commitments:
        demand = commitment.demand

        accepted_volume = float(commitment.accepted_volume)

        truck_volume, truck_penalty = truck_totals.get(
            demand.demand_id,
            (
                0.0,
                0.0,
            ),
        )

        final_barge_volume = float(accepted_volume - truck_volume)

        records.append(
            Table5DemandAllocation(
                demand_id=(demand.demand_id),
                requested_volume=float(demand.volume),
                acceptance_fraction=float(commitment.acceptance_fraction),
                accepted_volume=(accepted_volume),
                decision_sequence=(commitment.decision_sequence),
                decision_time=(commitment.decision_time),
                original_arc_allocations=(_original_arc_allocations(commitment)),
                truck_volume=(truck_volume),
                truck_penalty=(truck_penalty),
                final_barge_volume=(final_barge_volume),
            )
        )

    records.sort(
        key=lambda record: (
            record.decision_sequence,
            record.demand_id,
        )
    )

    snapshot = Table5AllocationSnapshot(demands=tuple(records))

    uncommitted_truck_ids = set(truck_totals) - {demand.demand_id for demand in snapshot.demands}

    if uncommitted_truck_ids:
        raise ValueError(
            "Truck history references demands without "
            "accepted booking commitments: "
            f"{sorted(uncommitted_truck_ids)}."
        )

    return snapshot
