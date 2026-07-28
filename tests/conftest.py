"""Shared test fixtures and fakes."""

from __future__ import annotations

import pytest

from src.application.prompt_history import PromptHistory
from src.domain.interfaces import (
    AgentRunner,
    ExecutionTracker,
    Notifier,
    RateLimiter,
    SessionStore,
)
from src.domain.models import Prompt, Response
from src.infrastructure.execution_tracker import InMemoryExecutionTracker
from src.infrastructure.session_store import InMemorySessionStore


class FakeRunner(AgentRunner):
    """Records run calls and returns a canned response."""

    def __init__(self) -> None:
        self.calls: list[tuple[Prompt, str | None]] = []
        self.cancelled = False
        self.context: float | None = None

    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
        self.calls.append((prompt, session_id))
        return Response(
            output="done",
            success=True,
            duration_seconds=0.1,
            agent_name="fake",
            session_id="sess-1",
        )

    async def cancel(self) -> None:
        self.cancelled = True

    def get_context_percent(self, session_id: str) -> float | None:
        return self.context


class FakeNotifier(Notifier):
    """Captures sent results and errors."""

    def __init__(self) -> None:
        self.results: list[tuple[Prompt, Response]] = []
        self.errors: list[str] = []

    async def send_result(self, prompt: Prompt, response: Response) -> None:
        self.results.append((prompt, response))

    async def send_error(self, message: str) -> None:
        self.errors.append(message)


class AllowAllRateLimiter(RateLimiter):
    """Never blocks."""

    def check(self, user_id: int) -> None:
        return None


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def tracker() -> ExecutionTracker:
    return InMemoryExecutionTracker()


@pytest.fixture
def session_store() -> SessionStore:
    return InMemorySessionStore()


@pytest.fixture
def history() -> PromptHistory:
    return PromptHistory()


@pytest.fixture
def rate_limiter() -> RateLimiter:
    return AllowAllRateLimiter()
