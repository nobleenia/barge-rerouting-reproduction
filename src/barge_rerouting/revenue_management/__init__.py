"""Revenue-management forecasts and capacity-protection inputs."""

from barge_rerouting.revenue_management.future_set import (
    FutureDemandCandidate,
    FutureDemandExclusion,
    FutureDemandExclusionReason,
    FutureDemandSelectionMode,
    FutureDemandSet,
    select_a004_interacting_future_set,
    select_explicit_future_set,
)

__all__ = [
    "FutureDemandCandidate",
    "FutureDemandExclusion",
    "FutureDemandExclusionReason",
    "FutureDemandSelectionMode",
    "FutureDemandSet",
    "select_a004_interacting_future_set",
    "select_explicit_future_set",
]
