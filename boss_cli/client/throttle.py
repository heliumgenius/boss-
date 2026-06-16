"""Rate-limiting with Gaussian jitter, burst penalty, and cooldown."""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class Throttle:
    """Request throttling with Gaussian jitter, burst detection, and cooldown."""

    def __init__(self, request_delay: float = 1.0):
        self._request_delay = request_delay
        self._base_request_delay = request_delay
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_count = 0
        self._recent_request_times: deque[float] = deque(maxlen=12)

    def delay(self) -> None:
        """Enforce minimum delay with Gaussian jitter to mimic human browsing."""
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            jitter = max(0, random.gauss(0.3, 0.15))
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            sleep_time = self._request_delay - elapsed + jitter
            logger.debug("Rate-limit delay: %.2fs", sleep_time)
            time.sleep(sleep_time)

        burst_penalty = self._burst_penalty_delay()
        if burst_penalty > 0:
            logger.debug("Burst penalty delay: %.2fs", burst_penalty)
            time.sleep(burst_penalty)

    def _burst_penalty_delay(self) -> float:
        """Add extra delay when a burst pattern looks less like human browsing."""
        if not self._recent_request_times:
            return 0.0
        now = time.time()
        recent_15s = sum(1 for ts in self._recent_request_times if now - ts <= 15)
        recent_45s = sum(1 for ts in self._recent_request_times if now - ts <= 45)
        if recent_45s >= 6:
            return random.uniform(4.0, 7.0)
        if recent_15s >= 3:
            return random.uniform(1.2, 2.8)
        return 0.0

    def mark_request(self) -> None:
        """Record a request timestamp."""
        now = time.time()
        self._last_request_time = now
        self._request_count += 1
        self._recent_request_times.append(now)

    def start_cooldown(self) -> None:
        """Handle rate-limit cooldown with exponential backoff."""
        self._rate_limit_count += 1
        cooldown = min(60, 10 * (2 ** (self._rate_limit_count - 1)))
        self._request_delay = max(self._request_delay, self._base_request_delay * 2)
        logger.warning(
            "Rate limited (count=%d), cooling down %.0fs, delay raised to %.1fs",
            self._rate_limit_count, cooldown, self._request_delay,
        )
        time.sleep(cooldown)

    def reset_cooldown(self) -> None:
        """Reset rate-limit counter on successful request."""
        self._rate_limit_count = 0

    @property
    def request_stats(self) -> dict[str, int | float]:
        return {
            "request_count": self._request_count,
            "last_request_time": self._last_request_time,
        }
