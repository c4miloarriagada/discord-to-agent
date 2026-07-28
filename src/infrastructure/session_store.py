"""In-memory session store."""

from src.domain.interfaces import SessionStore


class InMemorySessionStore(SessionStore):
    """Keeps the current agent session id per user (volatile)."""

    def __init__(self) -> None:
        self._sessions: dict[int, str] = {}

    def get(self, user_id: int) -> str | None:
        """Return the user's session id, if any."""
        return self._sessions.get(user_id)

    def set(self, user_id: int, session_id: str) -> None:
        """Store the user's session id."""
        self._sessions[user_id] = session_id

    def clear(self, user_id: int) -> None:
        """Drop the user's session id."""
        self._sessions.pop(user_id, None)
