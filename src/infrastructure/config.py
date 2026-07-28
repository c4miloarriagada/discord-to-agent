"""Configuration loading and validation via environment variables."""

from __future__ import annotations

from typing import Annotated

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from src.domain.exceptions import ConfigError


class Settings(BaseSettings):
    """Bot settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_bot_token: str
    # NoDecode keeps the raw env string so _split_ids can parse it;
    # otherwise pydantic-settings tries to JSON-decode complex fields first.
    allowed_channel_ids: Annotated[list[int], NoDecode] = []
    allowed_user_ids: Annotated[list[int], NoDecode] = []
    working_dir: str = "."
    agent_type: str = "kimi"
    kimi_command: str = "kimi"
    kimi_auto_approve_flag: str = "--yolo"
    kimi_sessions_dir: str = "~/.kimi-code/sessions"
    kimi_context_window: int = 1048576
    prompt_timeout: int = 300
    rate_limit_seconds: int = 10
    log_level: str = "INFO"

    @field_validator("allowed_channel_ids", "allowed_user_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        """Parse comma-separated id lists from env vars."""
        if isinstance(value, str):
            return [int(v.strip()) for v in value.split(",") if v.strip()]
        return value


def load_settings() -> Settings:
    """Load settings, failing fast with a clear message on misconfiguration.

    Raises:
        ConfigError: if required variables are missing or invalid.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = {e["loc"][0] for e in exc.errors() if e["type"] == "missing"}
        if "discord_bot_token" in missing:
            raise ConfigError(
                "DISCORD_BOT_TOKEN is not set. "
                "Copy .env.example to .env and fill in your bot token."
            ) from exc
        raise ConfigError(f"Invalid configuration: {exc}") from exc
