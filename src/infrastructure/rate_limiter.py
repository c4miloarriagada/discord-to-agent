"""In-memory per-user rate limiter."""

from __future__ import annotations

import time
from typing import Callable

from src.domain.exceptions import RateLimitError
from src.domain.interfaces import RateLimiter


class InMemoryRateLimiter(RateLimiter):
    """Allows one action per user per cooldown window."""

    def __init__(
        self, cooldown_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._last_seen: dict[int, float] = {}

    def check(self, user_id: int) -> None:
        """Raise RateLimitError if the user is inside the cooldown window."""
        now = self._clock()
        last = self._last_seen.get(user_id)
        if last is not None and now - last < self._cooldown:
            raise RateLimitError(self._cooldown - (now - last))
        self._last_seen[user_id] = now
