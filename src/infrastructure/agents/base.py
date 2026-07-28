"""Agent plugin contract and shared subprocess runner."""

from __future__ import annotations

import asyncio
import os
import signal
import time
from abc import ABC, abstractmethod

import structlog

from src.domain.interfaces import AgentRunner
from src.domain.models import ParseResult, Prompt, Response

logger = structlog.get_logger(__name__)


class AgentAdapter(ABC):
    """Minimal contract to plug a coding agent into the bot."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""

    @abstractmethod
    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
        """Return the full argv (no shell) to run the prompt."""

    def parse_output(self, raw: str) -> ParseResult:
        """Extract display text and session id from raw stdout."""
        return ParseResult(text=raw.strip())

    def get_context_percent(self, session_id: str) -> float | None:
        """Return context window usage for the session, or None."""
        return None


class SubprocessAgentRunner(AgentRunner):
    """Runs an agent CLI as a one-shot subprocess with timeout and cancel."""

    def __init__(self, adapter: AgentAdapter, working_dir: str, timeout_seconds: int) -> None:
        self._adapter = adapter
        self._working_dir = working_dir
        self._timeout = timeout_seconds
        self._process: asyncio.subprocess.Process | None = None

    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
        """Execute the prompt and capture the agent's output."""
        argv = self._adapter.build_command(prompt, session_id)
        started = time.monotonic()
        self._process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=self._working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            raw_bytes, _ = await asyncio.wait_for(
                self._process.communicate(), timeout=self._timeout
            )
            timed_out = False
        except asyncio.TimeoutError:
            self._kill_process()
            await self._process.wait()
            raw_bytes, timed_out = b"", True
        finally:
            process = self._process
            self._process = None
        duration = time.monotonic() - started
        parsed = self._adapter.parse_output(raw_bytes.decode(errors="replace"))
        context = (
            self._adapter.get_context_percent(parsed.session_id)
            if parsed.session_id
            else None
        )
        return Response(
            output=parsed.text,
            success=not timed_out and process.returncode == 0,
            duration_seconds=duration,
            timed_out=timed_out,
            agent_name=self._adapter.name,
            session_id=parsed.session_id,
            context_percent=context,
        )

    async def cancel(self) -> None:
        """Kill the active process, if any."""
        self._kill_process()

    def get_context_percent(self, session_id: str) -> float | None:
        """Delegate context usage lookup to the adapter."""
        return self._adapter.get_context_percent(session_id)

    def _kill_process(self) -> None:
        if self._process is None or self._process.returncode is not None:
            return
        try:
            os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            self._process.kill()
        logger.info("agent_process_killed", pid=self._process.pid)
