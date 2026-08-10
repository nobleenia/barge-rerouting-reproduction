"""Numerical cleanup tests for persisted recovery-flow decomposition."""

import pytest

from barge_rerouting.disruption.operational_execution import (
    _decompose_recovered_plan,
)
from barge_rerouting.disruption.recovery_transition import (
    RecoveredFragmentPlan,
    RecoveryArcFlow,
)
from barge_rerouting.experiments.phase11_table5_pilot import (
    build_table5_pilot_inputs,
)
from barge_rerouting.instance import (
    build_auxiliary_sink_arcs,
)

TRANSPORT_ARC_ID = "transport::63::table4::service_family_1::westbound::slot02"


def _disconnected_plan(
    volume: float,
) -> tuple[object, RecoveredFragmentPlan]:
    """Build the exact B52-A53 disconnected-flow geometry."""
    inputs = build_table5_pilot_inputs()
    instance = inputs.instance

    demand = instance.demand_by_id("K0372")

    transport_arc = instance.arc_by_id(TRANSPORT_ARC_ID)

    assert transport_arc.tail == (
        "B",
        52,
    )
    assert transport_arc.head == (
        "A",
        53,
    )
    assert demand.destination == "A"

    fragment_id = "K0372::numerical-dust-regression"

    delivery_arc = build_auxiliary_sink_arcs(
        demand_id=fragment_id,
        destination_nodes=(transport_arc.head,),
    )[0]

    plan = RecoveredFragmentPlan(
        event_id="booking::0428::K0428",
        recovery_time=42,
        fragment_id=fragment_id,
        demand_id="K0372",
        original_remaining_volume=volume,
        rerouting_source=("E", 42),
        immutable_arc_ids=(),
        barge_arc_flows=(
            RecoveryArcFlow(
                arc_id=TRANSPORT_ARC_ID,
                volume=volume,
            ),
            RecoveryArcFlow(
                arc_id=delivery_arc.arc_id,
                volume=volume,
            ),
        ),
        barge_delivered_volume=volume,
        truck_transfer=None,
    )

    return instance, plan


def test_decomposition_discards_observed_solver_dust() -> None:
    """The exact 1.056901e-6 FR residual is numerical zero."""
    instance, plan = _disconnected_plan(1.056901e-6)

    paths = _decompose_recovered_plan(
        instance,
        plan,
    )

    assert paths == ()


def test_decomposition_still_rejects_material_disconnected_flow() -> None:
    """Cleanup must not hide a materially disconnected recovery plan."""
    instance, plan = _disconnected_plan(1.0e-4)

    with pytest.raises(
        ValueError,
        match=("Persisted positive recovery flow remains undecomposed"),
    ):
        _decompose_recovered_plan(
            instance,
            plan,
        )
