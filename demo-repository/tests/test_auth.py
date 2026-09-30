import pytest

from shop.auth import authenticate_user, hash_password, issue_token, validate_token
from shop.routes import checkout_handler, login_handler


def test_login_and_protected_checkout():
    users = {"dev@example.test": {"id": "user-1", "password_hash": hash_password("correct-password")}}
    secret = "unit-test-signing-key"
    login = login_handler({"email": "dev@example.test", "password": "correct-password"}, users, secret)
    order = checkout_handler({"items": [{"price": 10, "quantity": 2}]}, f"Bearer {login['access_token']}", secret)
    assert order["total"] == 20
    assert order["user_id"] == "user-1"


def test_wrong_password_is_rejected():
    users = {"dev@example.test": {"id": "user-1", "password_hash": hash_password("correct-password")}}
    with pytest.raises(ValueError, match="credentials"):
        authenticate_user("dev@example.test", "wrong-password", users)


def test_invalid_signature_is_rejected():
    token = issue_token("user-1", "unit-test-signing-key")
    with pytest.raises(ValueError, match="signature"):
        validate_token(token, "different-unit-test-key")


def test_expired_token_is_rejected():
    token = issue_token("user-1", "unit-test-signing-key", ttl_seconds=-1)
    with pytest.raises(ValueError, match="Expired"):
        validate_token(token, "unit-test-signing-key")
