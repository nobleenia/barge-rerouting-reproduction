"""Publication-facing periodic service families for Phase 11.

The paper specifies:

- five consecutive terminals A--E;
- equal travel times between adjacent terminals;
- half-day model periods;
- weekly repetition every 14 periods;
- Service Family 1 with two service slots in each direction;
- Service Family 2 with four service slots in each direction.

The publication does not disclose the exact departure offsets or the
numerical adjacent-terminal travel duration.

The baseline below therefore preserves the published structure while
making those missing schedule details explicit controlled substitute
inputs. They must not be tuned to reproduce reported numerical results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from barge_rerouting.config import NetworkConfig
from barge_rerouting.domain import ScheduledTransportLeg
from barge_rerouting.experiments.phase11_table4 import (
    CONTROLLED_SUBSTITUTE_INPUT,
    TABLE4_CAPACITIES_TEU,
    TABLE4_SERVICE_FAMILIES,
)

TABLE4_TERMINALS: Final[tuple[str, ...]] = (
    "A",
    "B",
    "C",
    "D",
    "E",
)

TABLE4_REPEAT_PERIOD: Final = 14

# Controlled schedule assumption:
#
# Family 1: two departures per direction per 14-period cycle.
# Family 2: four departures per direction per 14-period cycle.
#
# Family 2 therefore has exactly twice the service frequency.
TABLE4_FAMILY_1_DEPARTURE_OFFSETS: Final[tuple[int, ...]] = (0, 7)

TABLE4_FAMILY_2_DEPARTURE_OFFSETS: Final[tuple[int, ...]] = (0, 3, 7, 10)

# The paper states equal adjacent-terminal travel times but does not
# disclose the numerical duration. The controlled baseline maps one
# adjacent leg to one half-day model period.
TABLE4_ADJACENT_TRAVEL_PERIODS: Final = 1


def _normalise_nonempty_string(
    name: str,
    value: object,
) -> str:
    """Validate and normalise one non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    normalised = value.strip()

    if not normalised:
        raise ValueError(f"{name} must be non-empty.")

    return normalised


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    """Validate one strictly positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be strictly positive.")

    return value


@dataclass(frozen=True, slots=True)
class PeriodicServiceFamilySpec:
    """One recurring publication-facing service family."""

    family_key: str
    label: str
    departure_offsets: tuple[int, ...]
    repeat_period: int = TABLE4_REPEAT_PERIOD
    adjacent_travel_periods: int = TABLE4_ADJACENT_TRAVEL_PERIODS
    reproduction_class: str = CONTROLLED_SUBSTITUTE_INPUT

    def __post_init__(self) -> None:
        """Validate one periodic service-family specification."""
        family_key = _normalise_nonempty_string(
            "family_key",
            self.family_key,
        )

        if family_key not in TABLE4_SERVICE_FAMILIES:
            raise ValueError(f"family_key must be one of {TABLE4_SERVICE_FAMILIES}.")

        label = _normalise_nonempty_string(
            "label",
            self.label,
        )

        if not isinstance(self.departure_offsets, tuple):
            raise TypeError("departure_offsets must be a tuple.")

        if not self.departure_offsets:
            raise ValueError("departure_offsets must be non-empty.")

        repeat_period = _validate_positive_integer(
            "repeat_period",
            self.repeat_period,
        )

        travel_periods = _validate_positive_integer(
            "adjacent_travel_periods",
            self.adjacent_travel_periods,
        )

        offsets: list[int] = []

        for offset in self.departure_offsets:
            if isinstance(offset, bool) or not isinstance(
                offset,
                int,
            ):
                raise TypeError("Every departure offset must be an integer.")

            if offset < 0:
                raise ValueError("Departure offsets must be non-negative.")

            if offset >= repeat_period:
                raise ValueError("Departure offsets must be below the repeat period.")

            offsets.append(offset)

        normalised_offsets = tuple(sorted(offsets))

        if len(set(normalised_offsets)) != len(normalised_offsets):
            raise ValueError("Departure offsets must be unique.")

        expected_slot_count = 2 if family_key == "service_family_1" else 4

        if len(normalised_offsets) != expected_slot_count:
            raise ValueError(
                f"{family_key} requires exactly {expected_slot_count} service slots per direction."
            )

        reproduction_class = _normalise_nonempty_string(
            "reproduction_class",
            self.reproduction_class,
        )

        if reproduction_class != CONTROLLED_SUBSTITUTE_INPUT:
            raise ValueError(
                "The default Phase 11 service schedules "
                "must remain classified as "
                "controlled_substitute_input."
            )

        object.__setattr__(
            self,
            "family_key",
            family_key,
        )
        object.__setattr__(
            self,
            "label",
            label,
        )
        object.__setattr__(
            self,
            "departure_offsets",
            normalised_offsets,
        )
        object.__setattr__(
            self,
            "repeat_period",
            repeat_period,
        )
        object.__setattr__(
            self,
            "adjacent_travel_periods",
            travel_periods,
        )
        object.__setattr__(
            self,
            "reproduction_class",
            reproduction_class,
        )

    @property
    def service_slots_per_direction(self) -> int:
        """Return recurring service slots in each direction."""
        return len(self.departure_offsets)

    @property
    def total_directional_service_slots(self) -> int:
        """Return eastbound plus westbound service slots."""
        return 2 * self.service_slots_per_direction


def default_table4_service_family_specs() -> tuple[PeriodicServiceFamilySpec, ...]:
    """Return the two controlled Table 4 service families."""
    return (
        PeriodicServiceFamilySpec(
            family_key="service_family_1",
            label="Service Family 1",
            departure_offsets=(TABLE4_FAMILY_1_DEPARTURE_OFFSETS),
        ),
        PeriodicServiceFamilySpec(
            family_key="service_family_2",
            label="Service Family 2",
            departure_offsets=(TABLE4_FAMILY_2_DEPARTURE_OFFSETS),
        ),
    )


def table4_service_family_spec(
    family_key: str,
) -> PeriodicServiceFamilySpec:
    """Return one default Table 4 service-family specification."""
    selected = _normalise_nonempty_string(
        "family_key",
        family_key,
    )

    for spec in default_table4_service_family_specs():
        if spec.family_key == selected:
            return spec

    raise KeyError(f"No Table 4 service family for {selected}.")


def _validate_time_periods(
    time_periods: tuple[int, ...],
) -> tuple[int, ...]:
    """Validate a contiguous half-day integer time grid."""
    if not isinstance(time_periods, tuple):
        raise TypeError("time_periods must be a tuple.")

    if len(time_periods) < 2:
        raise ValueError("At least two time periods are required.")

    for value in time_periods:
        if isinstance(value, bool) or not isinstance(
            value,
            int,
        ):
            raise TypeError("Every time period must be an integer.")

    if tuple(sorted(time_periods)) != time_periods:
        raise ValueError("time_periods must be sorted.")

    if len(set(time_periods)) != len(time_periods):
        raise ValueError("time_periods must be unique.")

    expected = tuple(
        range(
            time_periods[0],
            time_periods[-1] + 1,
        )
    )

    if time_periods != expected:
        raise ValueError(
            "Phase 11 publication-facing schedules require a contiguous half-day time grid."
        )

    return time_periods


def _validate_capacity_teu_for(
    capacity_teu: object,
    *,
    allowed_capacities_teu: tuple[int, ...],
    capacity_context: str,
) -> int:
    """Validate one experiment-specific nominal service capacity."""
    if isinstance(capacity_teu, bool) or not isinstance(
        capacity_teu,
        int,
    ):
        raise TypeError("capacity_teu must be an integer.")

    if not allowed_capacities_teu:
        raise ValueError("allowed_capacities_teu cannot be empty.")

    if not capacity_context:
        raise ValueError("capacity_context cannot be empty.")

    if capacity_teu not in allowed_capacities_teu:
        raise ValueError(f"{capacity_context} capacity must be one of {allowed_capacities_teu}.")

    return capacity_teu


def _validate_capacity_teu(
    capacity_teu: object,
) -> int:
    """Validate one frozen Table 4 nominal service capacity."""
    return _validate_capacity_teu_for(
        capacity_teu,
        allowed_capacities_teu=TABLE4_CAPACITIES_TEU,
        capacity_context="Table 4",
    )


def _service_id(
    spec: PeriodicServiceFamilySpec,
    *,
    direction: str,
    slot_number: int,
) -> str:
    """Return a recurring scheduled-service identifier."""
    return f"table4::{spec.family_key}::{direction}::slot{slot_number:02d}"


def _direction_pairs(
    direction: str,
) -> tuple[tuple[str, str], ...]:
    """Return adjacent corridor pairs for one direction."""
    if direction == "eastbound":
        return tuple(
            zip(
                TABLE4_TERMINALS[:-1],
                TABLE4_TERMINALS[1:],
                strict=True,
            )
        )

    if direction == "westbound":
        reversed_terminals = tuple(reversed(TABLE4_TERMINALS))

        return tuple(
            zip(
                reversed_terminals[:-1],
                reversed_terminals[1:],
                strict=True,
            )
        )

    raise ValueError(f"Unsupported direction: {direction}.")


def build_periodic_corridor_transport_legs(
    *,
    time_periods: tuple[int, ...],
    service_family: str,
    capacity_teu: int,
    allowed_capacities_teu: tuple[int, ...] | None = None,
    capacity_context: str = "Table 4",
) -> tuple[ScheduledTransportLeg, ...]:
    """Build recurring A--E corridor services over a time horizon.

    A recurring service slot keeps the same ``service_id`` across
    weekly cycles. Each occurrence contains four consecutive
    adjacent-terminal transport legs.

    An occurrence is included only when its complete A--E or E--A
    movement fits inside the configured horizon.
    """
    periods = _validate_time_periods(time_periods)

    if allowed_capacities_teu is None:
        capacity = _validate_capacity_teu(capacity_teu)
    else:
        capacity = _validate_capacity_teu_for(
            capacity_teu,
            allowed_capacities_teu=(allowed_capacities_teu),
            capacity_context=capacity_context,
        )

    spec = table4_service_family_spec(service_family)

    horizon_start = periods[0]
    horizon_end = periods[-1]

    complete_trip_duration = (len(TABLE4_TERMINALS) - 1) * spec.adjacent_travel_periods

    legs: list[ScheduledTransportLeg] = []

    cycle_start = horizon_start

    while cycle_start <= horizon_end:
        for slot_number, offset in enumerate(
            spec.departure_offsets,
            start=1,
        ):
            occurrence_departure = cycle_start + offset

            occurrence_arrival = occurrence_departure + complete_trip_duration

            if occurrence_arrival > horizon_end:
                continue

            for direction in (
                "eastbound",
                "westbound",
            ):
                service_id = _service_id(
                    spec,
                    direction=direction,
                    slot_number=slot_number,
                )

                for leg_index, (
                    origin,
                    destination,
                ) in enumerate(_direction_pairs(direction)):
                    departure_time = occurrence_departure + leg_index * spec.adjacent_travel_periods
                    arrival_time = departure_time + spec.adjacent_travel_periods

                    legs.append(
                        ScheduledTransportLeg(
                            service_id=service_id,
                            origin=origin,
                            destination=destination,
                            departure_time=departure_time,
                            arrival_time=arrival_time,
                            capacity=capacity,
                            direction=direction,
                        )
                    )

        cycle_start += spec.repeat_period

    if not legs:
        raise ValueError(
            f"The configured horizon contains no complete {service_family} service occurrence."
        )

    return tuple(
        sorted(
            legs,
            key=lambda leg: (
                leg.departure_time,
                leg.service_id,
                leg.origin,
                leg.destination,
            ),
        )
    )


def build_periodic_corridor_network_config(
    *,
    time_periods: tuple[int, ...],
    service_family: str,
    capacity_teu: int,
    allowed_capacities_teu: tuple[int, ...],
    capacity_context: str,
    add_holding_arcs: bool = True,
) -> NetworkConfig:
    """Build a corridor network under an explicit capacity domain."""
    if not isinstance(add_holding_arcs, bool):
        raise TypeError("add_holding_arcs must be a boolean.")

    periods = _validate_time_periods(time_periods)

    legs = build_periodic_corridor_transport_legs(
        time_periods=periods,
        service_family=service_family,
        capacity_teu=capacity_teu,
        allowed_capacities_teu=(allowed_capacities_teu),
        capacity_context=capacity_context,
    )

    return NetworkConfig(
        terminals=TABLE4_TERMINALS,
        time_periods=periods,
        transport_legs=legs,
        add_holding_arcs=add_holding_arcs,
    )


def build_table4_network_config(
    *,
    time_periods: tuple[int, ...],
    service_family: str,
    capacity_teu: int,
    add_holding_arcs: bool = True,
) -> NetworkConfig:
    """Build one publication-facing Table 4 network config."""
    return build_periodic_corridor_network_config(
        time_periods=time_periods,
        service_family=service_family,
        capacity_teu=capacity_teu,
        allowed_capacities_teu=(TABLE4_CAPACITIES_TEU),
        capacity_context="Table 4",
        add_holding_arcs=add_holding_arcs,
    )
