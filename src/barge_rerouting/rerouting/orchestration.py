"""Single-event orchestration of the Full-Reroute mechanism."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
    )

from barge_rerouting.instance import ExperimentInstance
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
from barge_rerouting.rerouting.optimization import (
    DcaRerouteSolution,
    build_dca_reroute_model,
)
from barge_rerouting.rerouting.transition import (
    DcaRerouteTransitionResult,
    apply_dca_reroute_solution,
)
from barge_rerouting.rolling_horizon.capacity import (
    TransportCapacitySnapshot,
    build_transport_capacity_snapshot,
)
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
    build_execution_snapshot,
)
from barge_rerouting.rolling_horizon.sequential import (
    SequentialBookingSolution,
    build_sequential_booking_model,
    solve_sequential_booking_model,
)
from barge_rerouting.rolling_horizon.state import (
    RollingBookingState,
)
from barge_rerouting.rolling_horizon.timeline import (
    BookingDecisionEvent,
)


@dataclass(frozen=True, slots=True)
class FullRerouteEventResult:
    """Complete diagnostic result of one Full-Reroute event."""

    event: BookingDecisionEvent
    state_before: RollingBookingState
    execution_before: ExecutionSnapshot
    ordinary_capacity: TransportCapacitySnapshot
    ordinary_solution: SequentialBookingSolution
    eligibility: ReroutingEligibilitySnapshot
    decision_snapshot: ReroutingDecisionSnapshot
    rerouting_capacity: ReroutingCapacitySnapshot
    fragment_networks: FragmentNetworkSnapshot
    reroute_solution: DcaRerouteSolution
    transition: DcaRerouteTransitionResult | None
    state_after: RollingBookingState
    execution_after: ExecutionSnapshot
    capacity_after: TransportCapacitySnapshot

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
            self.ordinary_solution,
            SequentialBookingSolution,
        ):
            raise TypeError("ordinary_solution must be a SequentialBookingSolution.")

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
            self.reroute_solution,
            DcaRerouteSolution,
        ):
            raise TypeError("reroute_solution must be a DcaRerouteSolution.")

        if self.transition is not None and not isinstance(
            self.transition,
            DcaRerouteTransitionResult,
        ):
            raise TypeError("transition must be a DcaRerouteTransitionResult or None.")

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
                    "must belong to the booking state instance."
                )

            if snapshot.physical_time != self.event.decision_time:
                raise ValueError("Every snapshot must use the event decision time.")

        if self.eligibility.current_event != self.event:
            raise ValueError("Eligibility must use the processed event.")

        if self.decision_snapshot.current_event_id != self.event.event_id:
            raise ValueError("The decision snapshot must use the processed event.")

        if self.rerouting_capacity.current_event_id != self.event.event_id:
            raise ValueError("The rerouting capacity must use the processed event.")

        if self.fragment_networks.current_event_id != self.event.event_id:
            raise ValueError("Fragment networks must use the processed event.")

        if self.ordinary_solution.event_id != self.event.event_id:
            raise ValueError("Ordinary solution must use the processed event.")

        if self.reroute_solution.event_id != self.event.event_id:
            raise ValueError("Reroute solution must use the processed event.")

        if self.reroute_solution.is_solved:
            if self.transition is None:
                raise ValueError("A solved rerouting decision requires a persistent transition.")

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
                raise ValueError("An unsolved rerouting decision cannot have a transition.")

            if self.state_after != self.state_before:
                raise ValueError("An unsolved event cannot change booking state.")

    @property
    def ordinary_acceptance_fraction(
        self,
    ) -> float | None:
        """Return the ordinary sequential-DCA acceptance."""
        if self.ordinary_solution.acceptance_fraction is None:
            return None

        return float(self.ordinary_solution.acceptance_fraction)

    @property
    def reroute_acceptance_fraction(
        self,
    ) -> float | None:
        """Return the Full-Reroute acceptance."""
        if self.reroute_solution.acceptance_fraction is None:
            return None

        return float(self.reroute_solution.acceptance_fraction)

    @property
    def event_was_processed(self) -> bool:
        """Return whether the rerouting model produced a solution."""
        return self.transition is not None

    @property
    def current_was_accepted(self) -> bool:
        """Return whether the current request was accepted."""
        return self.transition is not None and self.transition.current_was_accepted

    @property
    def rerouted_demand_ids(self) -> tuple[str, ...]:
        """Return prior demands whose routes were rebuilt."""
        if self.transition is None:
            return ()

        return tuple(str(demand_id) for demand_id in (self.transition.rerouted_demand_ids))

    @property
    def released_arc_ids(self) -> tuple[str, ...]:
        """Return transport arcs with released prior reservations."""
        return tuple(
            arc_id
            for arc_id in (self.rerouting_capacity.available_arc_ids)
            if (self.rerouting_capacity.released_volume_on(arc_id) > 1e-6)
        )


def run_full_reroute_event(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    *,
    solver_backend: SolverBackend | None = None,
) -> FullRerouteEventResult:
    """Run one complete Full-Reroute booking event."""

    # Import locally to avoid the solver_backend -> rerouting ->
    # orchestration -> solver_backend import cycle.
    from barge_rerouting.optimization.solver_backend import (
        SolverBackend,
        solve_dca_reroute_with_backend,
    )

    if solver_backend is None:
        solver_backend = SolverBackend.CPLEX

    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if state.instance_fingerprint != instance.demand_fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The Full-Reroute event must be the next unprocessed event.")

    execution_before = build_execution_snapshot(
        instance,
        state,
        physical_time=event.decision_time,
    )
    ordinary_capacity = build_transport_capacity_snapshot(
        instance,
        execution_before,
    )

    ordinary_artifacts = build_sequential_booking_model(
        instance,
        state,
        event,
        capacity_snapshot=ordinary_capacity,
    )

    try:
        ordinary_solution = solve_sequential_booking_model(ordinary_artifacts)
    finally:
        ordinary_artifacts.model.end()

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

    reroute_artifacts = build_dca_reroute_model(
        instance,
        state,
        event,
        rerouting_capacity,
        fragment_networks,
    )

    transition: DcaRerouteTransitionResult | None = None

    try:
        reroute_solution = solve_dca_reroute_with_backend(
            reroute_artifacts,
            backend=solver_backend,
        )

        if reroute_solution.is_solved:
            transition = apply_dca_reroute_solution(
                reroute_artifacts,
                reroute_solution,
            )
    finally:
        reroute_artifacts.model.end()

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

    return FullRerouteEventResult(
        event=event,
        state_before=state,
        execution_before=execution_before,
        ordinary_capacity=ordinary_capacity,
        ordinary_solution=ordinary_solution,
        eligibility=eligibility,
        decision_snapshot=decision_snapshot,
        rerouting_capacity=rerouting_capacity,
        fragment_networks=fragment_networks,
        reroute_solution=reroute_solution,
        transition=transition,
        state_after=state_after,
        execution_after=execution_after,
        capacity_after=capacity_after,
    )
