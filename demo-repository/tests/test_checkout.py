import pytest

from shop.checkout import calculate_total, checkout


def test_total_with_explicit_quantity():
    assert calculate_total([{"price": 10.0, "quantity": 2}]) == 20.0


def test_missing_quantity_defaults_to_one():
    # Deliberate regression: this fails before the agent's proposed patch.
    assert calculate_total([{"price": 12.5}]) == 12.5


def test_empty_cart_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        checkout("user-1", [])
