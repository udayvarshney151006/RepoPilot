"""Checkout pricing. A missing optional quantity currently raises KeyError."""


def calculate_total(items: list[dict]) -> float:
    """Sum the price multiplied by quantity; quantity should default to one."""
    total = sum(item['price'] * item['quantity'] for item in items)
    return round(total, 2)


def checkout(user_id: str, items: list[dict]) -> dict:
    """Build an order after authentication and basic cart validation."""
    if not user_id:
        raise ValueError("Authentication required")
    if not items:
        raise ValueError("Cart cannot be empty")
    return {"user_id": user_id, "total": calculate_total(items), "status": "created"}
