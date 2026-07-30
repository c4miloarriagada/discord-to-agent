"""Session stores: in-memory and JSON-file backed."""

from __future__ import annotations

import json
import os
from pathlib import Path

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


class JsonSessionStore(SessionStore):
    """Persists per-user agent session ids in a JSON file.

    Survives bot/container restarts, so conversations keep their agent
    context across deploys. Writes are atomic (tmp file + rename).
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path).expanduser()

    def get(self, user_id: int) -> str | None:
        """Return the user's session id, if any."""
        return self._load().get(str(user_id))

    def set(self, user_id: int, session_id: str) -> None:
        """Store the user's session id and flush to disk."""
        data = self._load()
        data[str(user_id)] = session_id
        self._save(data)

    def clear(self, user_id: int) -> None:
        """Drop the user's session id and flush to disk."""
        data = self._load()
        if data.pop(str(user_id), None) is not None:
            self._save(data)

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self._path)

