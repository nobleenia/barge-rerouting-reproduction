"""Deterministic current-demand allocation model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from docplex.mp.model import Model

from barge_rerouting.domain import CustomerCategory
from barge_rerouting.instance import ExperimentInstance


def _solver_name(*parts: object) -> str:
    """Create a readable CPLEX-compatible identifier."""
    raw_name = "__".join(str(part) for part in parts)
    return re.sub(r"[^A-Za-z0-9_]", "_", raw_name)


@dataclass(frozen=True, slots=True)
class DcaModelArtifacts:
    """DOcplex model and its indexed variables and constraints."""

    instance: ExperimentInstance
    model: Any
    acceptance_variables: dict[str, Any]
    flow_variables: dict[tuple[str, str], Any]
    flow_balance_constraints: dict[tuple[str, object], Any]
    sink_balance_constraints: dict[str, Any]
    capacity_constraints: dict[str, Any]

    @property
    def acceptance_variable_count(self) -> int:
        """Return the number of demand-acceptance variables."""
        return len(self.acceptance_variables)

    @property
    def flow_variable_count(self) -> int:
        """Return the number of demand-arc flow variables."""
        return len(self.flow_variables)


@dataclass(frozen=True, slots=True)
class DemandAcceptanceResult:
    """Solved acceptance fraction for one demand."""

    demand_id: str
    acceptance_fraction: float


@dataclass(frozen=True, slots=True)
class DemandArcFlowResult:
    """Solved flow for one demand-arc combination."""

    demand_id: str
    arc_id: str
    volume: float


@dataclass(frozen=True, slots=True)
class DcaSolution:
    """Extracted solution of one DCA model."""

    is_solved: bool
    solve_status: str
    objective_value: float | None
    acceptances: tuple[DemandAcceptanceResult, ...]
    flows: tuple[DemandArcFlowResult, ...]

    def acceptance_for(self, demand_id: str) -> float:
        """Return the solved acceptance fraction for one demand."""
        for result in self.acceptances:
            if result.demand_id == demand_id:
                return float(result.acceptance_fraction)

        raise KeyError(f"Unknown solved demand identifier: {demand_id}")

    def flow_for(self, demand_id: str, arc_id: str) -> float:
        """Return the solved flow for one demand-arc combination."""
        for result in self.flows:
            if result.demand_id == demand_id and result.arc_id == arc_id:
                return float(result.volume)

        raise KeyError(f"Unknown solved demand-arc combination: {demand_id}, {arc_id}")


def _create_acceptance_variable(
    model: Any,
    *,
    demand_id: str,
    category: CustomerCategory,
) -> Any:
    """Create an acceptance variable with the correct mathematical domain."""
    variable_name = _solver_name("xi", demand_id)

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
        return model.binary_var(name=variable_name)

    raise ValueError(f"Unsupported customer category: {category}")


def build_dca_model(
    instance: ExperimentInstance,
) -> DcaModelArtifacts:
    """Build the current-demand allocation mixed-integer programme."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    model = Model(
        name=_solver_name("dca", instance.config.experiment_name),
        log_output=instance.config.solver.log_output,
    )

    model.parameters.timelimit = instance.config.solver.time_limit_seconds
    model.parameters.mip.tolerances.mipgap = instance.config.solver.relative_mip_gap

    acceptance_variables: dict[str, Any] = {}
    flow_variables: dict[tuple[str, str], Any] = {}

    flow_balance_constraints: dict[tuple[str, object], Any] = {}
    sink_balance_constraints: dict[str, Any] = {}
    capacity_constraints: dict[str, Any] = {}

    for demand in instance.demands:
        acceptance_variables[demand.demand_id] = _create_acceptance_variable(
            model,
            demand_id=demand.demand_id,
            category=demand.category,
        )

    for network_index in instance.demand_network_indexes:
        demand_id = network_index.demand_id

        for arc_number, arc_id in enumerate(network_index.all_flow_arc_ids):
            flow_variables[(demand_id, arc_id)] = model.continuous_var(
                lb=0.0,
                name=_solver_name(
                    "v",
                    demand_id,
                    arc_number,
                    arc_id,
                ),
            )

    objective_terms = []

    for demand in instance.demands:
        acceptance_variable = acceptance_variables[demand.demand_id]

        objective_terms.append(demand.maximum_revenue * acceptance_variable)

    model.maximize(model.sum(objective_terms))

    for network_index in instance.demand_network_indexes:
        demand = network_index.demand
        demand_id = demand.demand_id
        acceptance_variable = acceptance_variables[demand_id]

        for node_index in network_index.node_flow_indexes:
            node = node_index.node

            outgoing_variables = [
                flow_variables[(demand_id, arc_id)]
                for arc_id in network_index.outgoing_flow_arc_ids(node)
            ]
            incoming_variables = [
                flow_variables[(demand_id, arc_id)]
                for arc_id in network_index.incoming_flow_arc_ids(node)
            ]

            left_hand_side = model.sum(outgoing_variables) - model.sum(incoming_variables)

            if node == network_index.source:
                right_hand_side = demand.volume * acceptance_variable
            else:
                right_hand_side = 0.0

            constraint = model.add_constraint(
                left_hand_side == right_hand_side,
                ctname=_solver_name(
                    "flow_balance",
                    demand_id,
                    node[0],
                    node[1],
                ),
            )

            flow_balance_constraints[(demand_id, node)] = constraint

        sink_variables = [
            flow_variables[(demand_id, arc_id)] for arc_id in network_index.sink_arc_ids
        ]

        sink_constraint = model.add_constraint(
            model.sum(sink_variables) == demand.volume * acceptance_variable,
            ctname=_solver_name(
                "sink_balance",
                demand_id,
            ),
        )

        sink_balance_constraints[demand_id] = sink_constraint

    for arc in instance.arcs:
        if not arc.is_transport:
            continue

        if arc.nominal_capacity is None:
            raise ValueError(f"Transport arc {arc.arc_id} has no capacity.")

        relevant_variables = []

        for network_index in instance.demand_network_indexes:
            if arc.arc_id not in network_index.feasible_arc_ids:
                continue

            relevant_variables.append(
                flow_variables[
                    (
                        network_index.demand_id,
                        arc.arc_id,
                    )
                ]
            )

        if not relevant_variables:
            continue

        capacity_constraint = model.add_constraint(
            model.sum(relevant_variables) <= arc.nominal_capacity,
            ctname=_solver_name(
                "capacity",
                arc.arc_id,
            ),
        )

        capacity_constraints[arc.arc_id] = capacity_constraint

    return DcaModelArtifacts(
        instance=instance,
        model=model,
        acceptance_variables=acceptance_variables,
        flow_variables=flow_variables,
        flow_balance_constraints=flow_balance_constraints,
        sink_balance_constraints=sink_balance_constraints,
        capacity_constraints=capacity_constraints,
    )


def solve_dca_model(
    artifacts: DcaModelArtifacts,
) -> DcaSolution:
    """Solve and extract one DCA model."""
    if not isinstance(artifacts, DcaModelArtifacts):
        raise TypeError("artifacts must be DcaModelArtifacts.")

    raw_solution = artifacts.model.solve(log_output=artifacts.instance.config.solver.log_output)
    solve_status = str(artifacts.model.solve_details.status)

    if raw_solution is None:
        return DcaSolution(
            is_solved=False,
            solve_status=solve_status,
            objective_value=None,
            acceptances=(),
            flows=(),
        )

    acceptances = tuple(
        DemandAcceptanceResult(
            demand_id=demand_id,
            acceptance_fraction=float(raw_solution.get_value(variable)),
        )
        for demand_id, variable in sorted(artifacts.acceptance_variables.items())
    )

    flows = tuple(
        DemandArcFlowResult(
            demand_id=demand_id,
            arc_id=arc_id,
            volume=float(raw_solution.get_value(variable)),
        )
        for (
            demand_id,
            arc_id,
        ), variable in sorted(artifacts.flow_variables.items())
    )

    return DcaSolution(
        is_solved=True,
        solve_status=solve_status,
        objective_value=float(raw_solution.objective_value),
        acceptances=acceptances,
        flows=flows,
    )
