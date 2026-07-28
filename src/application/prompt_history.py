"""In-memory history of the last prompt per user."""

from src.domain.exceptions import NoPreviousPromptError
from src.domain.models import Prompt


class PromptHistory:
    """Remembers the most recent prompt each user sent."""

    def __init__(self) -> None:
        self._last: dict[int, Prompt] = {}

    def record(self, prompt: Prompt) -> None:
        """Store prompt as the user's most recent one."""
        self._last[prompt.user_id] = prompt

    def get(self, user_id: int) -> Prompt:
        """Return the user's last prompt.

        Raises:
            NoPreviousPromptError: if the user has no recorded prompt.
        """
        try:
            return self._last[user_id]
        except KeyError as exc:
            raise NoPreviousPromptError("No previous prompt to act on.") from exc

    def clear(self, user_id: int) -> None:
        """Forget the user's last prompt, if any."""
        self._last.pop(user_id, None)
