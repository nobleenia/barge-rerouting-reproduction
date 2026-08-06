"""Single-event orchestration of combined DCA-RRM."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from barge_rerouting.domain import (
    FutureDemandForecast,
    FutureValueInterpretation,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.optimization.dca_rm import (
    FutureProtectionResult,
)
from barge_rerouting.optimization.dca_rrm import (
    DcaRrmSolution,
    build_dca_rrm_model,
    solve_dca_rrm_model,
    validate_dca_rrm_solution,
)
from barge_rerouting.rerouting.capacity import (
    ReroutingCapacitySnapshot,
    build_rerouting_capacity_snapshot,
)
from barge_rerouting.rerouting.eligibility import (
    ReroutingEligibilitySnapshot,
    detect_reroutable_demands,
)
from barge_rerouting.rerouting.in_transit import (
    ReroutingDecisionSnapshot,
    build_rerouting_decision_snapshot,
)
from barge_rerouting.rerouting.network import (
    FragmentNetworkSnapshot,
    build_fragment_network_snapshot,
)
from barge_rerouting.revenue_management.future_set import (
    FutureDemandSelectionMode,
    FutureDemandSet,
    select_a004_interacting_future_set,
    select_explicit_future_set,
)
from barge_rerouting.revenue_management.rrm_transition import (
    DcaRrmTransitionResult,
    apply_dca_rrm_solution,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
)

DCA_RRM_EVENT_TOLERANCE = 1e-6


@dataclass(frozen=True, slots=True)
class DcaRrmArcCapacityTransition:
    """Net bookable-capacity change after one DCA-RRM event.

    Unlike a myopic booking transition, DCA-RRM may increase
    bookable capacity on an arc by releasing an earlier future
    reservation during rerouting.
    """

    arc_id: str
    residual_before: float
    residual_after: float

    def __post_init__(self) -> None:
        """Validate and normalise one arc transition."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        arc_id = self.arc_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        values = {
            "residual_before": self.residual_before,
            "residual_after": self.residual_after,
        }

        normalised: dict[str, float] = {}

        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(
                value,
                (int, float),
            ):
                raise TypeError(f"{name} must be a real number.")

            numeric = float(value)

            if not isfinite(numeric):
                raise ValueError(f"{name} must be finite.")

            if numeric < -DCA_RRM_EVENT_TOLERANCE:
                raise ValueError(f"{name} must be non-negative.")

            normalised[name] = max(0.0, numeric)

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(
            self,
            "residual_before",
            normalised["residual_before"],
        )
        object.__setattr__(
            self,
            "residual_after",
            normalised["residual_after"],
        )

    @property
    def reserved_volume_change(self) -> float:
        """Return net newly reserved volume.

        Positive values mean additional reservation.
        Negative values mean net released reservation.
        """
        return float(self.residual_before - self.residual_after)

    @property
    def newly_reserved_volume(self) -> float:
        """Return the positive newly reserved component."""
        return float(max(0.0, self.reserved_volume_change))

    @property
    def released_volume(self) -> float:
        """Return the positive released-capacity component."""
        return float(max(0.0, -self.reserved_volume_change))


def _validate_lookahead(
    lookahead_periods: int | None,
) -> None:
    """Validate the optional look-ahead duration."""
    if lookahead_periods is None:
        return

    if isinstance(lookahead_periods, bool) or not isinstance(
        lookahead_periods,
        int,
    ):
        raise TypeError("lookahead_periods must be an integer or None.")

    if lookahead_periods < 0:
        raise ValueError("lookahead_periods must be non-negative.")


def _select_future_set(
    instance: ExperimentInstance,
    event: BookingDecisionEvent,
    forecasts: Sequence[FutureDemandForecast],
    *,
    selection_mode: FutureDemandSelectionMode,
    lookahead_periods: int | None,
) -> FutureDemandSet:
    """Construct the event's future-demand set."""
    if selection_mode is FutureDemandSelectionMode.EXPLICIT:
        return select_explicit_future_set(
            instance,
            event,
            forecasts,
        )

    if selection_mode is FutureDemandSelectionMode.A004_SHARED_ARC:
        lookahead_end_time = (
            None if lookahead_periods is None else event.decision_time + lookahead_periods
        )

        return select_a004_interacting_future_set(
            instance,
            event,
            forecasts,
            lookahead_end_time=lookahead_end_time,
        )

    raise ValueError(f"Unsupported future selection mode: {selection_mode}")


@dataclass(frozen=True, slots=True)
class DcaRrmEventResult:
    """Complete diagnostic result of one DCA-RRM event."""

    event: BookingDecisionEvent
    state_before: RollingBookingState
    execution_before: ExecutionSnapshot
    ordinary_capacity: TransportCapacitySnapshot
    eligibility: ReroutingEligibilitySnapshot
    decision_snapshot: ReroutingDecisionSnapshot
    rerouting_capacity: ReroutingCapacitySnapshot
    fragment_networks: FragmentNetworkSnapshot
    future_set: FutureDemandSet
    solution: DcaRrmSolution
    transition: DcaRrmTransitionResult | None
    state_after: RollingBookingState
    execution_after: ExecutionSnapshot
    capacity_after: TransportCapacitySnapshot
    capacity_transitions: tuple[
        DcaRrmArcCapacityTransition,
        ...,
    ]

    def __post_init__(self) -> None:
        """Validate event, state, and snapshot consistency."""
        if not isinstance(
            self.event,
            BookingDecisionEvent,
        ):
            raise TypeError("event must be a BookingDecisionEvent.")

        if not isinstance(
            self.state_before,
            RollingBookingState,
        ):
            raise TypeError("state_before must be a RollingBookingState.")

        if not isinstance(
            self.state_after,
            RollingBookingState,
        ):
            raise TypeError("state_after must be a RollingBookingState.")

        if not isinstance(
            self.execution_before,
            ExecutionSnapshot,
        ):
            raise TypeError("execution_before must be an ExecutionSnapshot.")

        if not isinstance(
            self.execution_after,
            ExecutionSnapshot,
        ):
            raise TypeError("execution_after must be an ExecutionSnapshot.")

        if not isinstance(
            self.ordinary_capacity,
            TransportCapacitySnapshot,
        ):
            raise TypeError("ordinary_capacity must be a TransportCapacitySnapshot.")

        if not isinstance(
            self.capacity_after,
            TransportCapacitySnapshot,
        ):
            raise TypeError("capacity_after must be a TransportCapacitySnapshot.")

        if not isinstance(
            self.eligibility,
            ReroutingEligibilitySnapshot,
        ):
            raise TypeError("eligibility must be a ReroutingEligibilitySnapshot.")

        if not isinstance(
            self.decision_snapshot,
            ReroutingDecisionSnapshot,
        ):
            raise TypeError("decision_snapshot must be a ReroutingDecisionSnapshot.")

        if not isinstance(
            self.rerouting_capacity,
            ReroutingCapacitySnapshot,
        ):
            raise TypeError("rerouting_capacity must be a ReroutingCapacitySnapshot.")

        if not isinstance(
            self.fragment_networks,
            FragmentNetworkSnapshot,
        ):
            raise TypeError("fragment_networks must be a FragmentNetworkSnapshot.")

        if not isinstance(
            self.future_set,
            FutureDemandSet,
        ):
            raise TypeError("future_set must be a FutureDemandSet.")

        if not isinstance(
            self.solution,
            DcaRrmSolution,
        ):
            raise TypeError("solution must be a DcaRrmSolution.")

        if self.transition is not None and not isinstance(
            self.transition,
            DcaRrmTransitionResult,
        ):
            raise TypeError("transition must be a DcaRrmTransitionResult or None.")

        if not isinstance(
            self.capacity_transitions,
            tuple,
        ):
            raise TypeError("capacity_transitions must be a tuple.")

        for capacity_transition in self.capacity_transitions:
            if not isinstance(
                capacity_transition,
                DcaRrmArcCapacityTransition,
            ):
                raise TypeError("Every capacity transition must be an DcaRrmArcCapacityTransition.")

        fingerprint = self.state_before.instance_fingerprint

        if self.state_after.instance_fingerprint != fingerprint:
            raise ValueError("Before and after states must belong to the same instance.")

        snapshots = (
            self.execution_before,
            self.ordinary_capacity,
            self.execution_after,
            self.capacity_after,
        )

        for snapshot in snapshots:
            if snapshot.instance_fingerprint != fingerprint:
                raise ValueError(
                    "Every execution and capacity snapshot "
                    "must belong to the booking-state instance."
                )

            if snapshot.physical_time != self.event.decision_time:
                raise ValueError("Every snapshot must use the event decision time.")

        if self.eligibility.current_event != self.event:
            raise ValueError("Eligibility must use the processed event.")

        if self.decision_snapshot.current_event_id != self.event.event_id:
            raise ValueError("The rerouting decision snapshot must use the processed event.")

        if self.rerouting_capacity.current_event_id != self.event.event_id:
            raise ValueError("The rerouting capacity must use the processed event.")

        if self.fragment_networks.current_event_id != self.event.event_id:
            raise ValueError("Fragment networks must use the processed event.")

        if self.future_set.current_event != self.event:
            raise ValueError("The future set must use the processed event.")

        if self.solution.event_id != self.event.event_id:
            raise ValueError("The DCA-RRM solution must use the processed event.")

        if self.solution.is_solved:
            if self.transition is None:
                raise ValueError("A solved DCA-RRM event requires a persistent transition.")

            if self.transition.state_before != self.state_before:
                raise ValueError("Transition state_before does not match the event input.")

            if self.transition.state_after != self.state_after:
                raise ValueError("Transition state_after does not match the event output.")

            if (
                self.state_after.processed_event_count
                != self.state_before.processed_event_count + 1
            ):
                raise ValueError("A solved event must append exactly one booking record.")
        else:
            if self.transition is not None:
                raise ValueError("An unsolved DCA-RRM event cannot have a transition.")

            if self.state_after != self.state_before:
                raise ValueError("An unsolved DCA-RRM event cannot change persistent state.")

        object.__setattr__(
            self,
            "capacity_transitions",
            tuple(
                sorted(
                    self.capacity_transitions,
                    key=lambda item: item.arc_id,
                )
            ),
        )

    @property
    def event_was_processed(self) -> bool:
        """Return whether the event produced a transition."""
        return self.transition is not None

    @property
    def acceptance_fraction(self) -> float | None:
        """Return the current acceptance decision."""
        value = self.solution.acceptance_fraction

        if value is None:
            return None

        return float(value)

    @property
    def accepted_volume(self) -> float:
        """Return realised accepted current volume."""
        if self.solution.acceptance_fraction is None:
            return 0.0

        return float(self.event.demand.volume * self.solution.acceptance_fraction)

    @property
    def current_was_accepted(self) -> bool:
        """Return whether positive current volume was accepted."""
        return bool(
            self.event_was_processed
            and self.acceptance_fraction is not None
            and self.acceptance_fraction > DCA_RRM_EVENT_TOLERANCE
        )

    @property
    def current_realised_revenue(self) -> float:
        """Return realised revenue from the current request."""
        return float(self.solution.current_revenue or 0.0)

    @property
    def optimisation_objective(self) -> float:
        """Return the event optimisation objective."""
        return float(self.solution.objective_value or 0.0)

    @property
    def future_expected_revenue(self) -> float:
        """Return the expected future contribution."""
        return float(self.solution.future_expected_revenue or 0.0)

    @property
    def forecast_ids(self) -> tuple[str, ...]:
        """Return selected future forecast identifiers."""
        return tuple(str(forecast_id) for forecast_id in self.future_set.forecast_ids)

    @property
    def protected_forecast_ids(self) -> tuple[str, ...]:
        """Return forecasts with positive selected protection."""
        return tuple(
            protection.forecast_id
            for protection in self.solution.protections
            if (protection.protected_volume > DCA_RRM_EVENT_TOLERANCE)
        )

    @property
    def selected_protection_volume(self) -> float:
        """Return total event-level selected future volume."""
        return float(sum(protection.protected_volume for protection in self.solution.protections))

    @property
    def discarded_tentative_future_volume(self) -> float:
        """Return future protection discarded after solving."""
        if self.transition is None:
            return 0.0

        return float(self.transition.discarded_protected_volume)

    @property
    def rerouted_demand_ids(self) -> tuple[str, ...]:
        """Return prior demands rebuilt by this event."""
        if self.transition is None:
            return ()

        return tuple(str(demand_id) for demand_id in self.transition.rerouted_demand_ids)

    @property
    def released_arc_ids(self) -> tuple[str, ...]:
        """Return arcs whose prior reservations were released."""
        return tuple(
            arc_id
            for arc_id in self.rerouting_capacity.available_arc_ids
            if (self.rerouting_capacity.released_volume_on(arc_id) > DCA_RRM_EVENT_TOLERANCE)
        )

    @property
    def released_reservation_volume(self) -> float:
        """Return cumulative released volume across arcs."""
        return float(self.rerouting_capacity.total_released_volume)

    def protection_for(
        self,
        forecast_id: str,
    ) -> FutureProtectionResult:
        """Return one event-level future protection."""
        return self.solution.protection_for(forecast_id)

    def capacity_transition_for(
        self,
        arc_id: str,
    ) -> DcaRrmArcCapacityTransition:
        """Return one realised capacity transition."""
        for transition in self.capacity_transitions:
            if transition.arc_id == arc_id:
                return transition

        raise KeyError(f"No capacity transition for {arc_id}.")


def run_dca_rrm_event(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    forecasts: Sequence[FutureDemandForecast],
    *,
    value_interpretation: FutureValueInterpretation,
    selection_mode: FutureDemandSelectionMode,
    lookahead_periods: int | None = None,
) -> DcaRrmEventResult:
    """Run one complete combined DCA-RRM booking event."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(
        value_interpretation,
        FutureValueInterpretation,
    ):
        raise TypeError("value_interpretation must be a FutureValueInterpretation.")

    if not isinstance(
        selection_mode,
        FutureDemandSelectionMode,
    ):
        raise TypeError("selection_mode must be a FutureDemandSelectionMode.")

    _validate_lookahead(lookahead_periods)

    if state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The DCA-RRM event must be the next unprocessed booking event.")

    execution_before = build_execution_snapshot(
        instance,
        state,
        physical_time=event.decision_time,
    )
    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution_before,
    )

    eligibility = detect_reroutable_demands(
        instance,
        state,
        execution_before,
        event,
    )
    decision_snapshot = build_rerouting_decision_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    rerouting_capacity = build_rerouting_capacity_snapshot(
        instance,
        ordinary_capacity,
        eligibility,
    )
    fragment_networks = build_fragment_network_snapshot(
        instance,
        decision_snapshot,
        rerouting_capacity,
    )

    future_set = _select_future_set(
        instance,
        event,
        forecasts,
        selection_mode=selection_mode,
        lookahead_periods=lookahead_periods,
    )

    artifacts = build_dca_rrm_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
        future_set,
        value_interpretation=value_interpretation,
    )

    transition: DcaRrmTransitionResult | None = None

    capacity_arc_ids = tuple(sorted(artifacts.available_capacities))
    residual_before = {
        arc_id: ordinary_capacity.bookable_capacity_for(arc_id) for arc_id in capacity_arc_ids
    }

    try:
        solution = solve_dca_rrm_model(artifacts)

        if solution.is_solved:
            validation = validate_dca_rrm_solution(
                artifacts,
                solution,
            )

            if not validation.is_valid:
                raise ValueError(
                    f"Solved DCA-RRM event failed independent validation: {validation.violations}."
                )

            transition = apply_dca_rrm_solution(
                artifacts,
                solution,
            )
    finally:
        artifacts.model.end()

    state_after = state if transition is None else transition.state_after

    execution_after = build_execution_snapshot(
        instance,
        state_after,
        physical_time=event.decision_time,
    )
    capacity_after = build_transport_capacity_snapshot(
        instance,
        execution_after,
    )

    capacity_transitions = tuple(
        DcaRrmArcCapacityTransition(
            arc_id=arc_id,
            residual_before=residual_before[arc_id],
            residual_after=(capacity_after.bookable_capacity_for(arc_id)),
        )
        for arc_id in capacity_arc_ids
    )

    return DcaRrmEventResult(
        event=event,
        state_before=state,
        execution_before=execution_before,
        ordinary_capacity=ordinary_capacity,
        eligibility=eligibility,
        decision_snapshot=decision_snapshot,
        rerouting_capacity=rerouting_capacity,
        fragment_networks=fragment_networks,
        future_set=future_set,
        solution=solution,
        transition=transition,
        state_after=state_after,
        execution_after=execution_after,
        capacity_after=capacity_after,
        capacity_transitions=capacity_transitions,
    )
