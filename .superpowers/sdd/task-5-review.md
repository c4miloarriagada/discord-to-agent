4e9a61d feat(infra): agent plugin system with kimi adapter

 src/infrastructure/agents/base.py                  | 104 +++++++++++++++++++++
 src/infrastructure/agents/kimi.py                  | 101 ++++++++++++++++++++
 src/infrastructure/agents/registry.py              |  34 +++++++
 tests/infrastructure/agents/__init__.py            |   0
 tests/infrastructure/agents/test_kimi_adapter.py   |  70 ++++++++++++++
 tests/infrastructure/agents/test_registry.py       |  24 +++++
 .../agents/test_subprocess_runner.py               | 104 +++++++++++++++++++++
 7 files changed, 437 insertions(+)

diff --git a/src/infrastructure/agents/base.py b/src/infrastructure/agents/base.py
new file mode 100644
index 0000000..16589e9
--- /dev/null
+++ b/src/infrastructure/agents/base.py
@@ -0,0 +1,104 @@
+"""Agent plugin contract and shared subprocess runner."""
+
+from __future__ import annotations
+
+import asyncio
+import os
+import signal
+import time
+from abc import ABC, abstractmethod
+
+import structlog
+
+from src.domain.interfaces import AgentRunner
+from src.domain.models import ParseResult, Prompt, Response
+
+logger = structlog.get_logger(__name__)
+
+
+class AgentAdapter(ABC):
+    """Minimal contract to plug a coding agent into the bot."""
+
+    @property
+    @abstractmethod
+    def name(self) -> str:
+        """Human-readable agent name."""
+
+    @abstractmethod
+    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
+        """Return the full argv (no shell) to run the prompt."""
+
+    def parse_output(self, raw: str) -> ParseResult:
+        """Extract display text and session id from raw stdout."""
+        return ParseResult(text=raw.strip())
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        """Return context window usage for the session, or None."""
+        return None
+
+
+class SubprocessAgentRunner(AgentRunner):
+    """Runs an agent CLI as a one-shot subprocess with timeout and cancel."""
+
+    def __init__(self, adapter: AgentAdapter, working_dir: str, timeout_seconds: int) -> None:
+        self._adapter = adapter
+        self._working_dir = working_dir
+        self._timeout = timeout_seconds
+        self._process: asyncio.subprocess.Process | None = None
+
+    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
+        """Execute the prompt and capture the agent's output."""
+        argv = self._adapter.build_command(prompt, session_id)
+        started = time.monotonic()
+        self._process = await asyncio.create_subprocess_exec(
+            *argv,
+            cwd=self._working_dir,
+            stdout=asyncio.subprocess.PIPE,
+            stderr=asyncio.subprocess.STDOUT,
+            start_new_session=True,
+        )
+        try:
+            raw_bytes, _ = await asyncio.wait_for(
+                self._process.communicate(), timeout=self._timeout
+            )
+            timed_out = False
+        except asyncio.TimeoutError:
+            self._kill_process()
+            await self._process.wait()
+            raw_bytes, timed_out = b"", True
+        finally:
+            process = self._process
+            self._process = None
+        duration = time.monotonic() - started
+        parsed = self._adapter.parse_output(raw_bytes.decode(errors="replace"))
+        context = (
+            self._adapter.get_context_percent(parsed.session_id)
+            if parsed.session_id
+            else None
+        )
+        return Response(
+            output=parsed.text,
+            success=not timed_out and process.returncode == 0,
+            duration_seconds=duration,
+            timed_out=timed_out,
+            agent_name=self._adapter.name,
+            session_id=parsed.session_id,
+            context_percent=context,
+        )
+
+    async def cancel(self) -> None:
+        """Kill the active process, if any."""
+        self._kill_process()
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        """Delegate context usage lookup to the adapter."""
+        return self._adapter.get_context_percent(session_id)
+
+    def _kill_process(self) -> None:
+        if self._process is None or self._process.returncode is not None:
+            return
+        try:
+            os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
+        except (ProcessLookupError, PermissionError):
+            self._process.kill()
+        logger.info("agent_process_killed", pid=self._process.pid)
diff --git a/src/infrastructure/agents/kimi.py b/src/infrastructure/agents/kimi.py
new file mode 100644
index 0000000..e394a3b
--- /dev/null
+++ b/src/infrastructure/agents/kimi.py
@@ -0,0 +1,101 @@
+"""Kimi Code CLI adapter."""
+
+from __future__ import annotations
+
+import glob
+import json
+import os
+
+from src.domain.models import ParseResult, Prompt
+from src.infrastructure.agents.base import AgentAdapter
+from src.infrastructure.config import Settings
+
+
+class KimiAdapter(AgentAdapter):
+    """Plugin for the Kimi Code CLI (`kimi -p`)."""
+
+    def __init__(
+        self,
+        command: str = "kimi",
+        auto_approve_flag: str = "--yolo",
+        sessions_dir: str = "~/.kimi-code/sessions",
+        context_window: int = 1048576,
+    ) -> None:
+        self._command = command
+        self._auto_approve_flag = auto_approve_flag
+        self._sessions_dir = os.path.expanduser(sessions_dir)
+        self._context_window = context_window
+
+    @classmethod
+    def from_settings(cls, settings: Settings) -> "KimiAdapter":
+        """Build the adapter from application settings."""
+        return cls(
+            command=settings.kimi_command,
+            auto_approve_flag=settings.kimi_auto_approve_flag,
+            sessions_dir=settings.kimi_sessions_dir,
+            context_window=settings.kimi_context_window,
+        )
+
+    @property
+    def name(self) -> str:
+        return "kimi"
+
+    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
+        """Build the kimi CLI invocation for a one-shot prompt."""
+        argv = [self._command, "-p", prompt.text, "--output-format", "stream-json"]
+        if prompt.auto_approve:
+            argv.append(self._auto_approve_flag)
+        if session_id:
+            argv.extend(["-S", session_id])
+        return argv
+
+    def parse_output(self, raw: str) -> ParseResult:
+        """Parse stream-json lines into display text plus session id."""
+        texts: list[str] = []
+        session_id: str | None = None
+        for line in raw.splitlines():
+            try:
+                event = json.loads(line)
+            except json.JSONDecodeError:
+                continue
+            if event.get("role") == "assistant" and event.get("content"):
+                texts.append(str(event["content"]))
+            if event.get("type") == "session.resume_hint":
+                session_id = event.get("session_id", session_id)
+        if not texts and session_id is None:
+            return ParseResult(text=raw.strip())
+        return ParseResult(text="\n".join(texts).strip(), session_id=session_id)
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        """Compute context usage from the session's wire.jsonl, if available."""
+        wire = self._find_wire_log(session_id)
+        if wire is None:
+            return None
+        usage = self._last_usage(wire)
+        if usage is None:
+            return None
+        total = sum(usage.values())
+        return round(100.0 * total / self._context_window, 1)
+
+    def _find_wire_log(self, session_id: str) -> str | None:
+        pattern = os.path.join(
+            self._sessions_dir, "*", session_id, "agents", "main", "wire.jsonl"
+        )
+        matches = glob.glob(pattern)
+        return matches[0] if matches else None
+
+    @staticmethod
+    def _last_usage(wire_path: str) -> dict[str, int] | None:
+        usage: dict[str, int] | None = None
+        try:
+            with open(wire_path, encoding="utf-8") as handle:
+                for line in handle:
+                    try:
+                        event = json.loads(line)
+                    except json.JSONDecodeError:
+                        continue
+                    if event.get("type") == "usage.record":
+                        usage = event.get("usage", usage)
+        except OSError:
+            return None
+        return usage
diff --git a/src/infrastructure/agents/registry.py b/src/infrastructure/agents/registry.py
new file mode 100644
index 0000000..5d7c5f7
--- /dev/null
+++ b/src/infrastructure/agents/registry.py
@@ -0,0 +1,34 @@
+"""Registry of available agent adapters."""
+
+from __future__ import annotations
+
+from typing import Callable
+
+from src.domain.exceptions import ConfigError
+from src.domain.interfaces import AgentRunner
+from src.infrastructure.agents.base import AgentAdapter, SubprocessAgentRunner
+from src.infrastructure.agents.kimi import KimiAdapter
+from src.infrastructure.config import Settings
+
+AGENT_ADAPTERS: dict[str, Callable[[Settings], AgentAdapter]] = {
+    "kimi": KimiAdapter.from_settings,
+}
+
+
+def create_agent_runner(settings: Settings) -> AgentRunner:
+    """Build the configured agent runner.
+
+    Raises:
+        ConfigError: if settings.agent_type is not registered.
+    """
+    factory = AGENT_ADAPTERS.get(settings.agent_type)
+    if factory is None:
+        available = ", ".join(sorted(AGENT_ADAPTERS))
+        raise ConfigError(
+            f"Unknown AGENT_TYPE '{settings.agent_type}'. Available: {available}"
+        )
+    return SubprocessAgentRunner(
+        adapter=factory(settings),
+        working_dir=settings.working_dir,
+        timeout_seconds=settings.prompt_timeout,
+    )
diff --git a/tests/infrastructure/agents/__init__.py b/tests/infrastructure/agents/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/infrastructure/agents/test_kimi_adapter.py b/tests/infrastructure/agents/test_kimi_adapter.py
new file mode 100644
index 0000000..bc76e0b
--- /dev/null
+++ b/tests/infrastructure/agents/test_kimi_adapter.py
@@ -0,0 +1,70 @@
+"""Tests for the Kimi Code CLI adapter."""
+
+import json
+
+from src.domain.models import Prompt
+from src.infrastructure.agents.kimi import KimiAdapter
+
+
+def test_build_command_basic():
+    adapter = KimiAdapter()
+    argv = adapter.build_command(Prompt(text="hello", user_id=1), session_id=None)
+    assert argv == ["kimi", "-p", "hello", "--output-format", "stream-json"]
+
+
+def test_build_command_with_approve_and_session():
+    adapter = KimiAdapter(command="/usr/bin/kimi", auto_approve_flag="--auto")
+    argv = adapter.build_command(
+        Prompt(text="hi", user_id=1, auto_approve=True), session_id="sess-9"
+    )
+    assert argv == [
+        "/usr/bin/kimi", "-p", "hi", "--output-format", "stream-json", "--auto",
+        "-S", "sess-9",
+    ]
+
+
+def test_parse_output_stream_json():
+    raw = "\n".join(
+        [
+            json.dumps({"role": "assistant", "content": "Hello"}),
+            json.dumps({"role": "assistant", "content": "World"}),
+            json.dumps(
+                {"role": "meta", "type": "session.resume_hint", "session_id": "sess-1"}
+            ),
+        ]
+    )
+    result = KimiAdapter().parse_output(raw)
+    assert result.text == "Hello\nWorld"
+    assert result.session_id == "sess-1"
+
+
+def test_parse_output_fallback_plain_text():
+    result = KimiAdapter().parse_output("plain output\n")
+    assert result.text == "plain output"
+    assert result.session_id is None
+
+
+def test_get_context_percent(tmp_path):
+    wire = tmp_path / "wd_x" / "sess-1" / "agents" / "main" / "wire.jsonl"
+    wire.parent.mkdir(parents=True)
+    wire.write_text(
+        json.dumps(
+            {
+                "type": "usage.record",
+                "usage": {
+                    "inputOther": 50000,
+                    "output": 10000,
+                    "inputCacheRead": 40000,
+                    "inputCacheCreation": 0,
+                },
+            }
+        )
+        + "\n"
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
+
+
+def test_get_context_percent_missing_session(tmp_path):
+    adapter = KimiAdapter(sessions_dir=str(tmp_path))
+    assert adapter.get_context_percent("nope") is None
diff --git a/tests/infrastructure/agents/test_registry.py b/tests/infrastructure/agents/test_registry.py
new file mode 100644
index 0000000..7ae17f3
--- /dev/null
+++ b/tests/infrastructure/agents/test_registry.py
@@ -0,0 +1,24 @@
+"""Tests for the agent adapter registry."""
+
+import pytest
+
+from src.domain.exceptions import ConfigError
+from src.infrastructure.agents.base import SubprocessAgentRunner
+from src.infrastructure.agents.kimi import KimiAdapter
+from src.infrastructure.agents.registry import create_agent_runner
+from src.infrastructure.config import Settings
+
+
+def make_settings(agent_type: str = "kimi") -> Settings:
+    return Settings(discord_bot_token="x", agent_type=agent_type)
+
+
+def test_create_runner_kimi():
+    runner = create_agent_runner(make_settings())
+    assert isinstance(runner, SubprocessAgentRunner)
+    assert isinstance(runner._adapter, KimiAdapter)
+
+
+def test_create_runner_unknown_type():
+    with pytest.raises(ConfigError, match="Unknown AGENT_TYPE"):
+        create_agent_runner(make_settings("gpt"))
diff --git a/tests/infrastructure/agents/test_subprocess_runner.py b/tests/infrastructure/agents/test_subprocess_runner.py
new file mode 100644
index 0000000..c9affde
--- /dev/null
+++ b/tests/infrastructure/agents/test_subprocess_runner.py
@@ -0,0 +1,104 @@
+"""Tests for SubprocessAgentRunner with a mocked subprocess."""
+
+import asyncio
+from unittest.mock import AsyncMock, MagicMock, patch
+
+import pytest
+
+from src.domain.models import ParseResult, Prompt
+from src.infrastructure.agents.base import AgentAdapter, SubprocessAgentRunner
+
+
+class FakeAdapter(AgentAdapter):
+    """Minimal adapter for runner tests."""
+
+    @property
+    def name(self) -> str:
+        return "fake"
+
+    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
+        return ["fake-cli", prompt.text]
+
+
+class SessionAdapter(FakeAdapter):
+    """Adapter that reports a session id and context usage."""
+
+    def parse_output(self, raw: str) -> ParseResult:
+        return ParseResult(text=raw.strip(), session_id="sess-7")
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        return 33.3 if session_id == "sess-7" else None
+
+
+def make_process(returncode: int | None = 0, output: bytes = b"hello") -> MagicMock:
+    process = MagicMock()
+    process.returncode = returncode
+    process.communicate = AsyncMock(return_value=(output, b""))
+    process.wait = AsyncMock()
+    process.pid = 99999  # nonexistent pid: killpg falls back to process.kill()
+    return process
+
+
+async def test_run_success():
+    process = make_process()
+    spawn = AsyncMock(return_value=process)
+    with patch("asyncio.create_subprocess_exec", spawn):
+        runner = SubprocessAgentRunner(FakeAdapter(), working_dir="/tmp", timeout_seconds=5)
+        response = await runner.run(Prompt(text="hi", user_id=1))
+    assert response.success is True
+    assert response.output == "hello"
+    assert response.agent_name == "fake"
+    assert response.timed_out is False
+    kwargs = spawn.call_args.kwargs
+    assert kwargs["cwd"] == "/tmp"
+    assert "shell" not in kwargs  # shell=False is the default; never enable it
+
+
+async def test_run_nonzero_exit_is_failure():
+    process = make_process(returncode=1, output=b"boom")
+    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 5)
+        response = await runner.run(Prompt(text="hi", user_id=1))
+    assert response.success is False
+    assert response.output == "boom"
+
+
+async def test_run_timeout_kills_process():
+    process = make_process(returncode=None)
+    process.communicate = lambda: asyncio.sleep(60)
+    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", timeout_seconds=1)
+        response = await runner.run(Prompt(text="hi", user_id=1))
+    assert response.timed_out is True
+    assert response.success is False
+    process.kill.assert_called()
+
+
+async def test_cancel_kills_active_process():
+    process = make_process(returncode=None)
+    started = asyncio.Event()
+
+    async def communicate():
+        started.set()
+        await asyncio.sleep(60)
+        return b"", b""
+
+    process.communicate = communicate
+    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+        runner = SubprocessAgentRunner(FakeAdapter(), "/tmp", 60)
+        task = asyncio.create_task(runner.run(Prompt(text="hi", user_id=1)))
+        await started.wait()
+        await runner.cancel()
+        process.kill.assert_called()
+    task.cancel()
+    with pytest.raises(asyncio.CancelledError):
+        await task
+
+
+async def test_run_fills_session_and_context():
+    process = make_process(output=b"text")
+    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
+        runner = SubprocessAgentRunner(SessionAdapter(), "/tmp", 5)
+        response = await runner.run(Prompt(text="hi", user_id=1))
+    assert response.session_id == "sess-7"
+    assert response.context_percent == 33.3
