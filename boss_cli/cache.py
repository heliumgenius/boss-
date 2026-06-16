"""Simple TTL cache for resolved friendId→uid/jobId mappings.

Usage:
    from boss_cli.cache import friend_uid_cache
    cached = friend_uid_cache.get("friend_uid:123")
    if cached:
        uid, job_id = cached["uid"], cached["job_id"]
"""

import time
from typing import Any


class TTLCache:
    """Simple TTL-based cache for API resolutions.

    Args:
        ttl_seconds: Time-to-live in seconds. Default 60.
    """

    def __init__(self, ttl_seconds: int = 60):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._store.pop(key)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def clear(self) -> None:
        self._store.clear()


friend_uid_cache = TTLCache(ttl_seconds=60)
