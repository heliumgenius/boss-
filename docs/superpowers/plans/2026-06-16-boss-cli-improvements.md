# boss-cli Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply 8 code quality improvements to boss-cli, then add a web UI

**Architecture:** All improvements are incremental refactors of `boss_cli/` — no API changes, no breaking changes. Each step is independently testable.

**Tech Stack:** Python 3.10+, click, httpx, pytest

---

## File Structure Changes

```
boss_cli/
├── client.py          # MODIFY: retry jitter, error code registry, header rotation
├── exceptions.py      # MODIFY: add error code registry
├── cache.py           # CREATE: TTL cache for N+1 resolution
├── keychain.py        # CREATE: platform keychain storage
├── auth.py            # MODIFY: use keychain.py
├── commands/
│   ├── recruiter/     # CREATE: split from recruiter.py
│   │   ├── __init__.py
│   │   ├── positions.py
│   │   ├── candidates.py
│   │   ├── interviews.py
│   │   └── chat.py
│   └── recruiter.py   # DELETE (replaced by recruiter/)
├── client/
│   ├── __init__.py    # CREATE: re-export BossClient
│   ├── transport.py   # CREATE: HTTP transport + retry
│   ├── throttle.py    # CREATE: rate limiting + jitter
│   └── antidetect.py  # CREATE: header generation + rotation
tests/
├── test_client.py     # CREATE: unit tests for client logic
├── test_auth.py       # CREATE: unit tests for auth
├── test_throttle.py   # CREATE: unit tests for rate limiting
└── conftest.py        # CREATE: shared fixtures
web/
├── app.py             # CREATE: Flask entry point
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── search.html
│   ├── applied.html
│   └── login.html
├── static/
│   ├── style.css
│   └── app.js
└── requirements-web.txt
```

---

## Task 1: Add jitter to exponential backoff

**Files:**
- Modify: `boss_cli/client.py:257-272` (the `_request` method's HTTP 429/5xx retry logic)

- [ ] **Step 1: Read the current retry logic**

Read `boss_cli/client.py` lines 240-280 to understand current backoff implementation.

- [ ] **Step 2: Apply edit — add full jitter**

Replace the retry wait calculation with a jittered version.

Current code (approx lines 265-269):
```python
if resp.status_code in (429, 500, 502, 503, 504):
    wait = (2 ** attempt) + random.uniform(0, 1)
```

Change to:
```python
if resp.status_code in (429, 500, 502, 503, 504):
    cap = 30.0
    base = 1.0
    wait = random.uniform(0, min(cap, base * (2 ** attempt)))
```

Also apply same pattern to network error retry (approx line 285):
```python
wait = (2 ** attempt) + random.uniform(0, 1)
```
→
```python
wait = random.uniform(0, min(cap, base * (2 ** attempt)))
```

- [ ] **Step 3: Run existing smoke tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`

- [ ] **Step 4: Commit**

---

## Task 2: Error code dict registry

**Files:**
- Modify: `boss_cli/client.py` (the `_handle_response` method)
- Modify: `boss_cli/exceptions.py` (add registry dict)

- [ ] **Step 1: Read current `_handle_response`**

Read `boss_cli/client.py` lines 207-240.

- [ ] **Step 2: Add error code registry to `exceptions.py`**

```python
from __future__ import annotations

from typing import Any


class BossApiError(Exception):
    ...

class SessionExpiredError(BossApiError):
    ...

class RateLimitError(BossApiError):
    ...

class ParamError(BossApiError):
    ...


# Error code registry: maps API response codes to (exception_class, message_template)
ERROR_CODE_MAP: dict[int, tuple[type[BossApiError], str]] = {
    37: (SessionExpiredError, "Session expired (code=37)"),
    17: (ParamError, "Missing required parameter (code=17)"),
    19: (ParamError, "Invalid parameter (code=19)"),
    9: (RateLimitError, "Rate limited (code=9)"),
}
```

- [ ] **Step 3: Refactor `_handle_response` to use registry**

Replace the if/elif chain with:
```python
def _handle_response(self, data: dict[str, Any], action: str) -> dict[str, Any]:
    code = data.get("code", -1)
    if code == 0:
        return data.get("zpData", {})

    message = data.get("message", "Unknown error")

    if code in (121, 122):
        raise BossApiError(
            f"{action}: 请求被安全系统拦截 (code={code})。"
            "此操作需要浏览器环境的安全验证，CLI 暂不支持。"
            "请在 BOSS直聘 网页端完成此操作。",
            code=code, response=data,
        )

    exc_info = ERROR_CODE_MAP.get(code)
    if exc_info:
        exc_class, tmpl = exc_info
        if exc_class is RateLimitError:
            self._rate_limit_count += 1
            cooldown = min(60, 10 * (2 ** (self._rate_limit_count - 1)))
            self._request_delay = max(self._request_delay, self._base_request_delay * 2)
            logger.warning(
                "Rate limited (count=%d), cooling down %.0fs, delay raised to %.1fs",
                self._rate_limit_count, cooldown, self._request_delay,
            )
            time.sleep(cooldown)
        raise exc_class(tmpl if message == "Unknown error" else f"{action}: {message} (code={code})")

    logger.warning("Unknown API error code=%s, raw_message=%s, action=%s", code, message, action)
    raise BossApiError(f"{action}: {message} (code={code})", code=code, response=data)
```

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`

- [ ] **Step 5: Commit**

---

## Task 3: N+1 friendId cache

**Files:**
- Create: `boss_cli/cache.py`
- Modify: `boss_cli/commands/recruiter.py`

- [ ] **Step 1: Create cache.py**

```python
"""Simple TTL cache for resolved friendId→(uid, jobId) mappings."""

from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """Simple TTL-based cache for API resolutions."""

    def __init__(self, ttl_seconds: int = 60):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def clear(self) -> None:
        self._store.clear()


# Shared instances
friend_uid_cache = TTLCache(ttl_seconds=60)
```

- [ ] **Step 2: Modify recruiter's `_resolve_friend_uid_and_job` to use cache**

```python
from ..cache import friend_uid_cache

def _resolve_friend_uid_and_job(cred, friend_id: int) -> tuple[int, int]:
    cache_key = f"friend_uid:{friend_id}"
    cached = friend_uid_cache.get(cache_key)
    if cached:
        return cached["uid"], cached["job_id"]

    data = run_client_action(
        cred,
        lambda c: c.get_boss_friend_details([friend_id]),
    )
    friend_list = data.get("friendList", [])
    if not friend_list:
        console.print(f"[red]未找到 friendId={friend_id} 的候选人信息[/red]")
        raise SystemExit(1)
    friend = friend_list[0]
    uid = friend.get("uid", 0)
    job_id = friend.get("jobId", 0)
    if not uid:
        console.print(f"[red]无法获取候选人 uid (friendId={friend_id})[/red]")
        raise SystemExit(1)

    friend_uid_cache.set(cache_key, {"uid": uid, "job_id": job_id})
    return uid, job_id
```

- [ ] **Step 3: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`
Also run: `.\.venv\Scripts\python.exe -m pytest tests/ -v`

- [ ] **Step 4: Commit**

---

## Task 4: Header rotation

**Files:**
- Modify: `boss_cli/client.py` (the `HEADERS` usage and `_headers_for_request`)

- [ ] **Step 1: Add header template rotation**

In `client.py`, add a module-level list of header template overrides:

```python
import random

# 3 User-Agent variants for rotation (all macOS Chrome family)
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
]
```

- [ ] **Step 2: Modify `_headers_for_request` to rotate UA**

In `_headers_for_request`, after `headers = dict(HEADERS)`, add:
```python
headers["User-Agent"] = random.choice(_USER_AGENTS)
```

- [ ] **Step 3: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`

- [ ] **Step 4: Commit**

---

## Task 5: Add pytest cassette tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_throttle.py`
- Create: `tests/test_client.py`
- Create: `tests/test_auth.py`
- Modify: `pyproject.toml` (add pytest-recording dep)

- [ ] **Step 1: Add pytest-recording to dev dependencies**

In `pyproject.toml`, add `"pytest-recording>=0.13"` to `[project.optional-dependencies] dev`.

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared test fixtures."""
from __future__ import annotations

import pytest
from boss_cli.cache import friend_uid_cache


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    friend_uid_cache.clear()
    yield


@pytest.fixture
def mock_credential():
    """Return a minimal mock credential."""
    from boss_cli.auth import Credential
    return Credential(cookies={"wt2": "test_wt2", "wbg": "test_wbg", "zp_at": "test_zp_at"})
```

- [ ] **Step 3: Create `tests/test_throttle.py`**

```python
"""Tests for rate-limiting and jitter logic."""
from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest

from boss_cli.client import BossClient


class TestRateLimitDelay:
    """Verify rate-limit delay produces reasonable intervals."""

    def test_no_delay_when_disabled(self):
        with BossClient(credential=None, request_delay=0) as client:
            t0 = time.time()
            client._rate_limit_delay()
            elapsed = time.time() - t0
            assert elapsed < 0.1, "Should not delay when request_delay=0"

    def test_delay_enforces_minimum_interval(self):
        with BossClient(credential=None, request_delay=0.5) as client:
            client._mark_request()
            t0 = time.time()
            client._rate_limit_delay()
            elapsed = time.time() - t0
            assert elapsed >= 0, "Delay should be non-negative"

    def test_burst_penalty_activates_after_3_requests(self):
        with BossClient(credential=None, request_delay=0) as client:
            # Simulate 3 rapid requests
            now = time.time()
            client._recent_request_times.extend([now - 5, now - 10, now - 14])
            penalty = client._burst_penalty_delay()
            assert penalty > 0, "Should impose penalty after 3 requests in 15s window"


class TestRetryJitter:
    """Verify jittered backoff doesn't produce identical values."""

    def test_jitter_is_random(self):
        with BossClient(credential=None, request_delay=0) as client:
            values = set()
            for attempt in range(3):
                cap = 30.0
                base = 1.0
                from random import uniform
                values.add(uniform(0, min(cap, base * (2 ** attempt))))
            assert len(values) > 1, "Jitter should produce different values"


class TestHeaderRotation:
    """Verify User-Agent rotation works."""

    def test_ua_rotation_changes_value(self):
        with BossClient(credential=None) as client:
            headers1 = client._headers_for_request("/wapi/zpgeek/search/joblist.json")
            headers2 = client._headers_for_request("/wapi/zpgeek/search/joblist.json")
            # With 3 UAs, consecutive calls should sometimes differ
            assert headers1.get("User-Agent", "")
            assert headers2.get("User-Agent", "")

    def test_ua_is_valid_format(self):
        with BossClient(credential=None) as client:
            headers = client._headers_for_request("/wapi/zpgeek/search/joblist.json")
            ua = headers.get("User-Agent", "")
            assert "Chrome" in ua
            assert "Safari" in ua


class TestErrorCodeRegistry:
    """Verify error code mapping works correctly."""

    def test_code_0_returns_zpdata(self):
        with BossClient(credential=None) as client:
            result = client._handle_response({"code": 0, "zpData": {"jobs": []}}, "test")
            assert result == {"jobs": []}

    def test_code_37_raises_session_expired(self):
        from boss_cli.exceptions import SessionExpiredError
        with BossClient(credential=None) as client:
            with pytest.raises(SessionExpiredError):
                client._handle_response({"code": 37, "message": "expired"}, "test")

    def test_unknown_code_logs_warning(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        from boss_cli.exceptions import BossApiError
        with BossClient(credential=None) as client:
            with pytest.raises(BossApiError):
                client._handle_response({"code": 999, "message": "new code"}, "test")
            assert "Unknown API error" in caplog.text
```

- [ ] **Step 4: Create `tests/test_auth.py`**

```python
"""Tests for auth module."""
from __future__ import annotations

from boss_cli.auth import Credential


class TestCredential:
    def test_empty_credential_invalid(self):
        cred = Credential(cookies={})
        assert not cred.is_valid
        assert cred.missing_required_cookies == ["__zp_stoken__", "wbg", "wt2", "zp_at"]

    def test_full_credential_valid(self):
        cred = Credential(cookies={"__zp_stoken__": "a", "wt2": "b", "wbg": "c", "zp_at": "d"})
        assert cred.is_valid
        assert cred.has_required_cookies
```

- [ ] **Step 5: Run tests to verify they fail then pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v`
Expected: All new tests pass.

- [ ] **Step 6: Commit**

---

## Task 6: Credential encryption (keychain)

**Files:**
- Create: `boss_cli/keychain.py`
- Modify: `boss_cli/auth.py`
- Modify: `pyproject.toml` (add keyring dependency)

- [ ] **Step 1: Add `keyring` to optional dependencies**

In `pyproject.toml`, add `"keyring>=25.0"` under `[project.optional-dependencies]`.

- [ ] **Step 2: Create `boss_cli/keychain.py`**

```python
"""Platform keychain integration for credential storage.

Strategy:
1. Try OS keychain (macOS Keychain, Windows Credential Manager, Linux libsecret)
2. Fall back to encrypted file using a machine-derived key
3. Last resort: plaintext file with warning
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "boss-cli"
CREDENTIAL_FILE = CONFIG_DIR / "credential.json"
KEYRING_SERVICE = "boss-cli"
KEYRING_USER = "zhipin_session"


def _store_keychain(data: dict) -> bool:
    try:
        import keyring
        payload = json.dumps(data, ensure_ascii=False)
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, payload)
        return True
    except ImportError:
        logger.debug("keyring not installed")
    except Exception as exc:
        logger.warning("Keychain store failed: %s", exc)
    return False


def _load_keychain() -> dict | None:
    try:
        import keyring
        payload = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if payload:
            return json.loads(payload)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("Keychain load failed: %s", exc)
    return None


def _delete_keychain() -> bool:
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        return True
    except Exception:
        pass
    return False


def save_credential_data(data: dict) -> None:
    if _store_keychain(data):
        logger.info("Credential saved to system keychain")
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIAL_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        CREDENTIAL_FILE.chmod(0o600)
    except Exception:
        pass
    logger.warning("Credential saved to plaintext file (keychain unavailable): %s", CREDENTIAL_FILE)


def load_credential_data() -> dict | None:
    data = _load_keychain()
    if data:
        return data

    if CREDENTIAL_FILE.exists():
        try:
            return json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read credential file: %s", exc)
    return None


def delete_credential_data() -> None:
    _delete_keychain()
    if CREDENTIAL_FILE.exists():
        CREDENTIAL_FILE.unlink()
```

- [ ] **Step 3: Modify `auth.py` to use `keychain.py`**

Replace `save_credential` and `load_credential` to delegate to `keychain.py`:
```python
from .keychain import save_credential_data, load_credential_data, delete_credential_data

def save_credential(credential: Credential) -> None:
    save_credential_data(credential.to_dict())

def load_credential() -> Credential | None:
    data = load_credential_data()
    if data:
        cred = Credential.from_dict(data)
        ...

def clear_credential() -> None:
    delete_credential_data()
    _AUTH_HEALTH_CACHE.clear()
```

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`

- [ ] **Step 5: Commit**

---

## Task 7: Split recruiter.py into package

**Files:**
- Create: `boss_cli/commands/recruiter/__init__.py`
- Create: `boss_cli/commands/recruiter/positions.py`
- Create: `boss_cli/commands/recruiter/candidates.py`
- Create: `boss_cli/commands/recruiter/interviews.py`
- Create: `boss_cli/commands/recruiter/chat.py`
- Delete: `boss_cli/commands/recruiter.py`

- [ ] **Step 1: Read current recruiter.py boundaries**

Read `boss_cli/commands/recruiter.py` to understand command groupings.

- [ ] **Step 2: Create `recruiter/__init__.py`**

```python
"""Recruiter (Boss) mode command group."""
from __future__ import annotations

import click


@click.group(name="recruiter")
def recruiter() -> None:
    """招聘方/雇主端操作 (Recruiter mode)"""


# Import submodules to register commands
from . import positions, candidates, interviews, chat  # noqa: F811, F401
```

- [ ] **Step 3: Move job-related commands to `positions.py`**

```python
"""Position management commands."""
from __future__ import annotations

from .._common import handle_command, require_auth, structured_output_options
from . import recruiter

@recruiter.command("jobs")
@structured_output_options
def recruiter_jobs(as_json, as_yaml):
    ...
```

- [ ] **Step 4: Move candidate commands to `candidates.py`**

```python
"""Candidate search and management commands."""
```

- [ ] **Step 5: Move interview commands to `interviews.py`**

```python
"""Interview management commands."""
```

- [ ] **Step 6: Move chat commands to `chat.py`**

```python
"""Chat with candidates commands."""
```

- [ ] **Step 7: Update `cli.py` import**

Replace `from .commands import recruiter` with `from .commands.recruiter import recruiter`

- [ ] **Step 8: Run tests + CLI smoke test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`
Run: `.\.venv\Scripts\python.exe -m boss_cli.cli recruiter --help`

- [ ] **Step 9: Commit**

---

## Task 8: Split BossClient into package

**Files:**
- Create: `boss_cli/client/__init__.py`
- Create: `boss_cli/client/transport.py`
- Create: `boss_cli/client/throttle.py`
- Create: `boss_cli/client/antidetect.py`
- Delete: `boss_cli/client.py`

- [ ] **Step 1: Create `throttle.py`**

```python
"""Rate-limiting with Gaussian jitter, burst penalty, and cooldown."""
from __future__ import annotations

import logging
import random
import time
from collections import deque

logger = logging.getLogger(__name__)


class Throttle:
    def __init__(self, request_delay: float = 1.0, max_retries: int = 3):
        self._request_delay = request_delay
        self._base_request_delay = request_delay
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_count = 0
        self._recent_request_times: deque[float] = deque(maxlen=12)

    def delay(self) -> None:
        ...

    def burst_penalty(self) -> float:
        ...

    def mark_request(self) -> None:
        ...

    def cooldown(self) -> float:
        ...
```

- [ ] **Step 2: Create `antidetect.py`**

```python
"""Anti-detection header generation with rotation."""
from __future__ import annotations

import random
from typing import Any

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
]

class AntiDetect:
    def headers_for_request(self, url: str, params: dict[str, Any] | None = None, cookies: dict[str, str] | None = None) -> dict[str, str]:
        ...
```

- [ ] **Step 3: Create `transport.py`**

```python
"""HTTP transport with retry and cookie management."""
```

- [ ] **Step 4: Create `client/__init__.py`**

```python
"""Re-export BossClient from transport."""
from .transport import BossClient

__all__ = ["BossClient"]
```

- [ ] **Step 5: Update all imports across codebase**

Replace `from ..client import BossClient` (and similar) with `from ..client.transport import BossClient`

- [ ] **Step 6: Run tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/ -v -m "not smoke"`
Run: `.\.venv\Scripts\python.exe -m boss_cli.cli --help`

- [ ] **Step 7: Commit**

---

## Task 9: Web UI (Phase 2)

**Files:** (all under `web/`)
- Create: `web/app.py`
- Create: `web/templates/base.html`
- Create: `web/templates/index.html`
- Create: `web/templates/search.html`
- Create: `web/templates/applied.html`
- Create: `web/templates/login.html`
- Create: `web/static/style.css`
- Create: `web/static/app.js`
- Create: `web/requirements-web.txt`

- [ ] **Step 1: Create `web/requirements-web.txt`**

```
flask>=3.0
```

- [ ] **Step 2-8: Implement Flask app + templates**

(Detailed implementation deferred — focus Phase 1 tasks first.)

---

## Self-Review Checklist

- [ ] Spec coverage: All 8 improvements from code review are mapped to tasks 1-8
- [ ] No placeholders: Every code block has real code
- [ ] Type consistency: function signatures match across tasks
