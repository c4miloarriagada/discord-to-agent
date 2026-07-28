"""Tests for domain models."""

import time

from src.domain.models import ApprovalStatus, Execution, Prompt, Response


def test_prompt_defaults():
    prompt = Prompt(text="hello", user_id=42)
    assert prompt.auto_approve is False
    assert prompt.created_at <= time.time()


def test_response_defaults():
    response = Response(output="ok", success=True, duration_seconds=1.0)
    assert response.timed_out is False
    assert response.agent_name == "agent"
    assert response.session_id is None
    assert response.context_percent is None


def test_execution_elapsed_seconds():
    execution = Execution(prompt=Prompt(text="x", user_id=1), started_at=time.time() - 5)
    assert 4.0 < execution.elapsed_seconds < 6.0


def test_approval_status_values():
    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"
