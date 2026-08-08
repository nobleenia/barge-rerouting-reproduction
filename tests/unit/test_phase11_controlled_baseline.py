"""Tests for the pre-registered Phase 11 controlled baseline."""

import pytest

from barge_rerouting.experiments import (
    TABLE4_CONTROLLED_HORIZON_END,
    TABLE4_CONTROLLED_PREMIUM_RATE,
    TABLE4_CONTROLLED_REQUEST_PERIODS,
    TABLE4_CONTROLLED_VMAX,
    TABLE4_CONTROLLED_VOLUME_PROBABILITIES,
    build_table4_controlled_demand_set,
    default_table4_controlled_demand_process,
    default_table4_controlled_economic_spec,
    default_table4_controlled_timing_pools,
    table4_economic_seed,
)


def test_controlled_volume_baseline_is_pre_registered() -> None:
    """VMAX and probability mass remain explicit constants."""
    assert TABLE4_CONTROLLED_VMAX == 2

    assert TABLE4_CONTROLLED_VOLUME_PROBABILITIES == (
        0.40,
        0.40,
        0.20,
    )

    spec = default_table4_controlled_economic_spec()

    assert spec.volume_distribution.maximum_volume == 2
    assert spec.volume_distribution.expected_volume == pytest.approx(0.8)


def test_controlled_fare_rates_are_fixed_before_solving() -> None:
    """Premium rates are explicit rather than tuned in model code."""
    spec = default_table4_controlled_economic_spec()

    assert TABLE4_CONTROLLED_PREMIUM_RATE == pytest.approx(1.25)

    assert spec.fare_rates.early_reservation_rate == pytest.approx(1.0)
    assert spec.fare_rates.standard_delivery_rate == pytest.approx(1.0)
    assert spec.fare_rates.late_reservation_rate == pytest.approx(1.25)
    assert spec.fare_rates.express_delivery_rate == pytest.approx(1.25)


def test_controlled_timing_pools_are_monotone_by_distance() -> None:
    """Timing pools preserve an explicit distance relationship."""
    pools = default_table4_controlled_timing_pools()

    assert len(pools) == 4

    for pool in pools:
        distance = pool.distance

        assert pool.anticipation_lags == (
            distance,
            distance + 1,
            distance + 2,
        )

        assert pool.delivery_slacks == (
            distance + 7,
            distance + 8,
            distance + 9,
        )


def test_pilot_has_140_opportunities_and_delivery_tail() -> None:
    """One arrival week contains 14 x 10 opportunities."""
    spec = default_table4_controlled_demand_process()

    assert TABLE4_CONTROLLED_REQUEST_PERIODS == tuple(range(14))
    assert TABLE4_CONTROLLED_HORIZON_END == 32
    assert spec.request_count == 140
    assert spec.horizon_end == 32


def test_economic_random_stream_is_separate() -> None:
    """Economic draws use a deterministic independent sub-stream."""
    assert table4_economic_seed(11001) == 1011001
    assert table4_economic_seed(11005) == 1011005


def test_controlled_demand_set_is_deterministic() -> None:
    """The same registered seed reproduces the exact demand set."""
    first = build_table4_controlled_demand_set(seed=11001)
    second = build_table4_controlled_demand_set(seed=11001)

    assert first == second
    assert first.structural_fingerprint == second.structural_fingerprint
    assert first.demand_fingerprint == second.demand_fingerprint


def test_zero_and_positive_volume_counts_reconcile() -> None:
    """Zero-volume opportunities remain explicitly accounted for."""
    demand_set = build_table4_controlled_demand_set(seed=11002)

    assert demand_set.opportunity_count == 140

    assert demand_set.zero_volume_count + demand_set.positive_demand_count == 140

    assert demand_set.zero_volume_count > 0
    assert demand_set.positive_demand_count > 0


def test_positive_realised_demands_use_only_supported_volumes() -> None:
    """Only volumes 1 and 2 become optimisation requests."""
    demand_set = build_table4_controlled_demand_set(seed=11003)

    assert {float(demand.volume) for demand in demand_set.demands}.issubset({1.0, 2.0})


def test_distinct_registered_seeds_produce_distinct_instances() -> None:
    """Five demand sets are genuine independent controlled realisations."""
    first = build_table4_controlled_demand_set(seed=11004)
    second = build_table4_controlled_demand_set(seed=11005)

    assert first.structural_fingerprint != second.structural_fingerprint

    assert first.demand_fingerprint != second.demand_fingerprint
