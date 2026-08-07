"""Fragment networks for status-triggered recovery."""

from __future__ import annotations

from barge_rerouting.disruption.recovery import (
    RecoveryFragmentSnapshot,
)
from barge_rerouting.disruption.recovery_capacity import (
    RecoveryCapacitySnapshot,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rerouting.network import (
    FragmentNetworkSnapshot,
    build_fragment_network_index_from_available_arcs,
)


def build_recovery_fragment_network_snapshot(
    instance: ExperimentInstance,
    recovery_fragments: RecoveryFragmentSnapshot,
    recovery_capacity: RecoveryCapacitySnapshot,
) -> FragmentNetworkSnapshot:
    """Build fragment networks against recovery transport arcs."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        recovery_fragments,
        RecoveryFragmentSnapshot,
    ):
        raise TypeError("recovery_fragments must be a RecoveryFragmentSnapshot.")

    if not isinstance(
        recovery_capacity,
        RecoveryCapacitySnapshot,
    ):
        raise TypeError("recovery_capacity must be a RecoveryCapacitySnapshot.")

    fingerprint = instance.demand_fingerprint

    if recovery_fragments.instance_fingerprint != fingerprint:
        raise ValueError("The recovery-fragment snapshot belongs to another instance.")

    if recovery_capacity.instance_fingerprint != fingerprint:
        raise ValueError("The recovery-capacity snapshot belongs to another instance.")

    if recovery_fragments.event_id != recovery_capacity.event_id:
        raise ValueError("Recovery fragments and capacity must use the same status event.")

    if recovery_fragments.physical_time != recovery_capacity.physical_time:
        raise ValueError("Recovery fragments and capacity must use the same physical time.")

    indexes = tuple(
        build_fragment_network_index_from_available_arcs(
            instance,
            fragment,
            tuple(recovery_capacity.available_arc_ids),
        )
        for fragment in recovery_fragments.fragments
    )

    return FragmentNetworkSnapshot(
        current_event_id=recovery_fragments.event_id,
        physical_time=recovery_fragments.physical_time,
        instance_fingerprint=fingerprint,
        indexes=indexes,
    )
