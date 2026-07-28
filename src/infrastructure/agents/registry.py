"""Registry of available agent adapters."""

from __future__ import annotations

from typing import Callable

from src.domain.exceptions import ConfigError
from src.domain.interfaces import AgentRunner
from src.infrastructure.agents.base import AgentAdapter, SubprocessAgentRunner
from src.infrastructure.agents.kimi import KimiAdapter
from src.infrastructure.config import Settings

AGENT_ADAPTERS: dict[str, Callable[[Settings], AgentAdapter]] = {
    "kimi": KimiAdapter.from_settings,
}


def create_agent_runner(settings: Settings) -> AgentRunner:
    """Build the configured agent runner.

    Raises:
        ConfigError: if settings.agent_type is not registered.
    """
    factory = AGENT_ADAPTERS.get(settings.agent_type)
    if factory is None:
        available = ", ".join(sorted(AGENT_ADAPTERS))
        raise ConfigError(
            f"Unknown AGENT_TYPE '{settings.agent_type}'. Available: {available}"
        )
    return SubprocessAgentRunner(
        adapter=factory(settings),
        working_dir=settings.working_dir,
        timeout_seconds=settings.prompt_timeout,
    )
