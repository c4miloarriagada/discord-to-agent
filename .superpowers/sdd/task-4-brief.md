### Task 4: In-memory state adapters (rate limiter, session store, execution tracker)

**Files:**
- Create: `src/infrastructure/rate_limiter.py`, `src/infrastructure/session_store.py`, `src/infrastructure/execution_tracker.py`
- Test: `tests/infrastructure/test_state_adapters.py`

**Interfaces:**
- Consumes: `RateLimiter`, `SessionStore`, `ExecutionTracker` ports; `RateLimitError`, `ExecutionBusyError`.
- Produces: `InMemoryRateLimiter(cooldown_seconds: float, clock=time.monotonic)`, `InMemorySessionStore()`, `InMemoryExecutionTracker()`.

- [ ] **Step 1: Write the failing test** — `tests/infrastructure/test_state_adapters.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/infrastructure/test_state_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `src/infrastructure/rate_limiter.py`**

```python
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
```

- [ ] **Step 4: Write `src/infrastructure/session_store.py`**

```python
"""In-memory session store."""

from src.domain.interfaces import SessionStore


class InMemorySessionStore(SessionStore):
    """Keeps the current agent session id per user (volatile)."""

    def __init__(self) -> None:
        self._sessions: dict[int, str] = {}

    def get(self, user_id: int) -> str | None:
        """Return the user's session id, if any."""
        return self._sessions.get(user_id)

    def set(self, user_id: int, session_id: str) -> None:
        """Store the user's session id."""
        self._sessions[user_id] = session_id

    def clear(self, user_id: int) -> None:
        """Drop the user's session id."""
        self._sessions.pop(user_id, None)
```

- [ ] **Step 5: Write `src/infrastructure/execution_tracker.py`**

```python
"""In-memory single-execution tracker."""

from src.domain.exceptions import ExecutionBusyError
from src.domain.interfaces import ExecutionTracker
from src.domain.models import Execution, Prompt


class InMemoryExecutionTracker(ExecutionTracker):
    """Allows exactly one active execution at a time."""

    def __init__(self) -> None:
        self._current: Execution | None = None

    def try_start(self, prompt: Prompt) -> Execution:
        """Start tracking; raise ExecutionBusyError when busy."""
        if self._current is not None:
            raise ExecutionBusyError(
                "An execution is already running. Use /status or /cancel."
            )
        self._current = Execution(prompt=prompt)
        return self._current

    def finish(self) -> None:
        """Clear the active execution."""
        self._current = None

    def current(self) -> Execution | None:
        """Return the active execution, if any."""
        return self._current
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/infrastructure/test_state_adapters.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/infrastructure/rate_limiter.py src/infrastructure/session_store.py src/infrastructure/execution_tracker.py tests/infrastructure/test_state_adapters.py
git commit -m "feat(infra): in-memory rate limiter, session store, execution tracker"
```

---

