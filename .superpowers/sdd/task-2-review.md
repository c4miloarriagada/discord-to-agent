e4803e3 feat(domain): models, exceptions and ports

 src/domain/exceptions.py    | 37 +++++++++++++++++++++
 src/domain/interfaces.py    | 79 +++++++++++++++++++++++++++++++++++++++++++++
 src/domain/models.py        | 59 +++++++++++++++++++++++++++++++++
 tests/test_domain_models.py | 30 +++++++++++++++++
 4 files changed, 205 insertions(+)

diff --git a/src/domain/exceptions.py b/src/domain/exceptions.py
new file mode 100644
index 0000000..33e3877
--- /dev/null
+++ b/src/domain/exceptions.py
@@ -0,0 +1,37 @@
+"""Domain exceptions. All user-facing errors derive from BotError."""
+
+
+class BotError(Exception):
+    """Base class for all expected, user-facing bot errors."""
+
+
+class ConfigError(BotError):
+    """Invalid or missing configuration at startup."""
+
+
+class PromptValidationError(BotError):
+    """The prompt text failed safety validation."""
+
+
+class RateLimitError(BotError):
+    """The user is sending prompts too fast."""
+
+    def __init__(self, retry_after: float) -> None:
+        self.retry_after = retry_after
+        super().__init__(f"Rate limit: try again in {retry_after:.0f}s")
+
+
+class ExecutionBusyError(BotError):
+    """Another execution is already running."""
+
+
+class NoActiveExecutionError(BotError):
+    """No execution is currently running."""
+
+
+class NoPreviousPromptError(BotError):
+    """No earlier prompt exists for this user."""
+
+
+class RunnerError(BotError):
+    """The agent runner failed unexpectedly."""
diff --git a/src/domain/interfaces.py b/src/domain/interfaces.py
new file mode 100644
index 0000000..f14cc2a
--- /dev/null
+++ b/src/domain/interfaces.py
@@ -0,0 +1,79 @@
+"""Ports (abstract interfaces) implemented by the infrastructure layer."""
+
+from __future__ import annotations
+
+from abc import ABC, abstractmethod
+
+from src.domain.models import Execution, Prompt, Response
+
+
+class AgentRunner(ABC):
+    """Runs prompts against a coding agent."""
+
+    @abstractmethod
+    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
+        """Execute a prompt, resuming session_id when provided."""
+
+    @abstractmethod
+    async def cancel(self) -> None:
+        """Cancel the active execution, if any."""
+
+    @abstractmethod
+    def get_context_percent(self, session_id: str) -> float | None:
+        """Return the session's context window usage, or None if unknown."""
+
+
+class Notifier(ABC):
+    """Delivers results and errors back to the user."""
+
+    @abstractmethod
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        """Send a run result."""
+
+    @abstractmethod
+    async def send_error(self, message: str) -> None:
+        """Send a user-facing error message."""
+
+
+class ExecutionTracker(ABC):
+    """Tracks the single active execution."""
+
+    @abstractmethod
+    def try_start(self, prompt: Prompt) -> Execution:
+        """Begin tracking a new execution.
+
+        Raises:
+            ExecutionBusyError: if another execution is active.
+        """
+
+    @abstractmethod
+    def finish(self) -> None:
+        """Mark the active execution as finished."""
+
+    @abstractmethod
+    def current(self) -> Execution | None:
+        """Return the active execution, if any."""
+
+
+class SessionStore(ABC):
+    """Stores the current agent session id per user."""
+
+    @abstractmethod
+    def get(self, user_id: int) -> str | None:
+        """Return the user's session id, if any."""
+
+    @abstractmethod
+    def set(self, user_id: int, session_id: str) -> None:
+        """Store the user's session id."""
+
+    @abstractmethod
+    def clear(self, user_id: int) -> None:
+        """Drop the user's session id."""
+
+
+class RateLimiter(ABC):
+    """Enforces a per-user cooldown between prompts."""
+
+    @abstractmethod
+    def check(self, user_id: int) -> None:
+        """Raise RateLimitError if the user must wait."""
diff --git a/src/domain/models.py b/src/domain/models.py
new file mode 100644
index 0000000..212d600
--- /dev/null
+++ b/src/domain/models.py
@@ -0,0 +1,59 @@
+"""Core domain entities for the Discord agent bot."""
+
+from __future__ import annotations
+
+import time
+from dataclasses import dataclass, field
+from enum import Enum
+
+
+class ApprovalStatus(Enum):
+    """Lifecycle of a prompt's proposed changes."""
+
+    PENDING = "pending"
+    APPROVED = "approved"
+    REJECTED = "rejected"
+
+
+@dataclass(frozen=True)
+class Prompt:
+    """A user request to run against the coding agent."""
+
+    text: str
+    user_id: int
+    auto_approve: bool = False
+    created_at: float = field(default_factory=time.time)
+
+
+@dataclass(frozen=True)
+class Response:
+    """The result of running a prompt through an agent."""
+
+    output: str
+    success: bool
+    duration_seconds: float
+    timed_out: bool = False
+    agent_name: str = "agent"
+    session_id: str | None = None
+    context_percent: float | None = None
+
+
+@dataclass(frozen=True)
+class ParseResult:
+    """Structured data extracted from raw agent output."""
+
+    text: str
+    session_id: str | None = None
+
+
+@dataclass
+class Execution:
+    """Tracks the currently running execution (in-memory)."""
+
+    prompt: Prompt
+    started_at: float = field(default_factory=time.time)
+
+    @property
+    def elapsed_seconds(self) -> float:
+        """Seconds since the execution started."""
+        return time.time() - self.started_at
diff --git a/tests/test_domain_models.py b/tests/test_domain_models.py
new file mode 100644
index 0000000..9f1bd52
--- /dev/null
+++ b/tests/test_domain_models.py
@@ -0,0 +1,30 @@
+"""Tests for domain models."""
+
+import time
+
+from src.domain.models import ApprovalStatus, Execution, Prompt, Response
+
+
+def test_prompt_defaults():
+    prompt = Prompt(text="hello", user_id=42)
+    assert prompt.auto_approve is False
+    assert prompt.created_at <= time.time()
+
+
+def test_response_defaults():
+    response = Response(output="ok", success=True, duration_seconds=1.0)
+    assert response.timed_out is False
+    assert response.agent_name == "agent"
+    assert response.session_id is None
+    assert response.context_percent is None
+
+
+def test_execution_elapsed_seconds():
+    execution = Execution(prompt=Prompt(text="x", user_id=1), started_at=time.time() - 5)
+    assert 4.0 < execution.elapsed_seconds < 6.0
+
+
+def test_approval_status_values():
+    assert ApprovalStatus.PENDING.value == "pending"
+    assert ApprovalStatus.APPROVED.value == "approved"
+    assert ApprovalStatus.REJECTED.value == "rejected"
