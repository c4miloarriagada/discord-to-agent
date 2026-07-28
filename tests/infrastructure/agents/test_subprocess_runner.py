"""Tests for SubprocessAgentRunner with a mocked subprocess."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import ParseResult, Prompt
from src.infrastructure.agents.base import AgentAdapter, SubprocessAgentRunner


class FakeAdapter(AgentAdapter):
    """Minimal adapter for runner tests."""

    @property
    def name(self) -> str:
        return "fake"

    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
        return ["fake-cli", prompt.text]


class SessionAdapter(FakeAdapter):
    """Adapter that reports a session id and context usage."""

    def parse_output(self, raw: str) -> ParseResult:
        return ParseResult(text=raw.strip(), session_id="sess-7")

    def get_context_percent(self, session_id: str) -> float | None:
        return 33.3 if session_id == "sess-7" else None


def make_process(returncode: int | None = 0, output: bytes = b"hello") -> MagicMock:
    process = MagicMock()
    process.returncode = returncode
    process.communicate = AsyncMock(return_value=(output, b""))
    process.wait = AsyncMock()
    process.pid = 99999  # mocked pid; killpg is patched to fail in kill tests
    return process


async def test_run_success():
    process = make_process()
    spawn = AsyncMock(return_value=process)
    with patch("asyncio.create_subprocess_exec", spawn):
        runner = SubprocessAgentRunner(FakeAdapter(), working_dir="/tmp", timeout_seconds=5)
        response = await runner.run(Prompt(text="hi", user_id=1))
    assert response.success is True
    assert response.output == "hello"
    assert response.agent_name == "fake"
    assert response.timed_out is False
    kwargs = spawn.call_args.kwargs
    assert kwargs["cwd"] == "/tmp"
    assert "shell" not in kwargs  # shell=False is the default; never enable it


async def test_run_nonzero_exit_is_failure():
    process = make_process(returncode=1, output=b"boom")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 5)
        response = await runner.run(Prompt(text="hi", user_id=1))
    assert response.success is False
    assert response.output == "boom"


async def test_run_timeout_kills_process():
    process = make_process(returncode=None)
    process.communicate = lambda: asyncio.sleep(60)
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        # killpg must not signal a real process group if pid 99999 happens to exist
        patch(
            "src.infrastructure.agents.base.os.killpg",
            side_effect=ProcessLookupError,
        ),
    ):
        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", timeout_seconds=1)
        response = await runner.run(Prompt(text="hi", user_id=1))
    assert response.timed_out is True
    assert response.success is False
    process.kill.assert_called()


async def test_cancel_kills_active_process():
    process = make_process(returncode=None)
    started = asyncio.Event()

    async def communicate():
        started.set()
        await asyncio.sleep(60)
        return b"", b""

    process.communicate = communicate
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        # killpg must not signal a real process group if pid 99999 happens to exist
        patch(
            "src.infrastructure.agents.base.os.killpg",
            side_effect=ProcessLookupError,
        ),
    ):
        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 60)
        task = asyncio.create_task(runner.run(Prompt(text="hi", user_id=1)))
        await started.wait()
        await runner.cancel()
        process.kill.assert_called()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_run_fills_session_and_context():
    process = make_process(output=b"text")
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        runner = SubprocessAgentRunner(SessionAdapter(), "/tmp", 5)
        response = await runner.run(Prompt(text="hi", user_id=1))
    assert response.session_id == "sess-7"
    assert response.context_percent == 33.3
