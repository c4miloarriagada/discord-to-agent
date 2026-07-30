973c849 feat(infra): settings loading and validation

 src/infrastructure/config.py        | 57 +++++++++++++++++++++++++++++++++++++
 tests/infrastructure/test_config.py | 33 +++++++++++++++++++++
 2 files changed, 90 insertions(+)

diff --git a/src/infrastructure/config.py b/src/infrastructure/config.py
new file mode 100644
index 0000000..b3ba36f
--- /dev/null
+++ b/src/infrastructure/config.py
@@ -0,0 +1,57 @@
+"""Configuration loading and validation via environment variables."""
+
+from __future__ import annotations
+
+from typing import Annotated
+
+from pydantic import ValidationError, field_validator
+from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
+
+from src.domain.exceptions import ConfigError
+
+
+class Settings(BaseSettings):
+    """Bot settings loaded from environment variables or a .env file."""
+
+    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
+
+    discord_bot_token: str
+    # NoDecode keeps the raw env string so _split_ids can parse it;
+    # otherwise pydantic-settings tries to JSON-decode complex fields first.
+    allowed_channel_ids: Annotated[list[int], NoDecode] = []
+    allowed_user_ids: Annotated[list[int], NoDecode] = []
+    working_dir: str = "."
+    agent_type: str = "kimi"
+    kimi_command: str = "kimi"
+    kimi_auto_approve_flag: str = "--yolo"
+    kimi_sessions_dir: str = "~/.kimi-code/sessions"
+    kimi_context_window: int = 1048576
+    prompt_timeout: int = 300
+    rate_limit_seconds: int = 10
+    log_level: str = "INFO"
+
+    @field_validator("allowed_channel_ids", "allowed_user_ids", mode="before")
+    @classmethod
+    def _split_ids(cls, value: object) -> object:
+        """Parse comma-separated id lists from env vars."""
+        if isinstance(value, str):
+            return [int(v.strip()) for v in value.split(",") if v.strip()]
+        return value
+
+
+def load_settings() -> Settings:
+    """Load settings, failing fast with a clear message on misconfiguration.
+
+    Raises:
+        ConfigError: if required variables are missing or invalid.
+    """
+    try:
+        return Settings()  # type: ignore[call-arg]
+    except ValidationError as exc:
+        missing = {e["loc"][0] for e in exc.errors() if e["type"] == "missing"}
+        if "discord_bot_token" in missing:
+            raise ConfigError(
+                "DISCORD_BOT_TOKEN is not set. "
+                "Copy .env.example to .env and fill in your bot token."
+            ) from exc
+        raise ConfigError(f"Invalid configuration: {exc}") from exc
diff --git a/tests/infrastructure/test_config.py b/tests/infrastructure/test_config.py
new file mode 100644
index 0000000..2f85071
--- /dev/null
+++ b/tests/infrastructure/test_config.py
@@ -0,0 +1,33 @@
+"""Tests for configuration loading."""
+
+import pytest
+
+from src.domain.exceptions import ConfigError
+from src.infrastructure.config import load_settings
+
+
+def test_load_settings_fails_without_token(monkeypatch, tmp_path):
+    monkeypatch.chdir(tmp_path)
+    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
+    with pytest.raises(ConfigError, match="DISCORD_BOT_TOKEN"):
+        load_settings()
+
+
+def test_load_settings_parses_id_lists(monkeypatch, tmp_path):
+    monkeypatch.chdir(tmp_path)
+    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
+    monkeypatch.setenv("ALLOWED_CHANNEL_IDS", "123, 456")
+    monkeypatch.setenv("ALLOWED_USER_IDS", "7")
+    settings = load_settings()
+    assert settings.allowed_channel_ids == [123, 456]
+    assert settings.allowed_user_ids == [7]
+
+
+def test_load_settings_defaults(monkeypatch, tmp_path):
+    monkeypatch.chdir(tmp_path)
+    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
+    settings = load_settings()
+    assert settings.agent_type == "kimi"
+    assert settings.prompt_timeout == 300
+    assert settings.rate_limit_seconds == 10
+    assert settings.allowed_channel_ids == []
