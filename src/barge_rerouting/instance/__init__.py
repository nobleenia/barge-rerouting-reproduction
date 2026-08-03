"""Canonical optimisation-instance assembly."""

from barge_rerouting.instance.builder import (
    assemble_experiment_instance,
)
from barge_rerouting.instance.model import (
    DemandNetworkIndex,
    ExperimentInstance,
    NodeFlowIndex,
)

__all__ = [
    "DemandNetworkIndex",
    "ExperimentInstance",
    "NodeFlowIndex",
    "assemble_experiment_instance",
]
