"""Use case: resolve Approve / Reject / Retry button actions."""

from __future__ import annotations

from src.application.prompt_history import PromptHistory
from src.application.prompt_service import PromptService
from src.domain.models import ApprovalStatus, Response


class ApprovalService:
    """Handles user decisions on a prompt's result."""

    def __init__(self, prompt_service: PromptService, history: PromptHistory) -> None:
        self._prompt_service = prompt_service
        self._history = history

    async def approve(self, user_id: int) -> Response:
        """Re-run the user's last prompt with auto-approval enabled."""
        prompt = self._history.get(user_id)
        return await self._prompt_service.execute(prompt.text, user_id, auto_approve=True)

    async def retry(self, user_id: int) -> Response:
        """Re-run the user's last prompt unchanged."""
        prompt = self._history.get(user_id)
        return await self._prompt_service.execute(
            prompt.text, user_id, auto_approve=prompt.auto_approve
        )

    async def reject(self, user_id: int) -> ApprovalStatus:
        """Discard the user's last prompt."""
        self._history.get(user_id)  # raises if there is nothing to reject
        self._history.clear(user_id)
        return ApprovalStatus.REJECTED
