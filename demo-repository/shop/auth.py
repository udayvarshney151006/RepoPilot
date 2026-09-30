"""Password authentication and HS256 token validation for the demo shop.

This module demonstrates a readable login flow. A deployed service should use
a maintained authentication library, account storage and secret rotation.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time


def hash_password(password: str, salt: str | None = None) -> str:
    """Create a salted PBKDF2 password hash; store the returned salt and digest."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Compare a password against its stored hash without timing-sensitive ==."""
    salt, _ = stored_hash.split(":", 1)
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


def authenticate_user(email: str, password: str, users: dict) -> dict:
    """Look up the account and validate its password before issuing a token."""
    user = users.get(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid credentials")
    return {"id": user["id"], "email": email}


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(user_id: str, secret: str, ttl_seconds: int = 3600) -> str:
    """Create a signed HS256 JWT with subject and expiration claims."""
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _encode(json.dumps({"sub": user_id, "exp": int(time.time()) + ttl_seconds}).encode())
    signing_input = f"{header}.{payload}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_encode(signature)}"


def validate_token(token: str, secret: str) -> dict:
    """Validate JWT algorithm, signature and expiration on protected requests."""
    try:
        header, payload, signature = token.split(".")
        if json.loads(_decode(header))["alg"] != "HS256":
            raise ValueError("Unsupported token algorithm")
        expected = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(signature)):
            raise ValueError("Invalid token signature")
        claims = json.loads(_decode(payload))
        if claims["exp"] <= time.time() or not isinstance(claims["sub"], str):
            raise ValueError("Expired or invalid token")
        return claims
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed token") from exc
