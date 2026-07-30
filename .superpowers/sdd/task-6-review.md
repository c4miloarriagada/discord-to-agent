913fe80 feat(app): prompt and approval services with history

 src/application/approval_service.py        |  33 +++++++++
 src/application/prompt_history.py          |  30 ++++++++
 src/application/prompt_service.py          | 101 ++++++++++++++++++++++++++
 tests/application/test_approval_service.py |  65 +++++++++++++++++
 tests/application/test_prompt_service.py   | 111 +++++++++++++++++++++++++++++
 tests/conftest.py                          |  93 ++++++++++++++++++++++++
 6 files changed, 433 insertions(+)

diff --git a/src/application/approval_service.py b/src/application/approval_service.py
new file mode 100644
index 0000000..0781f1f
--- /dev/null
+++ b/src/application/approval_service.py
@@ -0,0 +1,33 @@
+"""Use case: resolve Approve / Reject / Retry button actions."""
+
+from __future__ import annotations
+
+from src.application.prompt_history import PromptHistory
+from src.application.prompt_service import PromptService
+from src.domain.models import ApprovalStatus, Response
+
+
+class ApprovalService:
+    """Handles user decisions on a prompt's result."""
+
+    def __init__(self, prompt_service: PromptService, history: PromptHistory) -> None:
+        self._prompt_service = prompt_service
+        self._history = history
+
+    async def approve(self, user_id: int) -> Response:
+        """Re-run the user's last prompt with auto-approval enabled."""
+        prompt = self._history.get(user_id)
+        return await self._prompt_service.execute(prompt.text, user_id, auto_approve=True)
+
+    async def retry(self, user_id: int) -> Response:
+        """Re-run the user's last prompt unchanged."""
+        prompt = self._history.get(user_id)
+        return await self._prompt_service.execute(
+            prompt.text, user_id, auto_approve=prompt.auto_approve
+        )
+
+    async def reject(self, user_id: int) -> ApprovalStatus:
+        """Discard the user's last prompt."""
+        self._history.get(user_id)  # raises if there is nothing to reject
+        self._history.clear(user_id)
+        return ApprovalStatus.REJECTED
diff --git a/src/application/prompt_history.py b/src/application/prompt_history.py
new file mode 100644
index 0000000..14b8ebb
--- /dev/null
+++ b/src/application/prompt_history.py
@@ -0,0 +1,30 @@
+"""In-memory history of the last prompt per user."""
+
+from src.domain.exceptions import NoPreviousPromptError
+from src.domain.models import Prompt
+
+
+class PromptHistory:
+    """Remembers the most recent prompt each user sent."""
+
+    def __init__(self) -> None:
+        self._last: dict[int, Prompt] = {}
+
+    def record(self, prompt: Prompt) -> None:
+        """Store prompt as the user's most recent one."""
+        self._last[prompt.user_id] = prompt
+
+    def get(self, user_id: int) -> Prompt:
+        """Return the user's last prompt.
+
+        Raises:
+            NoPreviousPromptError: if the user has no recorded prompt.
+        """
+        try:
+            return self._last[user_id]
+        except KeyError as exc:
+            raise NoPreviousPromptError("No previous prompt to act on.") from exc
+
+    def clear(self, user_id: int) -> None:
+        """Forget the user's last prompt, if any."""
+        self._last.pop(user_id, None)
diff --git a/src/application/prompt_service.py b/src/application/prompt_service.py
new file mode 100644
index 0000000..a20461a
--- /dev/null
+++ b/src/application/prompt_service.py
@@ -0,0 +1,101 @@
+"""Use case: run a prompt against the coding agent and notify the result."""
+
+from __future__ import annotations
+
+import structlog
+
+from src.application.prompt_history import PromptHistory
+from src.domain.exceptions import (
+    NoActiveExecutionError,
+    PromptValidationError,
+)
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    Notifier,
+    RateLimiter,
+    SessionStore,
+)
+from src.domain.models import Execution, Prompt, Response
+
+logger = structlog.get_logger(__name__)
+
+
+class PromptService:
+    """Orchestrates validation, rate limiting, execution and notification."""
+
+    FORBIDDEN_TOKENS: tuple[str, ...] = (";", "|", "&&", "`", "$(")
+
+    def __init__(
+        self,
+        runner: AgentRunner,
+        tracker: ExecutionTracker,
+        rate_limiter: RateLimiter,
+        session_store: SessionStore,
+        history: PromptHistory,
+        notifier: Notifier | None = None,
+    ) -> None:
+        self._runner = runner
+        self._tracker = tracker
+        self._rate_limiter = rate_limiter
+        self._session_store = session_store
+        self._history = history
+        self._notifier = notifier
+
+    async def execute(self, text: str, user_id: int, auto_approve: bool = False) -> Response:
+        """Validate and run a prompt, then notify and store the result."""
+        self._validate(text)
+        self._rate_limiter.check(user_id)
+        prompt = Prompt(text=text, user_id=user_id, auto_approve=auto_approve)
+        self._tracker.try_start(prompt)
+        try:
+            session_id = self._session_store.get(user_id)
+            response = await self._runner.run(prompt, session_id)
+        finally:
+            self._tracker.finish()
+        if response.session_id:
+            self._session_store.set(user_id, response.session_id)
+        self._history.record(prompt)
+        if self._notifier:
+            await self._notifier.send_result(prompt, response)
+        logger.info(
+            "prompt_executed",
+            user_id=user_id,
+            success=response.success,
+            duration=round(response.duration_seconds, 2),
+        )
+        return response
+
+    def current_execution(self) -> Execution | None:
+        """Return the active execution, if any."""
+        return self._tracker.current()
+
+    async def cancel(self) -> None:
+        """Cancel the active execution.
+
+        Raises:
+            NoActiveExecutionError: if nothing is running.
+        """
+        if self._tracker.current() is None:
+            raise NoActiveExecutionError("No active execution to cancel.")
+        await self._runner.cancel()
+
+    def clear_context(self, user_id: int) -> None:
+        """Drop the user's session so the next prompt starts fresh."""
+        self._session_store.clear(user_id)
+
+    def context_percent(self, user_id: int) -> float | None:
+        """Return the user's session context usage, or None if unknown."""
+        session_id = self._session_store.get(user_id)
+        if session_id is None:
+            return None
+        return self._runner.get_context_percent(session_id)
+
+    def _validate(self, text: str) -> None:
+        if not text.strip():
+            raise PromptValidationError("The prompt cannot be empty.")
+        found = [token for token in self.FORBIDDEN_TOKENS if token in text]
+        if found:
+            raise PromptValidationError(
+                "The prompt contains forbidden characters: " + ", ".join(found)
+            )
diff --git a/tests/application/test_approval_service.py b/tests/application/test_approval_service.py
new file mode 100644
index 0000000..4fd386f
--- /dev/null
+++ b/tests/application/test_approval_service.py
@@ -0,0 +1,65 @@
+"""Tests for ApprovalService."""
+
+import pytest
+
+from src.application.approval_service import ApprovalService
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import NoPreviousPromptError
+from src.domain.models import ApprovalStatus, Prompt
+
+
+def make_approval(runner, tracker, rate_limiter, session_store, history, notifier):
+    service = PromptService(
+        runner=runner,
+        tracker=tracker,
+        rate_limiter=rate_limiter,
+        session_store=session_store,
+        history=history,
+        notifier=notifier,
+    )
+    return ApprovalService(service, history)
+
+
+async def test_approve_reruns_with_auto_approve(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    await approval.approve(42)
+    prompt, _ = runner.calls[0]
+    assert prompt.text == "fix"
+    assert prompt.auto_approve is True
+
+
+async def test_retry_reruns_unchanged(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    await approval.retry(42)
+    prompt, _ = runner.calls[0]
+    assert prompt.text == "fix"
+    assert prompt.auto_approve is False
+
+
+async def test_reject_clears_history(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    status = await approval.reject(42)
+    assert status is ApprovalStatus.REJECTED
+    with pytest.raises(NoPreviousPromptError):
+        history.get(42)
+
+
+async def test_actions_without_previous_prompt_raise(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.approve(42)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.retry(42)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.reject(42)
diff --git a/tests/application/test_prompt_service.py b/tests/application/test_prompt_service.py
new file mode 100644
index 0000000..578371f
--- /dev/null
+++ b/tests/application/test_prompt_service.py
@@ -0,0 +1,111 @@
+"""Tests for PromptService."""
+
+import pytest
+
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import (
+    ExecutionBusyError,
+    NoActiveExecutionError,
+    PromptValidationError,
+    RateLimitError,
+)
+from src.domain.interfaces import RateLimiter
+from src.domain.models import Prompt
+
+
+def make_service(runner, tracker, rate_limiter, session_store, history, notifier):
+    return PromptService(
+        runner=runner,
+        tracker=tracker,
+        rate_limiter=rate_limiter,
+        session_store=session_store,
+        history=history,
+        notifier=notifier,
+    )
+
+
+async def test_execute_happy_path(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    response = await service.execute("fix the bug", user_id=42)
+    assert response.success is True
+    assert notifier.results[0][0].text == "fix the bug"
+    assert session_store.get(42) == "sess-1"
+    assert history.get(42).text == "fix the bug"
+    assert tracker.current() is None
+
+
+async def test_execute_resumes_stored_session(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    session_store.set(42, "old-session")
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    await service.execute("continue", user_id=42)
+    assert runner.calls[0][1] == "old-session"
+
+
+@pytest.mark.parametrize(
+    "text",
+    ["rm -rf /; echo", "a | b", "a && b", "`whoami`", "$(whoami)", "   "],
+)
+async def test_execute_rejects_dangerous_text(
+    text, runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(PromptValidationError):
+        await service.execute(text, user_id=42)
+    assert runner.calls == []
+
+
+async def test_execute_enforces_rate_limit(runner, tracker, session_store, history, notifier):
+    class BlockingLimiter(RateLimiter):
+        def check(self, user_id: int) -> None:
+            raise RateLimitError(5.0)
+
+    service = make_service(runner, tracker, BlockingLimiter(), session_store, history, notifier)
+    with pytest.raises(RateLimitError):
+        await service.execute("hello", user_id=42)
+    assert runner.calls == []
+
+
+async def test_execute_rejects_when_busy(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    tracker.try_start(Prompt(text="other", user_id=7))
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(ExecutionBusyError):
+        await service.execute("hello", user_id=42)
+    assert runner.calls == []
+
+
+async def test_cancel_without_execution_raises(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(NoActiveExecutionError):
+        await service.cancel()
+
+
+async def test_cancel_delegates_to_runner(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    tracker.try_start(Prompt(text="x", user_id=42))
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    await service.cancel()
+    assert runner.cancelled is True
+
+
+def test_clear_context(runner, tracker, rate_limiter, session_store, history, notifier):
+    session_store.set(42, "sess")
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    service.clear_context(42)
+    assert session_store.get(42) is None
+
+
+def test_context_percent(runner, tracker, rate_limiter, session_store, history, notifier):
+    runner.context = 12.5
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    assert service.context_percent(42) is None
+    session_store.set(42, "sess")
+    assert service.context_percent(42) == 12.5
diff --git a/tests/conftest.py b/tests/conftest.py
new file mode 100644
index 0000000..7b9f556
--- /dev/null
+++ b/tests/conftest.py
@@ -0,0 +1,93 @@
+"""Shared test fixtures and fakes."""
+
+from __future__ import annotations
+
+import pytest
+
+from src.application.prompt_history import PromptHistory
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    Notifier,
+    RateLimiter,
+    SessionStore,
+)
+from src.domain.models import Prompt, Response
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.session_store import InMemorySessionStore
+
+
+class FakeRunner(AgentRunner):
+    """Records run calls and returns a canned response."""
+
+    def __init__(self) -> None:
+        self.calls: list[tuple[Prompt, str | None]] = []
+        self.cancelled = False
+        self.context: float | None = None
+
+    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
+        self.calls.append((prompt, session_id))
+        return Response(
+            output="done",
+            success=True,
+            duration_seconds=0.1,
+            agent_name="fake",
+            session_id="sess-1",
+        )
+
+    async def cancel(self) -> None:
+        self.cancelled = True
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        return self.context
+
+
+class FakeNotifier(Notifier):
+    """Captures sent results and errors."""
+
+    def __init__(self) -> None:
+        self.results: list[tuple[Prompt, Response]] = []
+        self.errors: list[str] = []
+
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        self.results.append((prompt, response))
+
+    async def send_error(self, message: str) -> None:
+        self.errors.append(message)
+
+
+class AllowAllRateLimiter(RateLimiter):
+    """Never blocks."""
+
+    def check(self, user_id: int) -> None:
+        return None
+
+
+@pytest.fixture
+def runner() -> FakeRunner:
+    return FakeRunner()
+
+
+@pytest.fixture
+def notifier() -> FakeNotifier:
+    return FakeNotifier()
+
+
+@pytest.fixture
+def tracker() -> ExecutionTracker:
+    return InMemoryExecutionTracker()
+
+
+@pytest.fixture
+def session_store() -> SessionStore:
+    return InMemorySessionStore()
+
+
+@pytest.fixture
+def history() -> PromptHistory:
+    return PromptHistory()
+
+
+@pytest.fixture
+def rate_limiter() -> RateLimiter:
+    return AllowAllRateLimiter()
