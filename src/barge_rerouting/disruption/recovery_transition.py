"""Persistent operational state after status-triggered recovery."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.truck_recourse import (
    TRUCK_RECOURSE_TOLERANCE,
    TruckRecourseModelArtifacts,
    TruckRecourseSolution,
    TruckRecourseValidationReport,
    validate_truck_recourse_solution,
)
from barge_rerouting.domain import (
    TimeSpaceNode,
    validate_time_space_node,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)


def _nonnegative_finite(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite non-negative value."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric < -TRUCK_RECOURSE_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric)


def _positive_finite(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite positive value."""
    numeric = _nonnegative_finite(name, value)

    if numeric <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")

    return numeric


def _normalise_identifier(
    name: str,
    value: object,
) -> str:
    """Validate a non-empty identifier."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    normalised = value.strip()

    if not normalised:
        raise ValueError(f"{name} must be non-empty.")

    return normalised


@dataclass(frozen=True, slots=True)
class RecoveryArcFlow:
    """One positive planned barge flow after recovery."""

    arc_id: str
    volume: float

    def __post_init__(self) -> None:
        """Validate one persisted barge flow."""
        object.__setattr__(
            self,
            "arc_id",
            _normalise_identifier(
                "arc_id",
                self.arc_id,
            ),
        )
        object.__setattr__(
            self,
            "volume",
            _positive_finite(
                "volume",
                self.volume,
            ),
        )


@dataclass(frozen=True, slots=True)
class TruckTransferPlan:
    """Persistent record of cargo allocated to direct truck."""

    event_id: str
    fragment_id: str
    demand_id: str
    transfer_node: TimeSpaceNode
    volume: float
    penalty_per_teu: float

    def __post_init__(self) -> None:
        """Validate one truck-transfer record."""
        object.__setattr__(
            self,
            "event_id",
            _normalise_identifier(
                "event_id",
                self.event_id,
            ),
        )
        object.__setattr__(
            self,
            "fragment_id",
            _normalise_identifier(
                "fragment_id",
                self.fragment_id,
            ),
        )
        object.__setattr__(
            self,
            "demand_id",
            _normalise_identifier(
                "demand_id",
                self.demand_id,
            ),
        )
        object.__setattr__(
            self,
            "transfer_node",
            validate_time_space_node(
                self.transfer_node,
                field_name="transfer_node",
            ),
        )
        object.__setattr__(
            self,
            "volume",
            _positive_finite(
                "volume",
                self.volume,
            ),
        )
        object.__setattr__(
            self,
            "penalty_per_teu",
            _positive_finite(
                "penalty_per_teu",
                self.penalty_per_teu,
            ),
        )

    @property
    def transfer_time(self) -> int:
        """Return the terminal-time at which truck transfer occurs."""
        return int(self.transfer_node[1])

    @property
    def penalty_value(self) -> float:
        """Return the incurred truck penalty."""
        return float(self.volume * self.penalty_per_teu)


@dataclass(frozen=True, slots=True)
class RecoveredFragmentPlan:
    """Persistent operational plan for one recovered fragment."""

    event_id: str
    recovery_time: int
    fragment_id: str
    demand_id: str
    original_remaining_volume: float
    rerouting_source: TimeSpaceNode
    immutable_arc_ids: tuple[str, ...]
    barge_arc_flows: tuple[RecoveryArcFlow, ...]
    barge_delivered_volume: float
    truck_transfer: TruckTransferPlan | None

    def __post_init__(self) -> None:
        """Validate recovered fragment accounting."""
        event_id = _normalise_identifier(
            "event_id",
            self.event_id,
        )
        if isinstance(self.recovery_time, bool) or not isinstance(
            self.recovery_time,
            int,
        ):
            raise TypeError("recovery_time must be an integer.")

        if self.recovery_time < 0:
            raise ValueError("recovery_time must be non-negative.")

        fragment_id = _normalise_identifier(
            "fragment_id",
            self.fragment_id,
        )
        demand_id = _normalise_identifier(
            "demand_id",
            self.demand_id,
        )
        remaining = _positive_finite(
            "original_remaining_volume",
            self.original_remaining_volume,
        )
        source = validate_time_space_node(
            self.rerouting_source,
            field_name="rerouting_source",
        )

        if not isinstance(self.immutable_arc_ids, tuple):
            raise TypeError("immutable_arc_ids must be a tuple.")

        immutable_arc_ids = tuple(
            _normalise_identifier(
                "immutable arc identifier",
                arc_id,
            )
            for arc_id in self.immutable_arc_ids
        )

        if len(set(immutable_arc_ids)) != len(immutable_arc_ids):
            raise ValueError("immutable_arc_ids must not contain duplicates.")

        if not isinstance(self.barge_arc_flows, tuple):
            raise TypeError("barge_arc_flows must be a tuple.")

        flows = tuple(self.barge_arc_flows)

        for flow in flows:
            if not isinstance(flow, RecoveryArcFlow):
                raise TypeError("Every barge flow must be a RecoveryArcFlow.")

        flow_arc_ids = tuple(flow.arc_id for flow in flows)

        if len(set(flow_arc_ids)) != len(flow_arc_ids):
            raise ValueError("Persisted barge arc identifiers must be unique.")

        barge_delivered = _nonnegative_finite(
            "barge_delivered_volume",
            self.barge_delivered_volume,
        )

        transfer = self.truck_transfer

        if transfer is not None:
            if not isinstance(
                transfer,
                TruckTransferPlan,
            ):
                raise TypeError("truck_transfer must be a TruckTransferPlan or None.")

            if transfer.event_id != event_id:
                raise ValueError("Truck transfer must use the recovery event.")

            if transfer.fragment_id != fragment_id:
                raise ValueError("Truck transfer must use the fragment ID.")

            if transfer.demand_id != demand_id:
                raise ValueError("Truck transfer must use the demand ID.")

            if transfer.transfer_node != source:
                raise ValueError("Truck transfer must occur at the effective rerouting source.")

        truck_volume = 0.0 if transfer is None else transfer.volume

        if abs(remaining - barge_delivered - truck_volume) > TRUCK_RECOURSE_TOLERANCE:
            raise ValueError(
                "Recovered fragment accounting is inconsistent: "
                "remaining must equal barge plus truck."
            )

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(
            self,
            "fragment_id",
            fragment_id,
        )
        object.__setattr__(
            self,
            "demand_id",
            demand_id,
        )
        object.__setattr__(
            self,
            "original_remaining_volume",
            remaining,
        )
        object.__setattr__(
            self,
            "rerouting_source",
            source,
        )
        object.__setattr__(
            self,
            "immutable_arc_ids",
            immutable_arc_ids,
        )
        object.__setattr__(
            self,
            "barge_arc_flows",
            tuple(
                sorted(
                    flows,
                    key=lambda flow: flow.arc_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "barge_delivered_volume",
            barge_delivered,
        )

    @property
    def truck_volume(self) -> float:
        """Return volume assigned to truck."""
        if self.truck_transfer is None:
            return 0.0

        return float(self.truck_transfer.volume)

    @property
    def barge_volume(self) -> float:
        """Return volume remaining on the barge network."""
        return float(self.barge_delivered_volume)

    def barge_flow_on(
        self,
        arc_id: str,
    ) -> float:
        """Return persisted barge flow on one arc."""
        normalised = _normalise_identifier(
            "arc_id",
            arc_id,
        )

        for flow in self.barge_arc_flows:
            if flow.arc_id == normalised:
                return float(flow.volume)

        return 0.0


@dataclass(frozen=True, slots=True)
class RecoveryOperationalState:
    """Phase-10 operational overlay above contractual bookings."""

    booking_state: RollingBookingState
    active_fragment_plans: tuple[
        RecoveredFragmentPlan,
        ...,
    ] = ()
    truck_transfer_history: tuple[
        TruckTransferPlan,
        ...,
    ] = ()
    recovery_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate operational recovery history."""
        if not isinstance(
            self.booking_state,
            RollingBookingState,
        ):
            raise TypeError("booking_state must be a RollingBookingState.")

        if not isinstance(
            self.active_fragment_plans,
            tuple,
        ):
            raise TypeError("active_fragment_plans must be a tuple.")

        if not isinstance(
            self.truck_transfer_history,
            tuple,
        ):
            raise TypeError("truck_transfer_history must be a tuple.")

        if not isinstance(
            self.recovery_event_ids,
            tuple,
        ):
            raise TypeError("recovery_event_ids must be a tuple.")

        plans = tuple(self.active_fragment_plans)
        transfers = tuple(self.truck_transfer_history)

        for plan in plans:
            if not isinstance(
                plan,
                RecoveredFragmentPlan,
            ):
                raise TypeError("Every active plan must be a RecoveredFragmentPlan.")

        for transfer in transfers:
            if not isinstance(
                transfer,
                TruckTransferPlan,
            ):
                raise TypeError("Every truck-history entry must be a TruckTransferPlan.")

        event_ids = tuple(
            _normalise_identifier(
                "recovery event identifier",
                event_id,
            )
            for event_id in self.recovery_event_ids
        )

        if len(set(event_ids)) != len(event_ids):
            raise ValueError("recovery_event_ids must be unique.")

        fragment_ids = tuple(plan.fragment_id for plan in plans)

        if len(set(fragment_ids)) != len(fragment_ids):
            raise ValueError("Active fragment plans must use unique IDs.")

        known_events = set(event_ids)

        for plan in plans:
            if plan.event_id not in known_events:
                raise ValueError(
                    "Every active fragment plan must reference a recorded recovery event."
                )

        for transfer in transfers:
            if transfer.event_id not in known_events:
                raise ValueError("Every truck transfer must reference a recorded recovery event.")

        object.__setattr__(
            self,
            "active_fragment_plans",
            tuple(
                sorted(
                    plans,
                    key=lambda plan: plan.fragment_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "truck_transfer_history",
            transfers,
        )
        object.__setattr__(
            self,
            "recovery_event_ids",
            event_ids,
        )

    @classmethod
    def empty(
        cls,
        booking_state: RollingBookingState,
    ) -> RecoveryOperationalState:
        """Create an operational overlay from booking history."""
        return cls(booking_state=booking_state)

    @property
    def instance_fingerprint(self) -> str:
        """Return the underlying experiment fingerprint."""
        return str(self.booking_state.instance_fingerprint)

    @property
    def recovery_event_count(self) -> int:
        """Return number of persisted status recoveries."""
        return len(self.recovery_event_ids)

    @property
    def total_truck_volume(self) -> float:
        """Return cumulative truck allocation."""
        return float(sum(transfer.volume for transfer in self.truck_transfer_history))

    @property
    def total_truck_penalty(self) -> float:
        """Return cumulative truck penalty."""
        return float(sum(transfer.penalty_value for transfer in self.truck_transfer_history))

    def plan_for(
        self,
        fragment_id: str,
    ) -> RecoveredFragmentPlan:
        """Return the latest operational plan for a fragment."""
        normalised = _normalise_identifier(
            "fragment_id",
            fragment_id,
        )

        for plan in self.active_fragment_plans:
            if plan.fragment_id == normalised:
                return plan

        raise KeyError(f"Unknown recovered fragment: {normalised}")

    def with_recovery(
        self,
        *,
        event_id: str,
        fragment_plans: tuple[
            RecoveredFragmentPlan,
            ...,
        ],
        truck_transfers: tuple[
            TruckTransferPlan,
            ...,
        ],
    ) -> RecoveryOperationalState:
        """Persist one additional status-recovery decision."""
        normalised_event_id = _normalise_identifier(
            "event_id",
            event_id,
        )

        if normalised_event_id in self.recovery_event_ids:
            raise ValueError("A recovery event cannot be applied twice.")

        latest_by_fragment = {plan.fragment_id: plan for plan in self.active_fragment_plans}

        for plan in fragment_plans:
            if plan.event_id != normalised_event_id:
                raise ValueError("New fragment plans must use the applied event ID.")

            latest_by_fragment[plan.fragment_id] = plan

        for transfer in truck_transfers:
            if transfer.event_id != normalised_event_id:
                raise ValueError("New truck transfers must use the applied event ID.")

        return RecoveryOperationalState(
            booking_state=self.booking_state,
            active_fragment_plans=tuple(latest_by_fragment.values()),
            truck_transfer_history=(
                *self.truck_transfer_history,
                *truck_transfers,
            ),
            recovery_event_ids=(
                *self.recovery_event_ids,
                normalised_event_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class TruckRecourseTransitionResult:
    """Persistent result of one status-triggered recovery."""

    state_before: RecoveryOperationalState
    state_after: RecoveryOperationalState
    event_id: str
    fragment_plans: tuple[
        RecoveredFragmentPlan,
        ...,
    ]
    truck_transfers: tuple[
        TruckTransferPlan,
        ...,
    ]
    validation_report: TruckRecourseValidationReport

    def __post_init__(self) -> None:
        """Validate transition bookkeeping."""
        if not isinstance(
            self.state_before,
            RecoveryOperationalState,
        ):
            raise TypeError("state_before must be a RecoveryOperationalState.")

        if not isinstance(
            self.state_after,
            RecoveryOperationalState,
        ):
            raise TypeError("state_after must be a RecoveryOperationalState.")

        event_id = _normalise_identifier(
            "event_id",
            self.event_id,
        )

        if self.state_before.booking_state != self.state_after.booking_state:
            raise ValueError("A status recovery must not rewrite contractual booking history.")

        if self.state_after.recovery_event_count != self.state_before.recovery_event_count + 1:
            raise ValueError("A recovery transition must append exactly one recovery event.")

        if self.state_after.recovery_event_ids[-1] != event_id:
            raise ValueError("The appended recovery event ID does not match the transition.")

        if not isinstance(
            self.validation_report,
            TruckRecourseValidationReport,
        ):
            raise TypeError("validation_report must be a TruckRecourseValidationReport.")

        if not self.validation_report.is_valid:
            raise ValueError("A persisted recovery requires an independently valid solution.")

        object.__setattr__(
            self,
            "event_id",
            event_id,
        )


def apply_truck_recourse_solution(
    artifacts: TruckRecourseModelArtifacts,
    solution: TruckRecourseSolution,
    state_before: RecoveryOperationalState,
    *,
    tolerance: float = TRUCK_RECOURSE_TOLERANCE,
) -> TruckRecourseTransitionResult:
    """Persist solved barge/truck recovery without changing bookings."""
    if not isinstance(
        artifacts,
        TruckRecourseModelArtifacts,
    ):
        raise TypeError("artifacts must be TruckRecourseModelArtifacts.")

    if not isinstance(
        solution,
        TruckRecourseSolution,
    ):
        raise TypeError("solution must be a TruckRecourseSolution.")

    if not isinstance(
        state_before,
        RecoveryOperationalState,
    ):
        raise TypeError("state_before must be a RecoveryOperationalState.")

    if state_before.instance_fingerprint != artifacts.instance.demand_fingerprint:
        raise ValueError("The operational state belongs to another experiment instance.")

    report = validate_truck_recourse_solution(
        artifacts,
        solution,
        tolerance=tolerance,
    )

    if not report.is_valid:
        raise ValueError(
            f"Truck-recourse solution failed independent validation: {report.violations}."
        )

    event_id = artifacts.recovery_fragments.event_id

    if event_id in state_before.recovery_event_ids:
        raise ValueError("A recovery event cannot be applied twice.")

    fragment_plans: list[RecoveredFragmentPlan] = []
    truck_transfers: list[TruckTransferPlan] = []

    for index in artifacts.fragment_networks.indexes:
        fragment_id = index.fragment_id
        fragment_state = artifacts.recovery_fragments.fragment_state_for(fragment_id)

        barge_flows = tuple(
            RecoveryArcFlow(
                arc_id=result.arc_id,
                volume=float(result.volume),
            )
            for result in solution.barge_flows
            if result.fragment_id == fragment_id and result.volume > tolerance
        )

        barge_delivered = float(
            sum(
                solution.fragment_flow_on(
                    fragment_id,
                    sink_arc_id,
                )
                for sink_arc_id in index.sink_arc_ids
            )
        )

        truck_volume = float(solution.truck_volume_for(fragment_id))

        if abs(truck_volume) <= tolerance:
            truck_volume = 0.0

        transfer: TruckTransferPlan | None = None

        if truck_volume > tolerance:
            transfer = TruckTransferPlan(
                event_id=event_id,
                fragment_id=fragment_id,
                demand_id=index.demand_id,
                transfer_node=fragment_state.rerouting_source,
                volume=truck_volume,
                penalty_per_teu=(artifacts.truck_penalty_per_teu_by_demand[index.demand_id]),
            )

            truck_transfers.append(transfer)

        fragment_plans.append(
            RecoveredFragmentPlan(
                event_id=event_id,
                recovery_time=(artifacts.recovery_fragments.physical_time),
                fragment_id=fragment_id,
                demand_id=index.demand_id,
                original_remaining_volume=(fragment_state.volume),
                rerouting_source=(fragment_state.rerouting_source),
                immutable_arc_ids=(fragment_state.immutable_arc_ids),
                barge_arc_flows=barge_flows,
                barge_delivered_volume=barge_delivered,
                truck_transfer=transfer,
            )
        )

    fragment_plan_tuple = tuple(fragment_plans)
    truck_transfer_tuple = tuple(truck_transfers)

    state_after = state_before.with_recovery(
        event_id=event_id,
        fragment_plans=fragment_plan_tuple,
        truck_transfers=truck_transfer_tuple,
    )

    return TruckRecourseTransitionResult(
        state_before=state_before,
        state_after=state_after,
        event_id=event_id,
        fragment_plans=fragment_plan_tuple,
        truck_transfers=truck_transfer_tuple,
        validation_report=report,
    )
