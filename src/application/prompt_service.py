"""Use case: run a prompt against the coding agent and notify the result."""

from __future__ import annotations

import structlog

from src.application.prompt_history import PromptHistory
from src.domain.exceptions import (
    NoActiveExecutionError,
    PromptValidationError,
)
from src.domain.interfaces import (
    AgentRunner,
    ExecutionTracker,
    Notifier,
    RateLimiter,
    SessionStore,
)
from src.domain.models import Execution, Prompt, Response

logger = structlog.get_logger(__name__)


class PromptService:
    """Orchestrates validation, rate limiting, execution and notification."""

    FORBIDDEN_TOKENS: tuple[str, ...] = (";", "|", "&&", "`", "$(")

    def __init__(
        self,
        runner: AgentRunner,
        tracker: ExecutionTracker,
        rate_limiter: RateLimiter,
        session_store: SessionStore,
        history: PromptHistory,
        notifier: Notifier | None = None,
    ) -> None:
        self._runner = runner
        self._tracker = tracker
        self._rate_limiter = rate_limiter
        self._session_store = session_store
        self._history = history
        self._notifier = notifier

    async def execute(
        self,
        text: str,
        user_id: int,
        auto_approve: bool = False,
        context: str | None = None,
    ) -> Response:
        """Validate and run a prompt, then notify and store the result.

        Only `text` is validated; `context` is trusted system-generated
        content (e.g. a replied notification) prepended to the prompt.
        """
        self._validate(text)
        self._rate_limiter.check(user_id)
        full_text = f"Context:\n{context}\n\nInstruction: {text}" if context else text
        prompt = Prompt(text=full_text, user_id=user_id, auto_approve=auto_approve)
        self._tracker.try_start(prompt)
        try:
            session_id = self._session_store.get(user_id)
            response = await self._runner.run(prompt, session_id)
        finally:
            self._tracker.finish()
        if response.session_id:
            self._session_store.set(user_id, response.session_id)
        self._history.record(prompt)
        if self._notifier:
            await self._notifier.send_result(prompt, response)
        logger.info(
            "prompt_executed",
            user_id=user_id,
            success=response.success,
            duration=round(response.duration_seconds, 2),
        )
        return response

    def current_execution(self) -> Execution | None:
        """Return the active execution, if any."""
        return self._tracker.current()

    async def cancel(self) -> None:
        """Cancel the active execution.

        Raises:
            NoActiveExecutionError: if nothing is running.
        """
        if self._tracker.current() is None:
            raise NoActiveExecutionError("No active execution to cancel.")
        await self._runner.cancel()

    def clear_context(self, user_id: int) -> None:
        """Drop the user's session so the next prompt starts fresh."""
        self._session_store.clear(user_id)

    def context_percent(self, user_id: int) -> float | None:
        """Return the user's session context usage, or None if unknown."""
        session_id = self._session_store.get(user_id)
        if session_id is None:
            return None
        return self._runner.get_context_percent(session_id)

    def _validate(self, text: str) -> None:
        if not text.strip():
            raise PromptValidationError("The prompt cannot be empty.")
        found = [token for token in self.FORBIDDEN_TOKENS if token in text]
        if found:
            raise PromptValidationError(
                "The prompt contains forbidden characters: " + ", ".join(found)
            )
