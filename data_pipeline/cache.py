"""
Cache layer (Redis with graceful fallback).

Caches expensive computations (VaR sims, factor tables). If REDIS_URL is set and
reachable, uses Redis; otherwise falls back to a process-local dict so the app
never breaks when Redis is absent. Values are JSON-serialized.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os

_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))
_REDIS_URL = os.environ.get("REDIS_URL", "").strip()

_mem: dict[str, str] = {}
_client = None
_backend = "memory"


def _redis():
    global _client, _backend
    if _client is not None:
        return _client
    if _REDIS_URL:
        try:
            import redis
            c = redis.from_url(_REDIS_URL, socket_connect_timeout=1)
            c.ping()
            _client = c
            _backend = "redis"
            return c
        except Exception:
            _backend = "memory (redis unreachable)"
    return None


def backend() -> str:
    _redis()
    return _backend


def get(key: str):
    r = _redis()
    raw = r.get(key) if r else _mem.get(key)
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


def set(key: str, value, ttl: int = _TTL):
    raw = json.dumps(value, default=str)
    r = _redis()
    if r:
        r.setex(key, ttl, raw)
    else:
        _mem[key] = raw


def cached(prefix: str, ttl: int = _TTL):
    """Decorator: cache a function's JSON-able return keyed by its args."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*args, **kwargs):
            sig = hashlib.md5(
                json.dumps([args, kwargs], default=str, sort_keys=True).encode()
            ).hexdigest()[:12]
            key = f"{prefix}:{sig}"
            hit = get(key)
            if hit is not None:
                return hit
            out = fn(*args, **kwargs)
            try:
                set(key, out, ttl)
            except TypeError:
                pass  # non-serializable; skip caching
            return out
        return wrap
    return deco


if __name__ == "__main__":
    set("demo", {"hello": 1})
    print("backend:", backend(), "| roundtrip:", get("demo"))
