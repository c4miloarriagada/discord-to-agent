"""Tests for the agent adapter registry."""

import pytest

from src.domain.exceptions import ConfigError
from src.infrastructure.agents.base import SubprocessAgentRunner
from src.infrastructure.agents.kimi import KimiAdapter
from src.infrastructure.agents.registry import create_agent_runner
from src.infrastructure.config import Settings


def make_settings(agent_type: str = "kimi") -> Settings:
    return Settings(discord_bot_token="x", agent_type=agent_type)


def test_create_runner_kimi():
    runner = create_agent_runner(make_settings())
    assert isinstance(runner, SubprocessAgentRunner)
    assert isinstance(runner._adapter, KimiAdapter)


def test_create_runner_unknown_type():
    with pytest.raises(ConfigError, match="Unknown AGENT_TYPE"):
        create_agent_runner(make_settings("gpt"))
