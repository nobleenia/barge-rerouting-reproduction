"""Canonical optimisation-instance assembly."""

from barge_rerouting.instance.builder import (
    assemble_experiment_instance,
)
from barge_rerouting.instance.delivery import (
    AuxiliarySinkArc,
    auxiliary_sink_id_for,
    build_auxiliary_sink_arcs,
)
from barge_rerouting.instance.model import (
    DemandNetworkIndex,
    ExperimentInstance,
    NodeFlowIndex,
)

__all__ = [
    "AuxiliarySinkArc",
    "DemandNetworkIndex",
    "ExperimentInstance",
    "NodeFlowIndex",
    "assemble_experiment_instance",
    "auxiliary_sink_id_for",
    "build_auxiliary_sink_arcs",
]
