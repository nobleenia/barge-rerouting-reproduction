"""Tests for water-adjusted transport capacities."""

from barge_rerouting.config import (
    CustomerMix,
    DemandGenerationConfig,
    ExperimentConfig,
    NetworkConfig,
    SolverConfig,
)
from barge_rerouting.disruption import (
    ActualCapacityProfile,
    ServiceStatusUpdateEvent,
    build_actual_capacity_profile,
)
from barge_rerouting.domain import (
    CustomerCategory,
    Demand,
    ScheduledTransportLeg,
)
from barge_rerouting.instance import (
    assemble_experiment_instance,
)


def build_instance():
    """Build a small scheduled corridor."""
    config = ExperimentConfig(
        experiment_name="phase10-capacity-test",
        random_seed=10,
        network=NetworkConfig(
            terminals=("A", "B", "C"),
            time_periods=(0, 1, 2, 3, 4),
            transport_legs=(
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="A",
                    destination="B",
                    departure_time=1,
                    arrival_time=2,
                    capacity=10,
                ),
                ScheduledTransportLeg(
                    service_id="S1",
                    origin="B",
                    destination="C",
                    departure_time=2,
                    arrival_time=3,
                    capacity=10,
                ),
                ScheduledTransportLeg(
                    service_id="S2",
                    origin="A",
                    destination="C",
                    departure_time=3,
                    arrival_time=4,
                    capacity=20,
                ),
            ),
        ),
        demand_generation=DemandGenerationConfig(
            number_of_demands=1,
            minimum_volume=1,
            maximum_volume=1,
            minimum_fare_per_teu=10,
            maximum_fare_per_teu=10,
            minimum_reservation_time=0,
            maximum_reservation_time=0,
            minimum_availability_lag=0,
            maximum_availability_lag=0,
            minimum_due_slack=4,
            maximum_due_slack=4,
            customer_mix=CustomerMix(
                regular_probability=1.0,
                partially_spot_probability=0.0,
                fully_spot_probability=0.0,
            ),
        ),
        solver=SolverConfig(
            time_limit_seconds=30,
            relative_mip_gap=0.0,
            log_output=False,
        ),
    )

    return assemble_experiment_instance(
        config,
        demands=(
            Demand(
                "K1",
                1,
                "A",
                "C",
                0,
                0,
                4,
                CustomerCategory.REGULAR,
                10,
            ),
        ),
    )


def transport_arc(
    instance,
    *,
    service_id: str,
    departure_time: int,
):
    """Return one uniquely identified transport arc."""
    matches = tuple(
        arc
        for arc in instance.arcs
        if (arc.is_transport and arc.service_id == service_id and arc.tail[1] == departure_time)
    )

    assert len(matches) == 1
    return matches[0]


def test_no_updates_preserve_nominal_capacity() -> None:
    """An empty update set must reproduce stable capacity."""
    instance = build_instance()

    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
    )

    assert isinstance(profile, ActualCapacityProfile)
    assert profile.affected_arc_ids == ()

    for state in profile.arc_states:
        assert state.actual_capacity == (state.nominal_capacity)
        assert state.water_level_factor == 1.0
        assert state.source_update_event_id is None


def test_update_applies_by_service_and_validity_window() -> None:
    """Only matching departures in the half-open window change."""
    instance = build_instance()
    update = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=3,
        water_level_factor=0.8,
        affected_service_ids=("S1",),
    )

    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
        status_updates=(update,),
    )

    first = transport_arc(
        instance,
        service_id="S1",
        departure_time=1,
    )
    second = transport_arc(
        instance,
        service_id="S1",
        departure_time=2,
    )
    outside = transport_arc(
        instance,
        service_id="S2",
        departure_time=3,
    )

    assert profile.actual_capacity_for(first.arc_id) == 8
    assert profile.actual_capacity_for(second.arc_id) == 8
    assert profile.actual_capacity_for(outside.arc_id) == 20


def test_past_departure_is_not_retroactively_changed() -> None:
    """A departed leg retains historical nominal accounting."""
    instance = build_instance()
    update = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=4,
        water_level_factor=0.7,
        affected_service_ids=("S1",),
    )

    profile = build_actual_capacity_profile(
        instance,
        physical_time=2,
        status_updates=(update,),
    )

    departed = transport_arc(
        instance,
        service_id="S1",
        departure_time=1,
    )
    same_time = transport_arc(
        instance,
        service_id="S1",
        departure_time=2,
    )

    assert profile.actual_capacity_for(departed.arc_id) == 10
    assert profile.actual_capacity_for(same_time.arc_id) == 7


def test_latest_known_update_wins() -> None:
    """A later applicable forecast supersedes an earlier one."""
    instance = build_instance()

    profile = build_actual_capacity_profile(
        instance,
        physical_time=1,
        status_updates=(
            ServiceStatusUpdateEvent(
                sequence_number=1,
                update_time=0,
                valid_from=0,
                valid_until=4,
                water_level_factor=0.9,
                affected_service_ids=("S1",),
            ),
            ServiceStatusUpdateEvent(
                sequence_number=2,
                update_time=1,
                valid_from=1,
                valid_until=4,
                water_level_factor=0.7,
                affected_service_ids=("S1",),
            ),
        ),
    )

    arc = transport_arc(
        instance,
        service_id="S1",
        departure_time=2,
    )
    state = profile.state_for(arc.arc_id)

    assert state.actual_capacity == 7
    assert state.water_level_factor == 0.7
    assert state.source_update_event_id == ("status::0002::0001")


def test_empty_service_set_updates_every_service() -> None:
    """An unscoped status update applies globally."""
    instance = build_instance()
    update = ServiceStatusUpdateEvent(
        sequence_number=1,
        update_time=0,
        valid_from=0,
        valid_until=5,
        water_level_factor=0.9,
    )

    profile = build_actual_capacity_profile(
        instance,
        physical_time=0,
        status_updates=(update,),
    )

    assert len(profile.affected_arc_ids) == 3

    s2 = transport_arc(
        instance,
        service_id="S2",
        departure_time=3,
    )

    assert profile.actual_capacity_for(s2.arc_id) == 18


def test_invalid_water_level_factor_is_rejected() -> None:
    """Paper-aligned capacity factors must be in (0, 1]."""
    import pytest

    with pytest.raises(
        ValueError,
        match=r"in \(0, 1\]",
    ):
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=0,
            valid_from=0,
            valid_until=4,
            water_level_factor=1.1,
        )

    with pytest.raises(
        ValueError,
        match=r"in \(0, 1\]",
    ):
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=0,
            valid_from=0,
            valid_until=4,
            water_level_factor=0.0,
        )


def test_invalid_status_validity_is_rejected() -> None:
    """Forecast validity cannot precede its publication."""
    import pytest

    with pytest.raises(
        ValueError,
        match="must not precede",
    ):
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=2,
            valid_from=1,
            valid_until=4,
            water_level_factor=0.8,
        )

    with pytest.raises(
        ValueError,
        match="strictly greater",
    ):
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=2,
            valid_from=2,
            valid_until=2,
            water_level_factor=0.8,
        )


def test_duplicate_update_sequences_are_rejected() -> None:
    """Status-event identity must remain unique."""
    import pytest

    instance = build_instance()

    updates = (
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=0,
            valid_from=0,
            valid_until=3,
            water_level_factor=0.9,
        ),
        ServiceStatusUpdateEvent(
            sequence_number=1,
            update_time=1,
            valid_from=1,
            valid_until=4,
            water_level_factor=0.8,
        ),
    )

    with pytest.raises(
        ValueError,
        match="sequence numbers must be unique",
    ):
        build_actual_capacity_profile(
            instance,
            physical_time=1,
            status_updates=updates,
        )
