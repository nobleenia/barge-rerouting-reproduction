"""Tests for Phase 11 economic/stochastic input structure."""

from dataclasses import replace

import pytest

from barge_rerouting.domain import VolumeProbability
from barge_rerouting.experiments import (
    DiscreteVolumeDistribution,
    DistanceEconomicInput,
    FareClassRates,
    Table4EconomicInputSpec,
    table4_economic_input_fingerprint,
)


def _distribution() -> DiscreteVolumeDistribution:
    """Build one controlled test probability mass."""
    return DiscreteVolumeDistribution(
        outcomes=(
            VolumeProbability(0, 0.20),
            VolumeProbability(1, 0.30),
            VolumeProbability(2, 0.50),
        )
    )


def _rates() -> FareClassRates:
    """Build controlled premium rates."""
    return FareClassRates(
        early_reservation_rate=1.0,
        late_reservation_rate=2.0,
        standard_delivery_rate=1.0,
        express_delivery_rate=3.0,
    )


def _distance_inputs() -> tuple[
    DistanceEconomicInput,
    ...,
]:
    """Build complete controlled distance inputs."""
    return tuple(
        DistanceEconomicInput(
            distance=distance,
            base_fare_per_teu=10.0 * distance,
            anticipation_threshold=distance,
            delivery_threshold=distance + 1,
        )
        for distance in (1, 2, 3, 4)
    )


def _spec() -> Table4EconomicInputSpec:
    """Build one complete controlled economic specification."""
    return Table4EconomicInputSpec(
        volume_distribution=_distribution(),
        fare_rates=_rates(),
        distance_inputs=_distance_inputs(),
    )


def test_volume_distribution_preserves_zero_to_vmax_support() -> None:
    """The published support is exactly 0 through VMAX."""
    distribution = _distribution()

    assert distribution.support == (0, 1, 2)
    assert distribution.maximum_volume == 2
    assert distribution.zero_probability == pytest.approx(0.20)
    assert distribution.expected_volume == pytest.approx(1.30)


def test_volume_distribution_rejects_missing_support_value() -> None:
    """Protection levels require contiguous 0..VMAX support."""
    with pytest.raises(
        ValueError,
        match="contiguous",
    ):
        DiscreteVolumeDistribution(
            outcomes=(
                VolumeProbability(0, 0.50),
                VolumeProbability(2, 0.50),
            )
        )


def test_fare_rates_enforce_published_reference_classes() -> None:
    """Early reservation and standard delivery must equal one."""
    with pytest.raises(
        ValueError,
        match="early-reservation",
    ):
        FareClassRates(
            early_reservation_rate=1.1,
            late_reservation_rate=2.0,
            standard_delivery_rate=1.0,
            express_delivery_rate=3.0,
        )

    with pytest.raises(
        ValueError,
        match="standard-delivery",
    ):
        FareClassRates(
            early_reservation_rate=1.0,
            late_reservation_rate=2.0,
            standard_delivery_rate=1.1,
            express_delivery_rate=3.0,
        )


def test_premium_fare_rates_must_exceed_one() -> None:
    """Late and express classes are high-contribution classes."""
    with pytest.raises(
        ValueError,
        match="late-reservation",
    ):
        FareClassRates(
            early_reservation_rate=1.0,
            late_reservation_rate=1.0,
            standard_delivery_rate=1.0,
            express_delivery_rate=3.0,
        )

    with pytest.raises(
        ValueError,
        match="express-delivery",
    ):
        FareClassRates(
            early_reservation_rate=1.0,
            late_reservation_rate=2.0,
            standard_delivery_rate=1.0,
            express_delivery_rate=1.0,
        )


def test_complete_spec_requires_all_four_corridor_distances() -> None:
    """Economic inputs cannot silently omit an OD distance."""
    with pytest.raises(
        ValueError,
        match="distances 1, 2, 3 and 4",
    ):
        Table4EconomicInputSpec(
            volume_distribution=_distribution(),
            fare_rates=_rates(),
            distance_inputs=_distance_inputs()[:3],
        )


def test_fare_equation_matches_multiplicative_paper_structure() -> None:
    """f = p * anticipation-rate * delivery-rate."""
    spec = _spec()

    assert spec.fare_per_teu_for_classes(
        distance=2,
        early_reservation=True,
        standard_delivery=True,
    ) == pytest.approx(20.0)

    assert spec.fare_per_teu_for_classes(
        distance=2,
        early_reservation=False,
        standard_delivery=True,
    ) == pytest.approx(40.0)

    assert spec.fare_per_teu_for_classes(
        distance=2,
        early_reservation=True,
        standard_delivery=False,
    ) == pytest.approx(60.0)

    assert spec.fare_per_teu_for_classes(
        distance=2,
        early_reservation=False,
        standard_delivery=False,
    ) == pytest.approx(120.0)


def test_economic_input_fingerprint_is_deterministic_and_sensitive() -> None:
    """Every numerical economic assumption enters traceability."""
    spec = _spec()

    first = table4_economic_input_fingerprint(spec)
    second = table4_economic_input_fingerprint(spec)

    changed_rates = replace(
        spec.fare_rates,
        late_reservation_rate=2.5,
    )
    changed = replace(
        spec,
        fare_rates=changed_rates,
    )

    third = table4_economic_input_fingerprint(changed)

    assert len(first) == 64
    assert first == second
    assert third != first
