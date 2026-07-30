### Task 3: Configuration (Settings + load_settings)

**Files:**
- Create: `src/infrastructure/config.py`
- Test: `tests/infrastructure/test_config.py`

**Interfaces:**
- Consumes: `src.domain.exceptions.ConfigError`.
- Produces: `Settings` (pydantic-settings) with fields `discord_bot_token: str`, `allowed_channel_ids: list[int]`, `allowed_user_ids: list[int]`, `working_dir: str = "."`, `agent_type: str = "kimi"`, `kimi_command: str = "kimi"`, `kimi_auto_approve_flag: str = "--yolo"`, `kimi_sessions_dir: str = "~/.kimi-code/sessions"`, `kimi_context_window: int = 1048576`, `prompt_timeout: int = 300`, `rate_limit_seconds: int = 10`, `log_level: str = "INFO"`; `load_settings() -> Settings` raising `ConfigError`.

- [ ] **Step 1: Write the failing test** — `tests/infrastructure/test_config.py`

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/infrastructure/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.infrastructure.config'`

- [ ] **Step 3: Write `src/infrastructure/config.py`**

```python
"""Configuration loading and validation via environment variables."""

from __future__ import annotations

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.domain.exceptions import ConfigError


class Settings(BaseSettings):
    """Bot settings loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_bot_token: str
    allowed_channel_ids: list[int] = []
    allowed_user_ids: list[int] = []
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/infrastructure/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/config.py tests/infrastructure/test_config.py
git commit -m "feat(infra): settings loading and validation"
```

---

