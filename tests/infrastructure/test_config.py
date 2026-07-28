"""Tests for configuration loading."""

import pytest

from src.domain.exceptions import ConfigError
from src.infrastructure.config import load_settings


def test_load_settings_fails_without_token(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="DISCORD_BOT_TOKEN"):
        load_settings()


def test_load_settings_parses_id_lists(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    monkeypatch.setenv("ALLOWED_CHANNEL_IDS", "123, 456")
    monkeypatch.setenv("ALLOWED_USER_IDS", "7")
    settings = load_settings()
    assert settings.allowed_channel_ids == [123, 456]
    assert settings.allowed_user_ids == [7]


def test_load_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    settings = load_settings()
    assert settings.agent_type == "kimi"
    assert settings.prompt_timeout == 300
    assert settings.rate_limit_seconds == 10
    assert settings.allowed_channel_ids == []
