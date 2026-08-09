"""Tests for the Phase 11 Table 5 controlled demand set."""

from collections import Counter

import pytest

from barge_rerouting.experiments.phase11_table5 import (
    TABLE5_DEMAND_COUNT,
    TABLE5_REQUESTS_PER_PERIOD,
)
from barge_rerouting.experiments.phase11_table5_demands import (
    TABLE5_CONTROLLED_SEED,
    TABLE5_POSITIVE_VOLUME_PROBABILITIES,
    TABLE5_VOLUME_CONDITIONING,
    build_table5_controlled_demand_set,
    default_table5_controlled_economic_spec,
    table5_economic_input_fingerprint,
)


def test_table5_positive_conditioning_is_a040() -> None:
    spec = default_table5_controlled_economic_spec()

    assert TABLE5_VOLUME_CONDITIONING == ("positive_volume_q_gt_0")

    assert TABLE5_POSITIVE_VOLUME_PROBABILITIES == (
        (1, 2.0 / 3.0),
        (2, 1.0 / 3.0),
    )

    # The underlying validated A032 distribution remains unchanged.
    outcomes = tuple(
        (
            outcome.volume,
            outcome.probability,
        )
        for outcome in spec.volume_distribution.outcomes
    )

    assert tuple(volume for volume, _ in outcomes) == (
        0,
        1,
        2,
    )

    assert tuple(probability for _, probability in outcomes) == pytest.approx(
        (
            0.40,
            0.40,
            0.20,
        )
    )

    # A040 is the same source distribution conditioned on Q > 0.
    expected_positive_volume = 1.0 * (2.0 / 3.0) + 2.0 * (1.0 / 3.0)

    assert expected_positive_volume == pytest.approx(4.0 / 3.0)


def test_table5_economic_fingerprint_includes_conditioning() -> None:
    spec = default_table5_controlled_economic_spec()

    first = table5_economic_input_fingerprint(spec)
    second = table5_economic_input_fingerprint(spec)

    assert first == second
    assert len(first) == 64


def test_table5_demand_set_contains_exactly_800_positive_requests() -> None:
    demand_set = build_table5_controlled_demand_set()

    assert demand_set.seed == (TABLE5_CONTROLLED_SEED)

    assert demand_set.request_count == (TABLE5_DEMAND_COUNT)

    assert len(demand_set.templates) == 800
    assert len(demand_set.demands) == 800

    assert all(demand.volume in (1.0, 2.0) for demand in demand_set.demands)


def test_table5_has_exactly_ten_bookings_per_request_period() -> None:
    demand_set = build_table5_controlled_demand_set()

    counts = Counter(demand.reservation_time for demand in demand_set.demands)

    assert tuple(sorted(counts)) == tuple(range(80))

    assert all(counts[period] == TABLE5_REQUESTS_PER_PERIOD for period in range(80))


def test_table5_controlled_demand_set_is_deterministic() -> None:
    first = build_table5_controlled_demand_set()

    second = build_table5_controlled_demand_set()

    assert first == second

    assert first.structural_fingerprint == second.structural_fingerprint

    assert first.economic_fingerprint == second.economic_fingerprint

    assert first.demand_fingerprint == second.demand_fingerprint


def test_table5_different_seed_changes_realised_instance() -> None:
    first = build_table5_controlled_demand_set(
        seed=TABLE5_CONTROLLED_SEED,
    )

    second = build_table5_controlled_demand_set(
        seed=TABLE5_CONTROLLED_SEED + 1,
    )

    assert first.structural_fingerprint != second.structural_fingerprint

    assert first.demand_fingerprint != second.demand_fingerprint


def test_frozen_table5_instance_matches_registered_fingerprints() -> None:
    from barge_rerouting.experiments.phase11_table5_demands import (
        TABLE5_EXPECTED_DEMAND_FINGERPRINT,
        TABLE5_EXPECTED_ECONOMIC_FINGERPRINT,
        TABLE5_EXPECTED_STRUCTURAL_FINGERPRINT,
        TABLE5_EXPECTED_TOTAL_REQUESTED_TEU,
        build_frozen_table5_controlled_demand_set,
    )

    demand_set = build_frozen_table5_controlled_demand_set()

    assert demand_set.structural_fingerprint == TABLE5_EXPECTED_STRUCTURAL_FINGERPRINT

    assert demand_set.economic_fingerprint == TABLE5_EXPECTED_ECONOMIC_FINGERPRINT

    assert demand_set.demand_fingerprint == TABLE5_EXPECTED_DEMAND_FINGERPRINT

    assert sum(demand.volume for demand in demand_set.demands) == pytest.approx(
        TABLE5_EXPECTED_TOTAL_REQUESTED_TEU
    )


def test_frozen_table5_diagnostic_distribution_is_stable() -> None:
    from barge_rerouting.experiments.phase11_table5_demands import (
        build_frozen_table5_controlled_demand_set,
    )

    demand_set = build_frozen_table5_controlled_demand_set()

    volume_counts = Counter(int(demand.volume) for demand in demand_set.demands)

    category_counts = Counter(demand.category.value for demand in demand_set.demands)

    assert volume_counts == {
        1: 524,
        2: 276,
    }

    assert category_counts == {
        "F": 273,
        "P": 254,
        "R": 273,
    }
