"""Framework-independent handlers expose the demo login and checkout flow."""

from shop.auth import authenticate_user, issue_token, validate_token
from shop.checkout import checkout


def login_handler(body: dict, users: dict, secret: str) -> dict:
    """POST /login validates a password and returns an access token."""
    user = authenticate_user(body["email"], body["password"], users)
    return {"access_token": issue_token(user["id"], secret), "token_type": "bearer"}


def require_auth(authorization: str, secret: str) -> str:
    """Protected endpoints validate the bearer token and obtain the user ID."""
    if not authorization.startswith("Bearer "):
        raise ValueError("Bearer token required")
    claims = validate_token(authorization.removeprefix("Bearer "), secret)
    return claims["sub"]


def checkout_handler(body: dict, authorization: str, secret: str) -> dict:
    """POST /checkout checks authentication before calculating the order total."""
    user_id = require_auth(authorization, secret)
    return checkout(user_id, body["items"])
