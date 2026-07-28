"""Kimi Code CLI adapter."""

from __future__ import annotations

import glob
import json
import os

from src.domain.models import ParseResult, Prompt
from src.infrastructure.agents.base import AgentAdapter
from src.infrastructure.config import Settings


class KimiAdapter(AgentAdapter):
    """Plugin for the Kimi Code CLI (`kimi -p`)."""

    def __init__(
        self,
        command: str = "kimi",
        auto_approve_flag: str = "--yolo",
        sessions_dir: str = "~/.kimi-code/sessions",
        context_window: int = 1048576,
    ) -> None:
        self._command = command
        self._auto_approve_flag = auto_approve_flag
        self._sessions_dir = os.path.expanduser(sessions_dir)
        self._context_window = context_window

    @classmethod
    def from_settings(cls, settings: Settings) -> "KimiAdapter":
        """Build the adapter from application settings."""
        return cls(
            command=settings.kimi_command,
            auto_approve_flag=settings.kimi_auto_approve_flag,
            sessions_dir=settings.kimi_sessions_dir,
            context_window=settings.kimi_context_window,
        )

    @property
    def name(self) -> str:
        return "kimi"

    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
        """Build the kimi CLI invocation for a one-shot prompt."""
        argv = [self._command, "-p", prompt.text, "--output-format", "stream-json"]
        if prompt.auto_approve:
            argv.append(self._auto_approve_flag)
        if session_id:
            argv.extend(["-S", session_id])
        return argv

    def parse_output(self, raw: str) -> ParseResult:
        """Parse stream-json lines into display text plus session id."""
        texts: list[str] = []
        session_id: str | None = None
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("role") == "assistant" and event.get("content"):
                texts.append(str(event["content"]))
            if event.get("type") == "session.resume_hint":
                session_id = event.get("session_id", session_id)
        if not texts and session_id is None:
            return ParseResult(text=raw.strip())
        return ParseResult(text="\n".join(texts).strip(), session_id=session_id)

    def get_context_percent(self, session_id: str) -> float | None:
        """Compute context usage from the session's wire.jsonl, if available."""
        wire = self._find_wire_log(session_id)
        if wire is None:
            return None
        usage = self._last_usage(wire)
        if usage is None:
            return None
        total = sum(v for v in usage.values() if isinstance(v, (int, float)))
        return round(100.0 * total / self._context_window, 1)

    def _find_wire_log(self, session_id: str) -> str | None:
        pattern = os.path.join(
            self._sessions_dir, "*", session_id, "agents", "main", "wire.jsonl"
        )
        matches = glob.glob(pattern)
        return matches[0] if matches else None

    @staticmethod
    def _last_usage(wire_path: str) -> dict[str, int] | None:
        usage: dict[str, int] | None = None
        try:
            with open(wire_path, encoding="utf-8") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("type") == "usage.record":
                        candidate = event.get("usage")
                        if isinstance(candidate, dict):
                            usage = candidate
        except OSError:
            return None
        return usage
