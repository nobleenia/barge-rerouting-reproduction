"""Joint current-demand allocation and accepted-fragment rerouting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import (
    DemandNetworkIndex,
    ExperimentInstance,
)
from barge_rerouting.rerouting.capacity import (
    ReroutingCapacitySnapshot,
)
from barge_rerouting.rerouting.network import (
    FragmentNetworkIndex,
    FragmentNetworkSnapshot,
)
from barge_rerouting.rolling_horizon import (
    BookingDecisionEvent,
    RollingBookingState,
)


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw_name = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw_name)


def _create_acceptance_variable(
    model: Any,
    *,
    demand_id: str,
    category: CustomerCategory,
) -> Any:
    """Create the current request's acceptance variable."""
    variable_name = _solver_name(
        "xi",
        demand_id,
    )

    if category is CustomerCategory.REGULAR:
        return model.continuous_var(
            lb=1.0,
            ub=1.0,
            name=variable_name,
        )

    if category is CustomerCategory.PARTIALLY_SPOT:
        return model.continuous_var(
            lb=0.0,
            ub=1.0,
            name=variable_name,
        )

    if category is CustomerCategory.FULLY_SPOT:
        return model.binary_var(
            name=variable_name,
        )

    raise ValueError(f"Unsupported customer category: {category}")


@dataclass(frozen=True, slots=True)
class DcaRerouteModelArtifacts:
    """DOcplex objects for one joint Full-Reroute decision."""

    instance: ExperimentInstance
    state: RollingBookingState
    event: BookingDecisionEvent
    capacity_snapshot: ReroutingCapacitySnapshot
    fragment_networks: FragmentNetworkSnapshot
    current_network_index: DemandNetworkIndex
    model: Any
    acceptance_variable: Any
    current_flow_variables: dict[str, Any]
    fragment_flow_variables: dict[tuple[str, str], Any]
    current_flow_balance_constraints: dict[object, Any]
    current_sink_balance_constraint: Any
    fragment_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ]
    fragment_sink_balance_constraints: dict[str, Any]
    capacity_constraints: dict[str, Any]
    available_capacities: dict[str, float]

    @property
    def current_flow_variable_count(self) -> int:
        """Return the current request's flow-variable count."""
        return len(self.current_flow_variables)

    @property
    def fragment_flow_variable_count(self) -> int:
        """Return all accepted-fragment flow-variable count."""
        return len(self.fragment_flow_variables)

    @property
    def total_flow_variable_count(self) -> int:
        """Return all flow-variable count."""
        return self.current_flow_variable_count + self.fragment_flow_variable_count

    @property
    def fragment_count(self) -> int:
        """Return the number of mandatory fragment commodities."""
        return len(self.fragment_networks.indexes)


@dataclass(frozen=True, slots=True)
class CurrentDemandFlowResult:
    """Solved current-request flow on one arc."""

    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class FragmentFlowResult:
    """Solved accepted-fragment flow on one arc."""

    fragment_id: str
    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class DcaRerouteSolution:
    """Extracted joint DCA-Reroute solution."""

    event_id: str
    demand_id: str
    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptance_fraction: float | None
    current_flows: tuple[CurrentDemandFlowResult, ...]
    fragment_flows: tuple[FragmentFlowResult, ...]

    def current_flow_on(
        self,
        arc_id: str,
    ) -> float:
        """Return current-demand flow on one arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_arc_id = arc_id.strip()

        for result in self.current_flows:
            if result.arc_id == normalised_arc_id:
                return float(result.volume)

        raise KeyError(f"Arc is not present in the current-demand solution: {normalised_arc_id}")

    def fragment_flow_on(
        self,
        fragment_id: str,
        arc_id: str,
    ) -> float:
        """Return one fragment's solved flow on one arc."""
        if not isinstance(fragment_id, str):
            raise TypeError("fragment_id must be a string.")

        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised_fragment_id = fragment_id.strip()
        normalised_arc_id = arc_id.strip()

        for result in self.fragment_flows:
            if result.fragment_id == normalised_fragment_id and result.arc_id == normalised_arc_id:
                return float(result.volume)

        raise KeyError(
            "Fragment-arc combination is not present in the "
            f"solution: {normalised_fragment_id}, "
            f"{normalised_arc_id}"
        )

    def fragment_delivered_volume(
        self,
        index: FragmentNetworkIndex,
    ) -> float:
        """Return solved fragment volume entering its logical sink."""
        if not isinstance(index, FragmentNetworkIndex):
            raise TypeError("index must be a FragmentNetworkIndex.")

        return float(
            sum(
                self.fragment_flow_on(
                    index.fragment_id,
                    arc_id,
                )
                for arc_id in index.sink_arc_ids
            )
        )


def _validate_joint_inputs(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    capacity_snapshot: ReroutingCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
) -> None:
    """Validate event and snapshot consistency."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(state, RollingBookingState):
        raise TypeError("state must be a RollingBookingState.")

    if not isinstance(event, BookingDecisionEvent):
        raise TypeError("event must be a BookingDecisionEvent.")

    if not isinstance(
        capacity_snapshot,
        ReroutingCapacitySnapshot,
    ):
        raise TypeError("capacity_snapshot must be a ReroutingCapacitySnapshot.")

    if not isinstance(
        fragment_networks,
        FragmentNetworkSnapshot,
    ):
        raise TypeError("fragment_networks must be a FragmentNetworkSnapshot.")

    fingerprint = instance.demand_fingerprint

    if state.instance_fingerprint != fingerprint:
        raise ValueError("The booking state belongs to another instance.")

    if event.sequence_number != state.next_sequence_number:
        raise ValueError("The booking event must be the next unprocessed event.")

    if capacity_snapshot.instance_fingerprint != fingerprint:
        raise ValueError("The rerouting-capacity snapshot belongs to another instance.")

    if fragment_networks.instance_fingerprint != fingerprint:
        raise ValueError("The fragment-network snapshot belongs to another instance.")

    if capacity_snapshot.current_event_id != event.event_id:
        raise ValueError("The capacity snapshot must use the booking event.")

    if fragment_networks.current_event_id != event.event_id:
        raise ValueError("The fragment networks must use the booking event.")

    if capacity_snapshot.physical_time != event.decision_time:
        raise ValueError("The capacity snapshot time must equal the decision time.")

    if fragment_networks.physical_time != event.decision_time:
        raise ValueError("The fragment-network time must equal the decision time.")

    instance_demand = instance.demand_by_id(event.demand_id)

    if instance_demand != event.demand:
        raise ValueError("The event demand does not match the instance.")


def build_dca_reroute_model(
    instance: ExperimentInstance,
    state: RollingBookingState,
    event: BookingDecisionEvent,
    capacity_snapshot: ReroutingCapacitySnapshot,
    fragment_networks: FragmentNetworkSnapshot,
) -> DcaRerouteModelArtifacts:
    """Build the joint current-request and fragment-routing model."""
    _validate_joint_inputs(
        instance,
        state,
        event,
        capacity_snapshot,
        fragment_networks,
    )

    demand = event.demand
    current_network_index = instance.network_index_for(demand.demand_id)
    available_transport_arc_ids = set(capacity_snapshot.available_arc_ids)

    unavailable_current_transport_arcs = tuple(
        sorted(
            arc_id
            for arc_id in current_network_index.feasible_arc_ids
            if instance.arc_by_id(arc_id).is_transport and arc_id not in available_transport_arc_ids
        )
    )

    if unavailable_current_transport_arcs:
        raise ValueError(
            "The current demand network contains non-bookable "
            "transport arcs: "
            f"{unavailable_current_transport_arcs}."
        )

    model = Model(
        name=_solver_name(
            "dca_reroute",
            event.sequence_number,
            demand.demand_id,
        ),
        log_output=instance.config.solver.log_output,
    )

    model.parameters.timelimit = instance.config.solver.time_limit_seconds
    model.parameters.mip.tolerances.mipgap = instance.config.solver.relative_mip_gap

    acceptance_variable = _create_acceptance_variable(
        model,
        demand_id=demand.demand_id,
        category=demand.category,
    )

    current_flow_variables: dict[str, Any] = {}

    for arc_number, arc_id in enumerate(current_network_index.all_flow_arc_ids):
        current_flow_variables[arc_id] = model.continuous_var(
            lb=0.0,
            name=_solver_name(
                "current_v",
                demand.demand_id,
                arc_number,
                arc_id,
            ),
        )

    fragment_flow_variables: dict[
        tuple[str, str],
        Any,
    ] = {}

    for index in fragment_networks.indexes:
        for arc_number, arc_id in enumerate(index.all_flow_arc_ids):
            fragment_flow_variables[
                (
                    index.fragment_id,
                    arc_id,
                )
            ] = model.continuous_var(
                lb=0.0,
                name=_solver_name(
                    "fragment_v",
                    index.fragment_id,
                    arc_number,
                    arc_id,
                ),
            )

    model.maximize(demand.maximum_revenue * acceptance_variable)

    current_flow_balance_constraints: dict[
        object,
        Any,
    ] = {}

    for node_index in current_network_index.node_flow_indexes:
        node = node_index.node

        outgoing_flow = model.sum(
            current_flow_variables[arc_id]
            for arc_id in (current_network_index.outgoing_flow_arc_ids(node))
        )
        incoming_flow = model.sum(
            current_flow_variables[arc_id]
            for arc_id in (current_network_index.incoming_flow_arc_ids(node))
        )

        required_balance = (
            demand.volume * acceptance_variable if node == current_network_index.source else 0.0
        )

        current_flow_balance_constraints[node] = model.add_constraint(
            outgoing_flow - incoming_flow == required_balance,
            ctname=_solver_name(
                "current_flow_balance",
                demand.demand_id,
                node[0],
                node[1],
            ),
        )

    current_sink_balance_constraint = model.add_constraint(
        model.sum(current_flow_variables[arc_id] for arc_id in (current_network_index.sink_arc_ids))
        == demand.volume * acceptance_variable,
        ctname=_solver_name(
            "current_sink_balance",
            demand.demand_id,
        ),
    )

    fragment_flow_balance_constraints: dict[
        tuple[str, object],
        Any,
    ] = {}
    fragment_sink_balance_constraints: dict[
        str,
        Any,
    ] = {}

    for index in fragment_networks.indexes:
        fragment_id = index.fragment_id

        for node_index in index.node_flow_indexes:
            node = node_index.node

            outgoing_flow = model.sum(
                fragment_flow_variables[
                    (
                        fragment_id,
                        arc_id,
                    )
                ]
                for arc_id in index.outgoing_flow_arc_ids(node)
            )
            incoming_flow = model.sum(
                fragment_flow_variables[
                    (
                        fragment_id,
                        arc_id,
                    )
                ]
                for arc_id in index.incoming_flow_arc_ids(node)
            )

            required_balance = index.volume if node == index.source else 0.0

            fragment_flow_balance_constraints[
                (
                    fragment_id,
                    node,
                )
            ] = model.add_constraint(
                outgoing_flow - incoming_flow == required_balance,
                ctname=_solver_name(
                    "fragment_flow_balance",
                    fragment_id,
                    node[0],
                    node[1],
                ),
            )

        fragment_sink_balance_constraints[fragment_id] = model.add_constraint(
            model.sum(
                fragment_flow_variables[
                    (
                        fragment_id,
                        arc_id,
                    )
                ]
                for arc_id in index.sink_arc_ids
            )
            == index.volume,
            ctname=_solver_name(
                "fragment_sink_balance",
                fragment_id,
            ),
        )

    capacity_constraints: dict[str, Any] = {}
    available_capacities: dict[str, float] = {}

    for arc_id in capacity_snapshot.available_arc_ids:
        arc = instance.arc_by_id(arc_id)

        if not arc.is_transport:
            raise ValueError("Rerouting capacity may only index transport arcs.")

        relevant_variables: list[Any] = []

        if arc_id in current_network_index.feasible_arc_ids:
            relevant_variables.append(current_flow_variables[arc_id])

        for index in fragment_networks.indexes:
            if arc_id not in index.feasible_arc_ids:
                continue

            relevant_variables.append(
                fragment_flow_variables[
                    (
                        index.fragment_id,
                        arc_id,
                    )
                ]
            )

        if not relevant_variables:
            continue

        available_capacity = float(capacity_snapshot.available_capacity_for(arc_id))

        available_capacities[arc_id] = available_capacity

        capacity_constraints[arc_id] = model.add_constraint(
            model.sum(relevant_variables) <= available_capacity,
            ctname=_solver_name(
                "rerouting_capacity",
                arc_id,
            ),
        )

    return DcaRerouteModelArtifacts(
        instance=instance,
        state=state,
        event=event,
        capacity_snapshot=capacity_snapshot,
        fragment_networks=fragment_networks,
        current_network_index=current_network_index,
        model=model,
        acceptance_variable=acceptance_variable,
        current_flow_variables=current_flow_variables,
        fragment_flow_variables=fragment_flow_variables,
        current_flow_balance_constraints=(current_flow_balance_constraints),
        current_sink_balance_constraint=(current_sink_balance_constraint),
        fragment_flow_balance_constraints=(fragment_flow_balance_constraints),
        fragment_sink_balance_constraints=(fragment_sink_balance_constraints),
        capacity_constraints=capacity_constraints,
        available_capacities=available_capacities,
    )


def solve_dca_reroute_model(
    artifacts: DcaRerouteModelArtifacts,
) -> DcaRerouteSolution:
    """Solve and extract one joint DCA-Reroute decision."""
    if not isinstance(
        artifacts,
        DcaRerouteModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRerouteModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=(artifacts.instance.config.solver.log_output))
    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return DcaRerouteSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            is_solved=False,
            solve_status=solve_status,
            objective_value=None,
            acceptance_fraction=None,
            current_flows=(),
            fragment_flows=(),
        )

    current_flows = tuple(
        CurrentDemandFlowResult(
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    fragment_flows = tuple(
        FragmentFlowResult(
            fragment_id=fragment_id,
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for (
            fragment_id,
            arc_id,
        ), variable in sorted(artifacts.fragment_flow_variables.items())
    )

    return DcaRerouteSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        is_solved=True,
        solve_status=solve_status,
        objective_value=float(raw_solution.objective_value),
        acceptance_fraction=float(raw_solution.get_value(artifacts.acceptance_variable)),
        current_flows=current_flows,
        fragment_flows=fragment_flows,
    )
