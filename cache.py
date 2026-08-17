"""Redis cache utility — optional, falls back to in-memory cache if Redis unavailable."""

import os
import json
import time
from typing import Optional, Any

_REDIS_URL = os.getenv("REDIS_URL", "")

_cache: dict[str, tuple[Any, float]] = {}

try:
    if _REDIS_URL:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(_REDIS_URL, decode_responses=True)
        _redis_client.ping()
    else:
        _redis_client = None
except Exception:
    _redis_client = None


def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache. Returns None if not found."""
    if _redis_client:
        val = _redis_client.get(key)
        if val:
            return json.loads(val)
        return None
    # In-memory fallback
    entry = _cache.get(key)
    if entry:
        value, expires_at = entry
        if time.time() < expires_at:
            return value
        del _cache[key]
    return None


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set a value in cache with TTL in seconds (default 5 min)."""
    if _redis_client:
        _redis_client.setex(key, ttl, json.dumps(value, default=str))
    else:
        _cache[key] = (value, time.time() + ttl)


def cache_delete(key: str) -> None:
    """Delete a key from cache."""
    if _redis_client:
        _redis_client.delete(key)
    else:
        _cache.pop(key, None)


def cache_flush_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern (e.g., 'flights:*')."""
    if _redis_client:
        for key in _redis_client.scan_iter(match=pattern):
            _redis_client.delete(key)
    else:
        keys_to_delete = [k for k in _cache if pattern.replace("*", "") in k]
        for k in keys_to_delete:
            del _cache[k]
