"""Raw Table-5 physical and economic reporting ledger."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite

from barge_rerouting.disruption.recovery_transition import (
    RecoveryOperationalState,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)

LEDGER_TOLERANCE = 1.0e-5


def _nonnegative(
    name: str,
    value: float,
) -> float:
    value = float(value)

    if not isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if value < -LEDGER_TOLERANCE:
        raise ValueError(f"{name} cannot be negative: {value}.")

    if abs(value) <= LEDGER_TOLERANCE:
        return 0.0

    return value


@dataclass(frozen=True, slots=True)
class Table5VolumeLedger:
    """Raw quantities retained before indicator denominators are chosen."""

    requested_request_count: int
    accepted_request_count: int

    requested_volume: float
    accepted_volume: float

    truck_volume: float
    final_barge_volume: float

    gross_revenue: float
    truck_penalty: float
    net_value: float

    def __post_init__(self) -> None:
        """Validate ledger conservation."""
        if self.requested_request_count < 0:
            raise ValueError("requested_request_count cannot be negative.")

        if self.accepted_request_count < 0:
            raise ValueError("accepted_request_count cannot be negative.")

        if self.accepted_request_count > self.requested_request_count:
            raise ValueError("accepted_request_count cannot exceed requested_request_count.")

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
        final_barge = _nonnegative(
            "final_barge_volume",
            self.final_barge_volume,
        )

        gross_revenue = float(self.gross_revenue)
        truck_penalty = _nonnegative(
            "truck_penalty",
            self.truck_penalty,
        )
        net_value = float(self.net_value)

        for name, value in (
            ("gross_revenue", gross_revenue),
            ("net_value", net_value),
        ):
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

        if accepted - requested > LEDGER_TOLERANCE:
            raise ValueError("Accepted volume cannot exceed requested volume.")

        allocation_residual = accepted - final_barge - truck

        if abs(allocation_residual) > LEDGER_TOLERANCE:
            raise ValueError(
                "Accepted-volume terminal allocation is "
                "inconsistent: "
                f"accepted={accepted}, "
                f"final_barge={final_barge}, "
                f"truck={truck}, "
                f"residual={allocation_residual}."
            )

        economic_residual = gross_revenue - truck_penalty - net_value

        if abs(economic_residual) > LEDGER_TOLERANCE:
            raise ValueError(
                "Economic ledger is inconsistent: "
                f"gross={gross_revenue}, "
                f"truck_penalty={truck_penalty}, "
                f"net={net_value}."
            )

        object.__setattr__(
            self,
            "requested_volume",
            requested,
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
            "final_barge_volume",
            final_barge,
        )
        object.__setattr__(
            self,
            "gross_revenue",
            gross_revenue,
        )
        object.__setattr__(
            self,
            "truck_penalty",
            truck_penalty,
        )
        object.__setattr__(
            self,
            "net_value",
            net_value,
        )

    @property
    def rejected_request_count(self) -> int:
        """Return requests with effectively zero final booking acceptance."""
        return self.requested_request_count - self.accepted_request_count

    @property
    def accepted_volume_rate_candidate(self) -> float:
        """Return raw accepted-volume/requested-volume percentage."""
        if self.requested_volume <= LEDGER_TOLERANCE:
            return 0.0

        return float(100.0 * self.accepted_volume / self.requested_volume)

    @property
    def accepted_request_rate_candidate(self) -> float:
        """Return raw accepted-request/request-count percentage."""
        if self.requested_request_count == 0:
            return 0.0

        return float(100.0 * self.accepted_request_count / self.requested_request_count)

    @property
    def truck_volume_rate_candidate(self) -> float:
        """Return truck/requested-volume percentage candidate."""
        if self.requested_volume <= LEDGER_TOLERANCE:
            return 0.0

        return float(100.0 * self.truck_volume / self.requested_volume)

    @property
    def final_barge_rate_candidate(self) -> float:
        """Return final-barge/requested-volume percentage candidate."""
        if self.requested_volume <= LEDGER_TOLERANCE:
            return 0.0

        return float(100.0 * self.final_barge_volume / self.requested_volume)


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


def _accepted_request_count(
    state: RollingBookingState,
) -> int:
    return len(state.accepted_demand_ids)


def _accepted_volume(
    state: RollingBookingState,
) -> float:
    return float(fsum(commitment.accepted_volume for commitment in state.commitments))


def _requested_population(
    state: RollingBookingState,
) -> tuple[int, float]:
    records = state.records

    return (
        len(records),
        float(fsum(record.event.demand.volume for record in records)),
    )


def build_table5_volume_ledger(
    *,
    final_state: (RollingBookingState | RecoveryOperationalState),
    gross_revenue: float,
    truck_penalty: float = 0.0,
) -> Table5VolumeLedger:
    """Build raw reporting quantities from a completed policy state."""
    booking_state = _booking_state(final_state)

    request_count, requested_volume = _requested_population(booking_state)

    accepted_count = _accepted_request_count(booking_state)

    accepted_volume = _accepted_volume(booking_state)

    if isinstance(
        final_state,
        RecoveryOperationalState,
    ):
        truck_volume = float(final_state.total_truck_volume)
    else:
        truck_volume = 0.0

    final_barge_volume = float(accepted_volume - truck_volume)

    return Table5VolumeLedger(
        requested_request_count=request_count,
        accepted_request_count=accepted_count,
        requested_volume=requested_volume,
        accepted_volume=accepted_volume,
        truck_volume=truck_volume,
        final_barge_volume=final_barge_volume,
        gross_revenue=float(gross_revenue),
        truck_penalty=float(truck_penalty),
        net_value=float(gross_revenue - truck_penalty),
    )
