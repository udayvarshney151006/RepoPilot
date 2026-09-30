import hashlib
import json

import redis

from app.config import settings


def client():
    return redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1) if settings.redis_url else None


def key(*parts: str) -> str:
    return "repopilot:query:" + hashlib.sha256("\0".join(parts).encode()).hexdigest()


def get(key: str):
    try:
        connection = client()
        value = connection.get(key) if connection else None
        return json.loads(value) if value else None
    except (redis.RedisError, ValueError):
        return None


def put(key: str, value: dict):
    try:
        connection = client()
        if connection:
            connection.setex(key, settings.query_cache_ttl, json.dumps(value))
    except redis.RedisError:
        pass  # Cache failure does not make evidence retrieval unavailable.
