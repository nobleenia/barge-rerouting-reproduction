"""HiGHS bridge for existing DOcplex MILP formulations.

The mathematical models continue to be constructed with DOcplex.

For HiGHS execution:

1. export the exact DOcplex model as CPLEX LP;
2. read that LP with HiGHS;
3. solve it;
4. recover primal values using preserved variable names;
5. construct the existing domain-specific solution objects.

This is a solver substitution, not a second implementation of the
DCA-RM or DCA-RRM mathematical formulations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import highspy

from barge_rerouting.optimization.dca_rm import (
    DcaRmCurrentFlowResult,
    DcaRmModelArtifacts,
    DcaRmSolution,
    FutureProtectionResult,
    FutureSelectorResult,
    FutureTentativeFlowResult,
)
from barge_rerouting.optimization.dca_rrm import (
    DcaRrmModelArtifacts,
    DcaRrmSolution,
)
from barge_rerouting.rerouting.optimization import (
    CurrentDemandFlowResult,
    FragmentFlowResult,
)


@dataclass(frozen=True, slots=True)
class HighsPrimalResult:
    """Solver-neutral primal result returned by the HiGHS bridge."""

    is_solved: bool
    solve_status: str
    objective_value: float | None
    values: dict[str, float]
    variable_count: int
    constraint_count: int


def _create_highs() -> highspy.Highs:
    """Create HiGHS across its incomplete third-party typing boundary."""
    return highspy.Highs()  # type: ignore[no-untyped-call]


def _read_highs_values(
    highs: highspy.Highs,
) -> dict[str, float]:
    """Return HiGHS primal values keyed by original LP variable name."""
    solution = highs.getSolution()

    values: dict[str, float] = {}

    for index, raw_value in enumerate(solution.col_value):
        status, name = highs.getColName(index)

        if status != highspy.HighsStatus.kOk:
            raise RuntimeError(f"Could not retrieve HiGHS column name at index {index}: {status}")

        selected_name = str(name)

        if not selected_name:
            raise RuntimeError("HiGHS returned an empty variable name.")

        if selected_name in values:
            raise RuntimeError(f"Duplicate HiGHS variable name: {selected_name}")

        values[selected_name] = float(raw_value)

    return values


def _value_of(
    values: dict[str, float],
    variable: Any,
) -> float:
    """Return one DOcplex variable's HiGHS primal value."""
    name = str(variable.name)

    if name not in values:
        raise KeyError(f"HiGHS solution contains no value for DOcplex variable {name}.")

    return float(values[name])


def solve_docplex_mip_with_highs(
    model: Any,
    *,
    time_limit_seconds: float,
    relative_mip_gap: float,
    log_output: bool,
) -> HighsPrimalResult:
    """Solve one already-built DOcplex MILP with HiGHS."""
    with TemporaryDirectory(prefix="barge_rerouting_highs_") as temporary_directory:
        exported_path = model.export_as_lp(
            path=temporary_directory,
            basename="model",
        )

        lp_path = Path(exported_path)

        highs = _create_highs()

        highs.setOptionValue(
            "output_flag",
            bool(log_output),
        )
        highs.setOptionValue(
            "time_limit",
            float(time_limit_seconds),
        )
        highs.setOptionValue(
            "mip_rel_gap",
            float(relative_mip_gap),
        )

        read_status = highs.readModel(str(lp_path))

        if read_status != highspy.HighsStatus.kOk:
            raise RuntimeError(f"HiGHS could not read exported DOcplex LP: {read_status}")

        run_status = highs.run()

        if run_status != highspy.HighsStatus.kOk:
            raise RuntimeError(f"HiGHS execution failed: {run_status}")

        model_status = highs.modelStatusToString(highs.getModelStatus())

        solve_status = f"HiGHS {highs.version()} {model_status}"

        # During the first production integration we accept only
        # proven optimal solutions. Time-limit incumbents can be
        # supported later with an explicit reporting contract.
        if model_status.lower() != "optimal":
            return HighsPrimalResult(
                is_solved=False,
                solve_status=solve_status,
                objective_value=None,
                values={},
                variable_count=highs.getNumCol(),
                constraint_count=highs.getNumRow(),
            )

        values = _read_highs_values(highs)

        if len(values) != model.number_of_variables:
            raise RuntimeError("HiGHS variable count does not match the exported DOcplex model.")

        return HighsPrimalResult(
            is_solved=True,
            solve_status=solve_status,
            objective_value=float(highs.getObjectiveValue()),
            values=values,
            variable_count=highs.getNumCol(),
            constraint_count=highs.getNumRow(),
        )


def solve_dca_rm_model_highs(
    artifacts: DcaRmModelArtifacts,
) -> DcaRmSolution:
    """Solve and extract one existing DCA-RM model using HiGHS."""
    if not isinstance(
        artifacts,
        DcaRmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRmModelArtifacts.")

    result = solve_docplex_mip_with_highs(
        artifacts.model,
        time_limit_seconds=(artifacts.instance.config.solver.time_limit_seconds),
        relative_mip_gap=(artifacts.instance.config.solver.relative_mip_gap),
        log_output=(artifacts.instance.config.solver.log_output),
    )

    if not result.is_solved or result.objective_value is None:
        return DcaRmSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            value_interpretation=(artifacts.value_interpretation),
            is_solved=False,
            solve_status=result.solve_status,
            objective_value=None,
            acceptance_fraction=None,
            current_revenue=None,
            future_expected_revenue=None,
            current_flows=(),
            selectors=(),
            protections=(),
            future_flows=(),
        )

    values = result.values

    acceptance = _value_of(
        values,
        artifacts.acceptance_variable,
    )

    current_flows = tuple(
        DcaRmCurrentFlowResult(
            arc_id=arc_id,
            volume=_value_of(
                values,
                variable,
            ),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    selectors = tuple(
        FutureSelectorResult(
            forecast_id=forecast_id,
            protection_level=level,
            selected_value=_value_of(
                values,
                variable,
            ),
        )
        for (
            forecast_id,
            level,
        ), variable in sorted(artifacts.selector_variables.items())
    )

    protections: list[FutureProtectionResult] = []

    for candidate in artifacts.future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id

        protected_volume = _value_of(
            values,
            artifacts.protected_volume_variables[forecast_id],
        )

        selected_level = int(round(protected_volume))

        protections.append(
            FutureProtectionResult(
                forecast_id=forecast_id,
                protection_level=selected_level,
                protected_volume=(protected_volume),
                credited_expected_volume=float(
                    forecast.protected_expected_volume(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
                credited_expected_revenue=float(
                    forecast.protected_expected_revenue(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
            )
        )

    future_flows = tuple(
        FutureTentativeFlowResult(
            forecast_id=forecast_id,
            arc_id=arc_id,
            volume=_value_of(
                values,
                variable,
            ),
        )
        for (
            forecast_id,
            arc_id,
        ), variable in sorted(artifacts.future_flow_variables.items())
    )

    current_revenue = float(artifacts.event.demand.maximum_revenue * acceptance)

    future_expected_revenue = float(
        sum(protection.credited_expected_revenue for protection in protections)
    )

    return DcaRmSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        value_interpretation=(artifacts.value_interpretation),
        is_solved=True,
        solve_status=result.solve_status,
        objective_value=(result.objective_value),
        acceptance_fraction=float(acceptance),
        current_revenue=current_revenue,
        future_expected_revenue=(future_expected_revenue),
        current_flows=current_flows,
        selectors=selectors,
        protections=tuple(protections),
        future_flows=future_flows,
    )


def solve_dca_rrm_model_highs(
    artifacts: DcaRrmModelArtifacts,
) -> DcaRrmSolution:
    """Solve and extract one existing DCA-RRM model using HiGHS."""
    if not isinstance(
        artifacts,
        DcaRrmModelArtifacts,
    ):
        raise TypeError("artifacts must be DcaRrmModelArtifacts.")

    result = solve_docplex_mip_with_highs(
        artifacts.model,
        time_limit_seconds=(artifacts.instance.config.solver.time_limit_seconds),
        relative_mip_gap=(artifacts.instance.config.solver.relative_mip_gap),
        log_output=(artifacts.instance.config.solver.log_output),
    )

    if not result.is_solved or result.objective_value is None:
        return DcaRrmSolution(
            event_id=artifacts.event.event_id,
            demand_id=artifacts.event.demand_id,
            value_interpretation=(artifacts.value_interpretation),
            is_solved=False,
            solve_status=result.solve_status,
            objective_value=None,
            acceptance_fraction=None,
            current_revenue=None,
            future_expected_revenue=None,
            current_flows=(),
            fragment_flows=(),
            selectors=(),
            protections=(),
            future_flows=(),
        )

    values = result.values

    acceptance = _value_of(
        values,
        artifacts.acceptance_variable,
    )

    current_flows = tuple(
        CurrentDemandFlowResult(
            arc_id=arc_id,
            volume=_value_of(
                values,
                variable,
            ),
        )
        for arc_id, variable in sorted(artifacts.current_flow_variables.items())
    )

    fragment_flows = tuple(
        FragmentFlowResult(
            fragment_id=fragment_id,
            arc_id=arc_id,
            volume=_value_of(
                values,
                variable,
            ),
        )
        for (
            fragment_id,
            arc_id,
        ), variable in sorted(artifacts.fragment_flow_variables.items())
    )

    selectors = tuple(
        FutureSelectorResult(
            forecast_id=forecast_id,
            protection_level=level,
            selected_value=_value_of(
                values,
                variable,
            ),
        )
        for (
            forecast_id,
            level,
        ), variable in sorted(artifacts.selector_variables.items())
    )

    protections: list[FutureProtectionResult] = []

    for candidate in artifacts.future_set.candidates:
        forecast = candidate.forecast
        forecast_id = candidate.forecast_id

        protected_volume = _value_of(
            values,
            artifacts.protected_volume_variables[forecast_id],
        )

        selected_level = int(round(protected_volume))

        protections.append(
            FutureProtectionResult(
                forecast_id=forecast_id,
                protection_level=selected_level,
                protected_volume=(protected_volume),
                credited_expected_volume=float(
                    forecast.protected_expected_volume(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
                credited_expected_revenue=float(
                    forecast.protected_expected_revenue(
                        selected_level,
                        interpretation=(artifacts.value_interpretation),
                    )
                ),
            )
        )

    future_flows = tuple(
        FutureTentativeFlowResult(
            forecast_id=forecast_id,
            arc_id=arc_id,
            volume=_value_of(
                values,
                variable,
            ),
        )
        for (
            forecast_id,
            arc_id,
        ), variable in sorted(artifacts.future_flow_variables.items())
    )

    current_revenue = float(artifacts.event.demand.maximum_revenue * acceptance)

    future_expected_revenue = float(
        sum(protection.credited_expected_revenue for protection in protections)
    )

    return DcaRrmSolution(
        event_id=artifacts.event.event_id,
        demand_id=artifacts.event.demand_id,
        value_interpretation=(artifacts.value_interpretation),
        is_solved=True,
        solve_status=result.solve_status,
        objective_value=(result.objective_value),
        acceptance_fraction=float(acceptance),
        current_revenue=current_revenue,
        future_expected_revenue=(future_expected_revenue),
        current_flows=current_flows,
        fragment_flows=fragment_flows,
        selectors=selectors,
        protections=tuple(protections),
        future_flows=future_flows,
    )
