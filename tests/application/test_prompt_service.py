"""Tests for PromptService."""

import pytest

from src.application.prompt_service import PromptService
from src.domain.exceptions import (
    ExecutionBusyError,
    NoActiveExecutionError,
    PromptValidationError,
    RateLimitError,
)
from src.domain.interfaces import RateLimiter
from src.domain.models import Prompt


def make_service(runner, tracker, rate_limiter, session_store, history, notifier):
    return PromptService(
        runner=runner,
        tracker=tracker,
        rate_limiter=rate_limiter,
        session_store=session_store,
        history=history,
        notifier=notifier,
    )


async def test_execute_happy_path(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    response = await service.execute("fix the bug", user_id=42)
    assert response.success is True
    assert notifier.results[0][0].text == "fix the bug"
    assert session_store.get(42) == "sess-1"
    assert history.get(42).text == "fix the bug"
    assert tracker.current() is None


async def test_execute_resumes_stored_session(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    session_store.set(42, "old-session")
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    await service.execute("continue", user_id=42)
    assert runner.calls[0][1] == "old-session"


@pytest.mark.parametrize(
    "text",
    ["rm -rf /; echo", "a | b", "a && b", "`whoami`", "$(whoami)", "   "],
)
async def test_execute_rejects_dangerous_text(
    text, runner, tracker, rate_limiter, session_store, history, notifier
):
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    with pytest.raises(PromptValidationError):
        await service.execute(text, user_id=42)
    assert runner.calls == []


async def test_execute_enforces_rate_limit(runner, tracker, session_store, history, notifier):
    class BlockingLimiter(RateLimiter):
        def check(self, user_id: int) -> None:
            raise RateLimitError(5.0)

    service = make_service(runner, tracker, BlockingLimiter(), session_store, history, notifier)
    with pytest.raises(RateLimitError):
        await service.execute("hello", user_id=42)
    assert runner.calls == []


async def test_execute_rejects_when_busy(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    tracker.try_start(Prompt(text="other", user_id=7))
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    with pytest.raises(ExecutionBusyError):
        await service.execute("hello", user_id=42)
    assert runner.calls == []


async def test_cancel_without_execution_raises(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    with pytest.raises(NoActiveExecutionError):
        await service.cancel()


async def test_cancel_delegates_to_runner(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    tracker.try_start(Prompt(text="x", user_id=42))
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    await service.cancel()
    assert runner.cancelled is True


def test_clear_context(runner, tracker, rate_limiter, session_store, history, notifier):
    session_store.set(42, "sess")
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    service.clear_context(42)
    assert session_store.get(42) is None


def test_context_percent(runner, tracker, rate_limiter, session_store, history, notifier):
    runner.context = 12.5
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    assert service.context_percent(42) is None
    session_store.set(42, "sess")
    assert service.context_percent(42) == 12.5


async def test_execute_with_context_validates_only_text(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    # Context may contain backticks/semicolons (PR comments do); text may not.
    await service.execute(
        "apply this", user_id=42, context="review: change `foo();` please"
    )
    prompt, _ = runner.calls[0]
    assert "Context:\nreview: change `foo();` please" in prompt.text
    assert "Instruction: apply this" in prompt.text


async def test_execute_with_context_still_rejects_dangerous_text(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
    with pytest.raises(PromptValidationError):
        await service.execute("bad; text", user_id=42, context="safe context")
    assert runner.calls == []
