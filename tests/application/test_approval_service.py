"""Tests for ApprovalService."""

import pytest

from src.application.approval_service import ApprovalService
from src.application.prompt_service import PromptService
from src.domain.exceptions import NoPreviousPromptError
from src.domain.models import ApprovalStatus, Prompt


def make_approval(runner, tracker, rate_limiter, session_store, history, notifier):
    service = PromptService(
        runner=runner,
        tracker=tracker,
        rate_limiter=rate_limiter,
        session_store=session_store,
        history=history,
        notifier=notifier,
    )
    return ApprovalService(service, history)


async def test_approve_reruns_with_auto_approve(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    history.record(Prompt(text="fix", user_id=42))
    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
    await approval.approve(42)
    prompt, _ = runner.calls[0]
    assert prompt.text == "fix"
    assert prompt.auto_approve is True


async def test_retry_reruns_unchanged(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    history.record(Prompt(text="fix", user_id=42))
    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
    await approval.retry(42)
    prompt, _ = runner.calls[0]
    assert prompt.text == "fix"
    assert prompt.auto_approve is False


async def test_reject_clears_history(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    history.record(Prompt(text="fix", user_id=42))
    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
    status = await approval.reject(42)
    assert status is ApprovalStatus.REJECTED
    with pytest.raises(NoPreviousPromptError):
        history.get(42)


async def test_actions_without_previous_prompt_raise(
    runner, tracker, rate_limiter, session_store, history, notifier
):
    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
    with pytest.raises(NoPreviousPromptError):
        await approval.approve(42)
    with pytest.raises(NoPreviousPromptError):
        await approval.retry(42)
    with pytest.raises(NoPreviousPromptError):
        await approval.reject(42)
