3e3b81f feat(infra): in-memory rate limiter, session store, execution tracker

 src/infrastructure/execution_tracker.py     | 29 ++++++++++++++++
 src/infrastructure/rate_limiter.py          | 28 +++++++++++++++
 src/infrastructure/session_store.py         | 22 ++++++++++++
 tests/infrastructure/test_state_adapters.py | 54 +++++++++++++++++++++++++++++
 4 files changed, 133 insertions(+)

diff --git a/src/infrastructure/execution_tracker.py b/src/infrastructure/execution_tracker.py
new file mode 100644
index 0000000..9882973
--- /dev/null
+++ b/src/infrastructure/execution_tracker.py
@@ -0,0 +1,29 @@
+"""In-memory single-execution tracker."""
+
+from src.domain.exceptions import ExecutionBusyError
+from src.domain.interfaces import ExecutionTracker
+from src.domain.models import Execution, Prompt
+
+
+class InMemoryExecutionTracker(ExecutionTracker):
+    """Allows exactly one active execution at a time."""
+
+    def __init__(self) -> None:
+        self._current: Execution | None = None
+
+    def try_start(self, prompt: Prompt) -> Execution:
+        """Start tracking; raise ExecutionBusyError when busy."""
+        if self._current is not None:
+            raise ExecutionBusyError(
+                "An execution is already running. Use /status or /cancel."
+            )
+        self._current = Execution(prompt=prompt)
+        return self._current
+
+    def finish(self) -> None:
+        """Clear the active execution."""
+        self._current = None
+
+    def current(self) -> Execution | None:
+        """Return the active execution, if any."""
+        return self._current
diff --git a/src/infrastructure/rate_limiter.py b/src/infrastructure/rate_limiter.py
new file mode 100644
index 0000000..f8c7b40
--- /dev/null
+++ b/src/infrastructure/rate_limiter.py
@@ -0,0 +1,28 @@
+"""In-memory per-user rate limiter."""
+
+from __future__ import annotations
+
+import time
+from typing import Callable
+
+from src.domain.exceptions import RateLimitError
+from src.domain.interfaces import RateLimiter
+
+
+class InMemoryRateLimiter(RateLimiter):
+    """Allows one action per user per cooldown window."""
+
+    def __init__(
+        self, cooldown_seconds: float, clock: Callable[[], float] = time.monotonic
+    ) -> None:
+        self._cooldown = cooldown_seconds
+        self._clock = clock
+        self._last_seen: dict[int, float] = {}
+
+    def check(self, user_id: int) -> None:
+        """Raise RateLimitError if the user is inside the cooldown window."""
+        now = self._clock()
+        last = self._last_seen.get(user_id)
+        if last is not None and now - last < self._cooldown:
+            raise RateLimitError(self._cooldown - (now - last))
+        self._last_seen[user_id] = now
diff --git a/src/infrastructure/session_store.py b/src/infrastructure/session_store.py
new file mode 100644
index 0000000..a6fde81
--- /dev/null
+++ b/src/infrastructure/session_store.py
@@ -0,0 +1,22 @@
+"""In-memory session store."""
+
+from src.domain.interfaces import SessionStore
+
+
+class InMemorySessionStore(SessionStore):
+    """Keeps the current agent session id per user (volatile)."""
+
+    def __init__(self) -> None:
+        self._sessions: dict[int, str] = {}
+
+    def get(self, user_id: int) -> str | None:
+        """Return the user's session id, if any."""
+        return self._sessions.get(user_id)
+
+    def set(self, user_id: int, session_id: str) -> None:
+        """Store the user's session id."""
+        self._sessions[user_id] = session_id
+
+    def clear(self, user_id: int) -> None:
+        """Drop the user's session id."""
+        self._sessions.pop(user_id, None)
diff --git a/tests/infrastructure/test_state_adapters.py b/tests/infrastructure/test_state_adapters.py
new file mode 100644
index 0000000..a319812
--- /dev/null
+++ b/tests/infrastructure/test_state_adapters.py
@@ -0,0 +1,54 @@
+"""Tests for in-memory state adapters."""
+
+import pytest
+
+from src.domain.exceptions import ExecutionBusyError, RateLimitError
+from src.domain.models import Prompt
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.rate_limiter import InMemoryRateLimiter
+from src.infrastructure.session_store import InMemorySessionStore
+
+
+def test_rate_limiter_allows_first_call():
+    InMemoryRateLimiter(10).check(1)  # must not raise
+
+
+def test_rate_limiter_blocks_within_cooldown():
+    limiter = InMemoryRateLimiter(10)
+    limiter.check(1)
+    with pytest.raises(RateLimitError):
+        limiter.check(1)
+
+
+def test_rate_limiter_allows_after_cooldown():
+    now = [100.0]
+    limiter = InMemoryRateLimiter(10, clock=lambda: now[0])
+    limiter.check(1)
+    now[0] += 11
+    limiter.check(1)  # must not raise
+
+
+def test_rate_limiter_users_are_independent():
+    limiter = InMemoryRateLimiter(10)
+    limiter.check(1)
+    limiter.check(2)  # must not raise
+
+
+def test_session_store_roundtrip():
+    store = InMemorySessionStore()
+    assert store.get(1) is None
+    store.set(1, "sess-1")
+    assert store.get(1) == "sess-1"
+    store.clear(1)
+    assert store.get(1) is None
+
+
+def test_tracker_single_execution():
+    tracker = InMemoryExecutionTracker()
+    assert tracker.current() is None
+    execution = tracker.try_start(Prompt(text="a", user_id=1))
+    assert tracker.current() is execution
+    with pytest.raises(ExecutionBusyError):
+        tracker.try_start(Prompt(text="b", user_id=2))
+    tracker.finish()
+    assert tracker.current() is None
