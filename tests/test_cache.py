"""Tests for TTL cache."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from boss_cli.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", {"value": 42})
        assert cache.get("key1") == {"value": 42}

    def test_get_missing_key(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_expiry(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set("key1", "value")
        time.sleep(1.5)
        assert cache.get("key1") is None

    def test_clear(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key1", "v1")
        cache.set("key2", "v2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_lazy_eviction_only_expired(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("volatile", "will_expire")
        cache.set("permanent", "stays")

        now = time.time()
        cache._store["volatile"] = (now - 1, "will_expire")
        cache._store["permanent"] = (now + 3600, "stays")

        assert cache.get("volatile") is None
        assert cache.get("permanent") == "stays"

    def test_race_condition_safe_get(self):
        cache = TTLCache(ttl_seconds=-1)
        cache.set("key", "val")
        assert cache.get("key") is None
        assert cache.get("key") is None

    def test_different_instances_independent(self):
        cache1 = TTLCache(ttl_seconds=60)
        cache2 = TTLCache(ttl_seconds=60)
        cache1.set("key", "cache1_val")
        assert cache2.get("key") is None
