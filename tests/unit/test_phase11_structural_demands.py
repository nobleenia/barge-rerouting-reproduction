"""Tests for the Phase 11 structural demand process."""

from collections import Counter

import pytest

from barge_rerouting.experiments import (
    TABLE4_CUSTOMER_CATEGORIES,
    TABLE4_ORDERED_OD_PAIRS,
    DistanceTimingPool,
    Table4DemandProcessSpec,
    corridor_distance,
    generate_table4_request_templates,
    request_template_fingerprint,
)


def _timing_pools() -> tuple[DistanceTimingPool, ...]:
    """Controlled test-only timing pools."""
    return (
        DistanceTimingPool(
            distance=1,
            anticipation_lags=(0, 1),
            delivery_slacks=(2, 3),
        ),
        DistanceTimingPool(
            distance=2,
            anticipation_lags=(0, 1),
            delivery_slacks=(3, 4),
        ),
        DistanceTimingPool(
            distance=3,
            anticipation_lags=(0, 1),
            delivery_slacks=(4, 5),
        ),
        DistanceTimingPool(
            distance=4,
            anticipation_lags=(0, 1),
            delivery_slacks=(5, 6),
        ),
    )


def _spec() -> Table4DemandProcessSpec:
    """Build a small controlled structural specification."""
    return Table4DemandProcessSpec(
        request_periods=(0, 1, 2),
        horizon_end=9,
        timing_pools=_timing_pools(),
    )


def test_corridor_contains_twenty_ordered_od_pairs() -> None:
    """Five terminals produce 5 x 4 ordered OD pairs."""
    assert len(TABLE4_ORDERED_OD_PAIRS) == 20
    assert len(set(TABLE4_ORDERED_OD_PAIRS)) == 20

    assert ("A", "E") in TABLE4_ORDERED_OD_PAIRS
    assert ("E", "A") in TABLE4_ORDERED_OD_PAIRS
    assert ("A", "A") not in TABLE4_ORDERED_OD_PAIRS


def test_corridor_distance_is_number_of_adjacent_legs() -> None:
    """OD distance follows the five-terminal corridor."""
    assert corridor_distance("A", "B") == 1
    assert corridor_distance("A", "C") == 2
    assert corridor_distance("A", "D") == 3
    assert corridor_distance("A", "E") == 4
    assert corridor_distance("E", "A") == 4


def test_process_generates_ten_requests_per_half_day() -> None:
    """Published demand density is preserved exactly."""
    templates = generate_table4_request_templates(
        _spec(),
        seed=11001,
    )

    assert len(templates) == 30

    counts = Counter(template.reservation_time for template in templates)

    assert counts == {
        0: 10,
        1: 10,
        2: 10,
    }


def test_structural_generation_is_deterministic() -> None:
    """The same controlled seed gives the identical request stream."""
    first = generate_table4_request_templates(
        _spec(),
        seed=11001,
    )
    second = generate_table4_request_templates(
        _spec(),
        seed=11001,
    )
    third = generate_table4_request_templates(
        _spec(),
        seed=11002,
    )

    assert first == second
    assert request_template_fingerprint(first) == request_template_fingerprint(second)

    assert request_template_fingerprint(third) != request_template_fingerprint(first)


def test_categories_are_drawn_only_from_uniform_category_domain() -> None:
    """Every realised category belongs to R/P/F."""
    templates = generate_table4_request_templates(
        _spec(),
        seed=11003,
    )

    assert {template.category for template in templates}.issubset(set(TABLE4_CUSTOMER_CATEGORIES))

    assert len(TABLE4_CUSTOMER_CATEGORIES) == 3


def test_timing_draw_uses_the_od_distance_pool() -> None:
    """Every anticipation/deadline draw belongs to its distance pool."""
    spec = _spec()

    templates = generate_table4_request_templates(
        spec,
        seed=11004,
    )

    for template in templates:
        pool = spec.timing_pool_for(template.distance)

        assert template.anticipation_lag in pool.anticipation_lags
        assert template.delivery_slack in pool.delivery_slacks

        assert template.availability_time == template.reservation_time + template.anticipation_lag

        assert template.due_time == template.availability_time + template.delivery_slack


def test_request_identifiers_and_sequence_are_stable() -> None:
    """Structural rows retain deterministic booking order."""
    templates = generate_table4_request_templates(
        _spec(),
        seed=11005,
    )

    assert tuple(template.sequence_number for template in templates) == tuple(range(1, 31))

    assert templates[0].demand_id == "K0001"
    assert templates[-1].demand_id == "K0030"


def test_spec_rejects_horizon_that_would_bias_late_draws() -> None:
    """The generator never silently truncates timing pools."""
    with pytest.raises(
        ValueError,
        match="extend beyond horizon_end",
    ):
        Table4DemandProcessSpec(
            request_periods=(0, 1, 2),
            horizon_end=7,
            timing_pools=_timing_pools(),
        )
