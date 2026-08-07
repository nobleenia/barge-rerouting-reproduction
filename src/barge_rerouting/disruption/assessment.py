"""Detection of future commitment overload after capacity updates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from barge_rerouting.disruption.capacity import (
    ACTUAL_CAPACITY_TOLERANCE,
    ActualCapacityProfile,
)
from barge_rerouting.instance import ExperimentInstance
from barge_rerouting.rolling_horizon.execution import (
    ExecutionSnapshot,
)


def _validate_nonnegative_integer(
    name: str,
    value: object,
) -> int:
    """Validate and return a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value < 0:
        raise ValueError(f"{name} must be non-negative.")

    return value


def _validate_nonnegative_float(
    name: str,
    value: object,
) -> float:
    """Validate and return a finite non-negative float."""
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(f"{name} must be a real number.")

    numeric = float(value)

    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite.")

    if numeric < -ACTUAL_CAPACITY_TOLERANCE:
        raise ValueError(f"{name} must be non-negative.")

    return max(0.0, numeric)


def _normalise_identifiers(
    value: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    """Validate and sort a unique identifier tuple."""
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    identifiers: list[str] = []

    for identifier in value:
        if not isinstance(identifier, str):
            raise TypeError(f"Every identifier in {field_name} must be a string.")

        normalised = identifier.strip()

        if not normalised:
            raise ValueError(f"Every identifier in {field_name} must be non-empty.")

        identifiers.append(normalised)

    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{field_name} must not contain duplicates.")

    return tuple(sorted(identifiers))


@dataclass(frozen=True, slots=True)
class FutureArcDisruption:
    """Actual-capacity state of one future service leg."""

    arc_id: str
    service_id: str
    nominal_capacity: float
    actual_capacity: float
    committed_volume: float
    actual_bookable_capacity: float
    overload_volume: float
    affected_path_ids: tuple[str, ...] = ()
    affected_demand_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate future-arc capacity accounting."""
        if not isinstance(self.arc_id, str):
            raise TypeError("arc_id must be a string.")

        if not isinstance(self.service_id, str):
            raise TypeError("service_id must be a string.")

        arc_id = self.arc_id.strip()
        service_id = self.service_id.strip()

        if not arc_id:
            raise ValueError("arc_id must be non-empty.")

        if not service_id:
            raise ValueError("service_id must be non-empty.")

        nominal = _validate_nonnegative_float(
            "nominal_capacity",
            self.nominal_capacity,
        )
        actual = _validate_nonnegative_float(
            "actual_capacity",
            self.actual_capacity,
        )
        committed = _validate_nonnegative_float(
            "committed_volume",
            self.committed_volume,
        )
        bookable = _validate_nonnegative_float(
            "actual_bookable_capacity",
            self.actual_bookable_capacity,
        )
        overload = _validate_nonnegative_float(
            "overload_volume",
            self.overload_volume,
        )

        if actual - nominal > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Actual capacity must not exceed nominal capacity.")

        expected_bookable = max(
            0.0,
            actual - committed,
        )
        expected_overload = max(
            0.0,
            committed - actual,
        )

        if abs(bookable - expected_bookable) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError(
                "Actual bookable capacity is inconsistent with committed and actual volume."
            )

        if abs(overload - expected_overload) > ACTUAL_CAPACITY_TOLERANCE:
            raise ValueError("Overload volume is inconsistent with committed and actual capacity.")

        path_ids = _normalise_identifiers(
            self.affected_path_ids,
            field_name="affected_path_ids",
        )
        demand_ids = _normalise_identifiers(
            self.affected_demand_ids,
            field_name="affected_demand_ids",
        )

        if overload > ACTUAL_CAPACITY_TOLERANCE:
            if not path_ids:
                raise ValueError("An overloaded arc requires affected paths.")

            if not demand_ids:
                raise ValueError("An overloaded arc requires affected demands.")

        object.__setattr__(self, "arc_id", arc_id)
        object.__setattr__(
            self,
            "service_id",
            service_id,
        )
        object.__setattr__(
            self,
            "nominal_capacity",
            nominal,
        )
        object.__setattr__(
            self,
            "actual_capacity",
            actual,
        )
        object.__setattr__(
            self,
            "committed_volume",
            committed,
        )
        object.__setattr__(
            self,
            "actual_bookable_capacity",
            bookable,
        )
        object.__setattr__(
            self,
            "overload_volume",
            overload,
        )
        object.__setattr__(
            self,
            "affected_path_ids",
            path_ids,
        )
        object.__setattr__(
            self,
            "affected_demand_ids",
            demand_ids,
        )

    @property
    def is_overloaded(self) -> bool:
        """Return whether commitments exceed actual capacity."""
        return bool(self.overload_volume > ACTUAL_CAPACITY_TOLERANCE)

    @property
    def capacity_loss(self) -> float:
        """Return capacity removed relative to nominal."""
        return float(self.nominal_capacity - self.actual_capacity)


@dataclass(frozen=True, slots=True)
class DisruptionAssessment:
    """Future-capacity feasibility assessment at one time."""

    physical_time: int
    instance_fingerprint: str
    arc_states: tuple[FutureArcDisruption, ...]

    def __post_init__(self) -> None:
        """Validate assessment identity and arc uniqueness."""
        physical_time = _validate_nonnegative_integer(
            "physical_time",
            self.physical_time,
        )

        if not isinstance(self.instance_fingerprint, str):
            raise TypeError("instance_fingerprint must be a string.")

        fingerprint = self.instance_fingerprint.strip().lower()

        if len(fingerprint) != 64:
            raise ValueError("instance_fingerprint must contain 64 hexadecimal characters.")

        if any(character not in "0123456789abcdef" for character in fingerprint):
            raise ValueError("instance_fingerprint must be hexadecimal.")

        if not isinstance(self.arc_states, tuple):
            raise TypeError("arc_states must be a tuple.")

        for state in self.arc_states:
            if not isinstance(state, FutureArcDisruption):
                raise TypeError("Every arc state must be a FutureArcDisruption.")

        arc_ids = tuple(state.arc_id for state in self.arc_states)

        if len(set(arc_ids)) != len(arc_ids):
            raise ValueError("Disruption-assessment arc identifiers must be unique.")

        object.__setattr__(
            self,
            "physical_time",
            physical_time,
        )
        object.__setattr__(
            self,
            "instance_fingerprint",
            fingerprint,
        )
        object.__setattr__(
            self,
            "arc_states",
            tuple(
                sorted(
                    self.arc_states,
                    key=lambda state: state.arc_id,
                )
            ),
        )

    @property
    def is_feasible(self) -> bool:
        """Return whether every future commitment remains feasible."""
        return not any(state.is_overloaded for state in self.arc_states)

    @property
    def disrupted_arc_ids(self) -> tuple[str, ...]:
        """Return future arcs exceeding actual capacity."""
        return tuple(state.arc_id for state in self.arc_states if state.is_overloaded)

    @property
    def affected_demand_ids(self) -> tuple[str, ...]:
        """Return demands using at least one overloaded arc."""
        return tuple(
            sorted(
                {
                    demand_id
                    for state in self.arc_states
                    if state.is_overloaded
                    for demand_id in state.affected_demand_ids
                }
            )
        )

    @property
    def affected_path_ids(self) -> tuple[str, ...]:
        """Return paths using at least one overloaded arc."""
        return tuple(
            sorted(
                {
                    path_id
                    for state in self.arc_states
                    if state.is_overloaded
                    for path_id in state.affected_path_ids
                }
            )
        )

    @property
    def maximum_arc_overload(self) -> float:
        """Return the largest overload on one service leg."""
        return float(
            max(
                (state.overload_volume for state in self.arc_states),
                default=0.0,
            )
        )

    def state_for(
        self,
        arc_id: str,
    ) -> FutureArcDisruption:
        """Return assessment state for one future arc."""
        if not isinstance(arc_id, str):
            raise TypeError("arc_id must be a string.")

        normalised = arc_id.strip()

        if not normalised:
            raise ValueError("arc_id must be non-empty.")

        for state in self.arc_states:
            if state.arc_id == normalised:
                return state

        raise KeyError(f"Arc {normalised} is not a future transport arc in this assessment.")


def build_disruption_assessment(
    instance: ExperimentInstance,
    execution_snapshot: ExecutionSnapshot,
    actual_capacity_profile: ActualCapacityProfile,
) -> DisruptionAssessment:
    """Detect future commitments exceeding actual capacity."""
    if not isinstance(instance, ExperimentInstance):
        raise TypeError("instance must be an ExperimentInstance.")

    if not isinstance(
        execution_snapshot,
        ExecutionSnapshot,
    ):
        raise TypeError("execution_snapshot must be an ExecutionSnapshot.")

    if not isinstance(
        actual_capacity_profile,
        ActualCapacityProfile,
    ):
        raise TypeError("actual_capacity_profile must be an ActualCapacityProfile.")

    fingerprint = instance.demand_fingerprint

    if execution_snapshot.instance_fingerprint != fingerprint:
        raise ValueError("The execution snapshot belongs to another instance.")

    if actual_capacity_profile.instance_fingerprint != fingerprint:
        raise ValueError("The actual-capacity profile belongs to another instance.")

    if execution_snapshot.physical_time != actual_capacity_profile.physical_time:
        raise ValueError("Execution and actual-capacity states must use the same physical time.")

    states: list[FutureArcDisruption] = []

    for capacity_state in actual_capacity_profile.arc_states:
        if not capacity_state.is_future:
            continue

        matching_paths = tuple(
            path
            for path in execution_snapshot.planned_paths
            if capacity_state.arc_id in path.physical_arc_ids
        )

        committed_volume = float(sum(path.volume for path in matching_paths))
        actual_capacity = float(capacity_state.actual_capacity)
        overload = max(
            0.0,
            committed_volume - actual_capacity,
        )
        bookable = max(
            0.0,
            actual_capacity - committed_volume,
        )

        affected_paths = (
            tuple(path.path_id for path in matching_paths)
            if overload > ACTUAL_CAPACITY_TOLERANCE
            else ()
        )
        affected_demands = (
            tuple(sorted({path.demand_id for path in matching_paths}))
            if overload > ACTUAL_CAPACITY_TOLERANCE
            else ()
        )

        states.append(
            FutureArcDisruption(
                arc_id=capacity_state.arc_id,
                service_id=capacity_state.service_id,
                nominal_capacity=(capacity_state.nominal_capacity),
                actual_capacity=actual_capacity,
                committed_volume=committed_volume,
                actual_bookable_capacity=bookable,
                overload_volume=overload,
                affected_path_ids=affected_paths,
                affected_demand_ids=affected_demands,
            )
        )

    return DisruptionAssessment(
        physical_time=execution_snapshot.physical_time,
        instance_fingerprint=fingerprint,
        arc_states=tuple(states),
    )
