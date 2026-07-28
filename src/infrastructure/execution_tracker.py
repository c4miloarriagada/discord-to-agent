"""In-memory single-execution tracker."""

from src.domain.exceptions import ExecutionBusyError
from src.domain.interfaces import ExecutionTracker
from src.domain.models import Execution, Prompt


class InMemoryExecutionTracker(ExecutionTracker):
    """Allows exactly one active execution at a time."""

    def __init__(self) -> None:
        self._current: Execution | None = None

    def try_start(self, prompt: Prompt) -> Execution:
        """Start tracking; raise ExecutionBusyError when busy."""
        if self._current is not None:
            raise ExecutionBusyError(
                "An execution is already running. Use /status or /cancel."
            )
        self._current = Execution(prompt=prompt)
        return self._current

    def finish(self) -> None:
        """Clear the active execution."""
        self._current = None

    def current(self) -> Execution | None:
        """Return the active execution, if any."""
        return self._current
