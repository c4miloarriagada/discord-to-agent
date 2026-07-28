"""Ports (abstract interfaces) implemented by the infrastructure layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.models import Execution, PrComment, Prompt, Response


class AgentRunner(ABC):
    """Runs prompts against a coding agent."""

    @abstractmethod
    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
        """Execute a prompt, resuming session_id when provided."""

    @abstractmethod
    async def cancel(self) -> None:
        """Cancel the active execution, if any."""

    @abstractmethod
    def get_context_percent(self, session_id: str) -> float | None:
        """Return the session's context window usage, or None if unknown."""


class Notifier(ABC):
    """Delivers results and errors back to the user."""

    @abstractmethod
    async def send_result(self, prompt: Prompt, response: Response) -> None:
        """Send a run result."""

    @abstractmethod
    async def send_error(self, message: str) -> None:
        """Send a user-facing error message."""


class ExecutionTracker(ABC):
    """Tracks the single active execution."""

    @abstractmethod
    def try_start(self, prompt: Prompt) -> Execution:
        """Begin tracking a new execution.

        Raises:
            ExecutionBusyError: if another execution is active.
        """

    @abstractmethod
    def finish(self) -> None:
        """Mark the active execution as finished."""

    @abstractmethod
    def current(self) -> Execution | None:
        """Return the active execution, if any."""


class SessionStore(ABC):
    """Stores the current agent session id per user."""

    @abstractmethod
    def get(self, user_id: int) -> str | None:
        """Return the user's session id, if any."""

    @abstractmethod
    def set(self, user_id: int, session_id: str) -> None:
        """Store the user's session id."""

    @abstractmethod
    def clear(self, user_id: int) -> None:
        """Drop the user's session id."""


class RateLimiter(ABC):
    """Enforces a per-user cooldown between prompts."""

    @abstractmethod
    def check(self, user_id: int) -> None:
        """Raise RateLimitError if the user must wait."""


class PrCommentSource(ABC):
    """Fetches new pull request comments from a code hosting platform."""

    @abstractmethod
    async def fetch_new_comments(self, since: datetime) -> list[PrComment]:
        """Return comments created at or after `since`."""
