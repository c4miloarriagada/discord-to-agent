"""Domain exceptions. All user-facing errors derive from BotError."""


class BotError(Exception):
    """Base class for all expected, user-facing bot errors."""


class ConfigError(BotError):
    """Invalid or missing configuration at startup."""


class PromptValidationError(BotError):
    """The prompt text failed safety validation."""


class RateLimitError(BotError):
    """The user is sending prompts too fast."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit: try again in {retry_after:.0f}s")


class ExecutionBusyError(BotError):
    """Another execution is already running."""


class NoActiveExecutionError(BotError):
    """No execution is currently running."""


class NoPreviousPromptError(BotError):
    """No earlier prompt exists for this user."""


class RunnerError(BotError):
    """The agent runner failed unexpectedly."""
