"""Tests for transportation demand domain objects."""

from typing import cast

import pytest

from barge_rerouting.domain import (
    AcceptanceVariableType,
    CustomerCategory,
    Demand,
)


def make_demand(
    *,
    category: CustomerCategory = CustomerCategory.PARTIALLY_SPOT,
) -> Demand:
    """Return a valid demand for use in tests."""
    return Demand(
        demand_id="K001",
        volume=12.0,
        origin="A",
        destination="C",
        reservation_time=0,
        availability_time=1,
        due_time=4,
        category=category,
        fare_per_teu=25.0,
    )


def test_customer_categories_map_to_correct_variable_types() -> None:
    """Each category must map to its mathematical acceptance domain."""
    assert CustomerCategory.REGULAR.acceptance_variable_type is AcceptanceVariableType.FIXED
    assert (
        CustomerCategory.PARTIALLY_SPOT.acceptance_variable_type
        is AcceptanceVariableType.CONTINUOUS
    )
    assert CustomerCategory.FULLY_SPOT.acceptance_variable_type is AcceptanceVariableType.BINARY


def test_valid_demand_is_normalised_and_has_expected_revenue() -> None:
    """Demand identifiers and terminals are stripped and revenue is computed."""
    demand = Demand(
        demand_id="  K001  ",
        volume=12,
        origin="  A ",
        destination=" C  ",
        reservation_time=0,
        availability_time=1,
        due_time=4,
        category=CustomerCategory.PARTIALLY_SPOT,
        fare_per_teu=25,
    )

    assert demand.demand_id == "K001"
    assert demand.origin == "A"
    assert demand.destination == "C"
    assert demand.volume == pytest.approx(12.0)
    assert demand.fare_per_teu == pytest.approx(25.0)
    assert demand.maximum_revenue == pytest.approx(300.0)


def test_partially_spot_demand_allows_fractional_acceptance() -> None:
    """A partially-spot customer may be accepted fractionally."""
    demand = make_demand(category=CustomerCategory.PARTIALLY_SPOT)

    assert demand.accepted_volume(0.25) == pytest.approx(3.0)
    assert demand.accepted_revenue(0.25) == pytest.approx(75.0)


def test_regular_demand_requires_full_acceptance() -> None:
    """A regular customer's request cannot be partially rejected."""
    demand = make_demand(category=CustomerCategory.REGULAR)

    assert demand.accepted_volume(1.0) == pytest.approx(12.0)

    with pytest.raises(ValueError, match="fully accepted"):
        demand.accepted_volume(0.75)


def test_fully_spot_demand_requires_binary_acceptance() -> None:
    """A fully-spot request must be accepted entirely or rejected."""
    demand = make_demand(category=CustomerCategory.FULLY_SPOT)

    assert demand.accepted_volume(0.0) == pytest.approx(0.0)
    assert demand.accepted_volume(1.0) == pytest.approx(12.0)

    with pytest.raises(ValueError, match="fully accepted or rejected"):
        demand.accepted_volume(0.5)


def test_acceptance_fraction_cannot_exceed_one() -> None:
    """No demand may be accepted above its requested volume."""
    demand = make_demand()

    with pytest.raises(ValueError, match="must not exceed one"):
        demand.accepted_volume(1.01)


@pytest.mark.parametrize(
    ("reservation_time", "availability_time", "due_time", "message"),
    [
        (2, 1, 4, "reservation_time"),
        (0, 4, 3, "availability_time"),
        (-1, 1, 4, "non-negative"),
    ],
)
def test_invalid_time_order_is_rejected(
    reservation_time: int,
    availability_time: int,
    due_time: int,
    message: str,
) -> None:
    """Demand times must be nonnegative and logically ordered."""
    with pytest.raises(ValueError, match=message):
        Demand(
            demand_id="K001",
            volume=12.0,
            origin="A",
            destination="C",
            reservation_time=reservation_time,
            availability_time=availability_time,
            due_time=due_time,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=25.0,
        )


@pytest.mark.parametrize("invalid_volume", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_volume_is_rejected(invalid_volume: float) -> None:
    """A realised demand requires finite, strictly positive volume."""
    with pytest.raises(ValueError):
        Demand(
            demand_id="K001",
            volume=invalid_volume,
            origin="A",
            destination="C",
            reservation_time=0,
            availability_time=1,
            due_time=4,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=25.0,
        )


def test_negative_or_nonfinite_fare_is_rejected() -> None:
    """Fare must be finite and nonnegative."""
    with pytest.raises(ValueError):
        Demand(
            demand_id="K001",
            volume=12.0,
            origin="A",
            destination="C",
            reservation_time=0,
            availability_time=1,
            due_time=4,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=float("nan"),
        )

    with pytest.raises(ValueError):
        Demand(
            demand_id="K001",
            volume=12.0,
            origin="A",
            destination="C",
            reservation_time=0,
            availability_time=1,
            due_time=4,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=-1.0,
        )


def test_origin_and_destination_must_be_different() -> None:
    """A transportation demand must require actual movement."""
    with pytest.raises(ValueError, match="must be different"):
        Demand(
            demand_id="K001",
            volume=12.0,
            origin="A",
            destination="A",
            reservation_time=0,
            availability_time=1,
            due_time=4,
            category=CustomerCategory.PARTIALLY_SPOT,
            fare_per_teu=25.0,
        )


def test_invalid_customer_category_is_rejected() -> None:
    """Raw unsupported category strings must not enter the domain model."""
    with pytest.raises(TypeError, match="CustomerCategory"):
        Demand(
            demand_id="K001",
            volume=12.0,
            origin="A",
            destination="C",
            reservation_time=0,
            availability_time=1,
            due_time=4,
            category=cast(CustomerCategory, "X"),
            fare_per_teu=25.0,
        )
