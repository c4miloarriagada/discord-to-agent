"""Core domain entities for the Discord agent bot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class ApprovalStatus(Enum):
    """Lifecycle of a prompt's proposed changes."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Prompt:
    """A user request to run against the coding agent."""

    text: str
    user_id: int
    auto_approve: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class Response:
    """The result of running a prompt through an agent."""

    output: str
    success: bool
    duration_seconds: float
    timed_out: bool = False
    agent_name: str = "agent"
    session_id: str | None = None
    context_percent: float | None = None


@dataclass(frozen=True)
class ParseResult:
    """Structured data extracted from raw agent output."""

    text: str
    session_id: str | None = None


@dataclass
class Execution:
    """Tracks the currently running execution (in-memory)."""

    prompt: Prompt
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since the execution started."""
        return time.time() - self.started_at
