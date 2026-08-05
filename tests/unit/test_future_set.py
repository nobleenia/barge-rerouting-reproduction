"""Tests for construction of K(current)."""

from pathlib import Path

import pytest

from barge_rerouting.config import (
    load_experiment_config,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    FutureDemandForecast,
    VolumeProbability,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)
from barge_rerouting.revenue_management import (
    FutureDemandExclusionReason,
    FutureDemandSelectionMode,
    select_a004_interacting_future_set,
    select_explicit_future_set,
)
from barge_rerouting.rolling_horizon import (
    build_booking_timeline,
)


def build_current_example():
    """Build a current demand using prefix and bottleneck services."""
    config = load_experiment_config(Path("tests/fixtures/rerouting_switch_experiment.yaml"))

    current = Demand(
        demand_id="CURRENT",
        volume=4,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=0,
        due_time=2,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=10,
    )

    instance = assemble_experiment_instance(
        config,
        demands=(current,),
    )
    event = build_booking_timeline(instance).event_at_sequence(1)

    return instance, event


def forecast(
    forecast_id: str,
    origin: str,
    destination: str,
    availability_time: int,
    due_time: int,
    *,
    maximum_volume: int = 4,
) -> FutureDemandForecast:
    """Build one controlled future forecast."""
    if maximum_volume == 0:
        outcomes = (VolumeProbability(0, 1.0),)
    else:
        outcomes = (
            VolumeProbability(0, 0.5),
            VolumeProbability(maximum_volume, 0.5),
        )

    return FutureDemandForecast(
        forecast_id=forecast_id,
        origin=origin,
        destination=destination,
        availability_time=availability_time,
        due_time=due_time,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=100,
        outcomes=outcomes,
    )


def test_explicit_set_keeps_supplied_feasible_forecasts() -> None:
    """Explicit mode must not infer shared-arc membership."""
    instance, event = build_current_example()

    shared = forecast(
        "SHARED",
        "B",
        "C",
        1,
        2,
    )
    alternative = forecast(
        "ALTERNATIVE",
        "B",
        "D",
        1,
        2,
    )

    future_set = select_explicit_future_set(
        instance,
        event,
        (shared, alternative),
    )

    assert future_set.selection_mode is (FutureDemandSelectionMode.EXPLICIT)
    assert future_set.forecast_ids == (
        "ALTERNATIVE",
        "SHARED",
    )
    assert future_set.exclusions == ()


def test_explicit_candidate_contains_solver_ready_network() -> None:
    """Projected forecasts must have flow and sink indexes."""
    instance, event = build_current_example()

    future_set = select_explicit_future_set(
        instance,
        event,
        (
            forecast(
                "SHARED",
                "B",
                "C",
                1,
                2,
            ),
        ),
    )

    candidate = future_set.candidate_for("SHARED")
    network = candidate.network_index

    assert network.source == ("B", 1)
    assert network.destination_nodes == (("C", 2),)
    assert network.demand.volume == pytest.approx(4.0)
    assert len(network.sink_arc_ids) == 1
    assert network.sink_arc_ids[0].startswith("delivery::SHARED::")


def test_shared_arc_interaction_is_indexed() -> None:
    """The shared forecast must compete on S_BOTTLENECK."""
    instance, event = build_current_example()

    future_set = select_explicit_future_set(
        instance,
        event,
        (
            forecast(
                "SHARED",
                "B",
                "C",
                1,
                2,
            ),
        ),
    )

    candidate = future_set.candidate_for("SHARED")

    assert candidate.shared_transport_arc_ids == ("transport::1::S_BOTTLENECK",)


def test_a004_selector_keeps_only_interacting_forecast() -> None:
    """Automatic mode must retain only later shared-capacity demand."""
    instance, event = build_current_example()

    future_set = select_a004_interacting_future_set(
        instance,
        event,
        (
            forecast(
                "SHARED",
                "B",
                "C",
                1,
                2,
            ),
            forecast(
                "ALTERNATIVE",
                "B",
                "D",
                1,
                2,
            ),
        ),
    )

    assert future_set.selection_mode is (FutureDemandSelectionMode.A004_SHARED_ARC)
    assert future_set.forecast_ids == ("SHARED",)

    exclusion = future_set.exclusion_for("ALTERNATIVE")
    assert exclusion.reason is (FutureDemandExclusionReason.NO_SHARED_TRANSPORT_ARC)


def test_same_time_forecast_is_not_inferred_as_future() -> None:
    """Availability must be later under the A004 proxy rule."""
    instance, event = build_current_example()

    future_set = select_a004_interacting_future_set(
        instance,
        event,
        (
            forecast(
                "SAME_TIME",
                "A",
                "C",
                0,
                2,
            ),
        ),
    )

    assert future_set.forecast_ids == ()
    assert future_set.exclusion_for("SAME_TIME").reason is (
        FutureDemandExclusionReason.NOT_LATER_THAN_CURRENT_EVENT
    )


def test_infeasible_forecast_is_excluded() -> None:
    """A forecast with no route by its deadline cannot enter K."""
    instance, event = build_current_example()

    future_set = select_a004_interacting_future_set(
        instance,
        event,
        (
            forecast(
                "INFEASIBLE",
                "A",
                "D",
                1,
                1,
            ),
        ),
    )

    assert future_set.forecast_ids == ()
    assert future_set.exclusion_for("INFEASIBLE").reason is (
        FutureDemandExclusionReason.NETWORK_INFEASIBLE
    )


def test_zero_volume_forecast_is_excluded() -> None:
    """A degenerate zero forecast has no selector level."""
    instance, event = build_current_example()

    future_set = select_a004_interacting_future_set(
        instance,
        event,
        (
            forecast(
                "ZERO",
                "B",
                "C",
                1,
                2,
                maximum_volume=0,
            ),
        ),
    )

    assert future_set.forecast_ids == ()
    assert future_set.exclusion_for("ZERO").reason is (
        FutureDemandExclusionReason.ZERO_MAXIMUM_VOLUME
    )


def test_lookahead_horizon_excludes_later_forecasts() -> None:
    """The optional horizon must constrain inferred candidates."""
    instance, event = build_current_example()

    future_set = select_a004_interacting_future_set(
        instance,
        event,
        (
            forecast(
                "SHARED",
                "B",
                "C",
                1,
                2,
            ),
        ),
        lookahead_end_time=0,
    )

    assert future_set.forecast_ids == ()
    assert future_set.exclusion_for("SHARED").reason is (
        FutureDemandExclusionReason.OUTSIDE_LOOKAHEAD
    )


def test_invalid_lookahead_is_rejected() -> None:
    """A look-ahead horizon cannot precede the event."""
    instance, event = build_current_example()

    with pytest.raises(
        ValueError,
        match="cannot precede",
    ):
        select_a004_interacting_future_set(
            instance,
            event,
            (),
            lookahead_end_time=-1,
        )


def test_duplicate_forecast_ids_are_rejected() -> None:
    """Forecast identifiers must be unique within one decision."""
    instance, event = build_current_example()
    duplicate = forecast(
        "DUPLICATE",
        "B",
        "C",
        1,
        2,
    )

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        select_explicit_future_set(
            instance,
            event,
            (duplicate, duplicate),
        )


def test_future_set_is_deterministic() -> None:
    """Input ordering must not change selected candidates."""
    instance, event = build_current_example()

    shared = forecast(
        "SHARED",
        "B",
        "C",
        1,
        2,
    )
    alternative = forecast(
        "ALTERNATIVE",
        "B",
        "D",
        1,
        2,
    )

    first = select_explicit_future_set(
        instance,
        event,
        (shared, alternative),
    )
    second = select_explicit_future_set(
        instance,
        event,
        (alternative, shared),
    )

    assert first == second
