"""Deterministic generation of time-feasible synthetic demands."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

import networkx as nx

from barge_rerouting.config import ExperimentConfig
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    TimeSpaceNode,
)
from barge_rerouting.network.time_space import build_time_space_network


@dataclass(frozen=True, slots=True)
class FeasibleDemandTemplate:
    """One feasible origin, destination, and time-window combination."""

    origin: str
    destination: str
    reservation_time: int
    availability_time: int
    due_time: int


def _validate_random_seed(random_seed: object) -> int:
    """Validate and return a nonnegative random seed."""
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise TypeError("random_seed must be an integer.")

    if random_seed < 0:
        raise ValueError("random_seed must be non-negative.")

    return random_seed


def _can_reach_destination_by_due(
    graph: nx.MultiDiGraph,
    *,
    source: TimeSpaceNode,
    destination: str,
    availability_time: int,
    due_time: int,
    time_periods: tuple[int, ...],
) -> bool:
    """Return whether the destination can be reached by the deadline."""
    if source not in graph:
        return False

    for destination_time in time_periods:
        if destination_time < availability_time:
            continue

        if destination_time > due_time:
            break

        destination_node: TimeSpaceNode = (
            destination,
            destination_time,
        )

        if destination_node not in graph:
            continue

        if nx.has_path(graph, source, destination_node):
            return True

    return False


def enumerate_feasible_demand_templates(
    config: ExperimentConfig,
) -> tuple[FeasibleDemandTemplate, ...]:
    """Enumerate all feasible demand timing and OD combinations.

    A candidate is retained only when cargo available at the specified source
    node can reach the destination at or before the candidate due time.
    """
    graph = build_time_space_network(
        terminals=config.network.terminals,
        time_periods=config.network.time_periods,
        transport_legs=config.network.transport_legs,
        add_holding_arcs=config.network.add_holding_arcs,
    )

    generation = config.demand_generation
    time_periods = config.network.time_periods
    time_period_set = set(time_periods)

    templates: list[FeasibleDemandTemplate] = []

    for reservation_time in range(
        generation.minimum_reservation_time,
        generation.maximum_reservation_time + 1,
    ):
        for availability_lag in range(
            generation.minimum_availability_lag,
            generation.maximum_availability_lag + 1,
        ):
            availability_time = reservation_time + availability_lag

            if availability_time not in time_period_set:
                continue

            for due_slack in range(
                generation.minimum_due_slack,
                generation.maximum_due_slack + 1,
            ):
                due_time = availability_time + due_slack

                if due_time > config.network.horizon_end:
                    continue

                for origin in config.network.terminals:
                    source: TimeSpaceNode = (
                        origin,
                        availability_time,
                    )

                    for destination in config.network.terminals:
                        if destination == origin:
                            continue

                        if not _can_reach_destination_by_due(
                            graph,
                            source=source,
                            destination=destination,
                            availability_time=availability_time,
                            due_time=due_time,
                            time_periods=time_periods,
                        ):
                            continue

                        templates.append(
                            FeasibleDemandTemplate(
                                origin=origin,
                                destination=destination,
                                reservation_time=reservation_time,
                                availability_time=availability_time,
                                due_time=due_time,
                            )
                        )

    return tuple(templates)


def _sample_customer_category(
    random_generator: Random,
    config: ExperimentConfig,
) -> CustomerCategory:
    """Sample one category using the configured category probabilities."""
    mix = config.demand_generation.customer_mix
    random_value = random_generator.random()

    regular_boundary = mix.regular_probability
    partially_spot_boundary = regular_boundary + mix.partially_spot_probability

    if random_value < regular_boundary:
        return CustomerCategory.REGULAR

    if random_value < partially_spot_boundary:
        return CustomerCategory.PARTIALLY_SPOT

    return CustomerCategory.FULLY_SPOT


def generate_demands(
    config: ExperimentConfig,
    *,
    random_seed: int | None = None,
) -> tuple[Demand, ...]:
    """Generate a deterministic collection of feasible demands.

    Args:
        config:
            Complete validated experiment configuration.
        random_seed:
            Optional override used for controlled replications. When omitted,
            the seed stored in the experiment configuration is used.

    Returns:
        Generated demands in deterministic identifier order.

    Raises:
        ValueError:
            If the network and generation ranges produce no feasible template.
    """
    selected_seed = (
        config.random_seed if random_seed is None else _validate_random_seed(random_seed)
    )

    random_generator = Random(selected_seed)
    templates = enumerate_feasible_demand_templates(config)

    if not templates:
        raise ValueError(
            "No feasible demand templates can be generated from the "
            "configured network and time ranges."
        )

    generation = config.demand_generation
    demands: list[Demand] = []

    for demand_number in range(
        1,
        generation.number_of_demands + 1,
    ):
        template_index = random_generator.randrange(len(templates))
        template = templates[template_index]

        volume = random_generator.randint(
            generation.minimum_volume,
            generation.maximum_volume,
        )

        fare_per_teu = round(
            random_generator.uniform(
                generation.minimum_fare_per_teu,
                generation.maximum_fare_per_teu,
            ),
            2,
        )

        category = _sample_customer_category(
            random_generator,
            config,
        )

        demands.append(
            Demand(
                demand_id=f"K{demand_number:04d}",
                volume=volume,
                origin=template.origin,
                destination=template.destination,
                reservation_time=template.reservation_time,
                availability_time=template.availability_time,
                due_time=template.due_time,
                category=category,
                fare_per_teu=fare_per_teu,
            )
        )

    return tuple(demands)
