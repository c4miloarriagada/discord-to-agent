"""Tests for in-memory state adapters."""

import pytest

from src.domain.exceptions import ExecutionBusyError, RateLimitError
from src.domain.models import Prompt
from src.infrastructure.execution_tracker import InMemoryExecutionTracker
from src.infrastructure.rate_limiter import InMemoryRateLimiter
from src.infrastructure.session_store import InMemorySessionStore


def test_rate_limiter_allows_first_call():
    InMemoryRateLimiter(10).check(1)  # must not raise


def test_rate_limiter_blocks_within_cooldown():
    limiter = InMemoryRateLimiter(10)
    limiter.check(1)
    with pytest.raises(RateLimitError):
        limiter.check(1)


def test_rate_limiter_allows_after_cooldown():
    now = [100.0]
    limiter = InMemoryRateLimiter(10, clock=lambda: now[0])
    limiter.check(1)
    now[0] += 11
    limiter.check(1)  # must not raise


def test_rate_limiter_users_are_independent():
    limiter = InMemoryRateLimiter(10)
    limiter.check(1)
    limiter.check(2)  # must not raise


def test_session_store_roundtrip():
    store = InMemorySessionStore()
    assert store.get(1) is None
    store.set(1, "sess-1")
    assert store.get(1) == "sess-1"
    store.clear(1)
    assert store.get(1) is None


def test_tracker_single_execution():
    tracker = InMemoryExecutionTracker()
    assert tracker.current() is None
    execution = tracker.try_start(Prompt(text="a", user_id=1))
    assert tracker.current() is execution
    with pytest.raises(ExecutionBusyError):
        tracker.try_start(Prompt(text="b", user_id=2))
    tracker.finish()
    assert tracker.current() is None
