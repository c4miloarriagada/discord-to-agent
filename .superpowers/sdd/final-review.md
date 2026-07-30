61a1b0b feat: docker packaging and readme
7d928d6 fix(interface): remove unused import, hint action callback
b6334b8 feat(interface): slash commands, approval buttons, message listener
0686f2c feat(infra): discord notifier with embed and file helpers
913fe80 feat(app): prompt and approval services with history
3956899 fix(infra): guard non-dict JSON in kimi adapter, safe pid mocking in runner tests
4e9a61d feat(infra): agent plugin system with kimi adapter
3e3b81f feat(infra): in-memory rate limiter, session store, execution tracker
973c849 feat(infra): settings loading and validation
e4803e3 feat(domain): models, exceptions and ports
b016b85 chore: project scaffolding

 .env.example                                       |  12 ++
 .gitignore                                         |  12 ++
 Dockerfile                                         |  14 ++
 Makefile                                           |  16 ++
 README.md                                          | 195 +++++++++++++++++++++
 docker-compose.yml                                 |  10 ++
 pytest.ini                                         |   4 +
 requirements.txt                                   |   9 +
 src/__init__.py                                    |   0
 src/application/__init__.py                        |   0
 src/application/approval_service.py                |  33 ++++
 src/application/prompt_history.py                  |  30 ++++
 src/application/prompt_service.py                  | 101 +++++++++++
 src/domain/__init__.py                             |   0
 src/domain/exceptions.py                           |  37 ++++
 src/domain/interfaces.py                           |  79 +++++++++
 src/domain/models.py                               |  59 +++++++
 src/infrastructure/__init__.py                     |   0
 src/infrastructure/agents/__init__.py              |   0
 src/infrastructure/agents/base.py                  | 104 +++++++++++
 src/infrastructure/agents/kimi.py                  | 107 +++++++++++
 src/infrastructure/agents/registry.py              |  34 ++++
 src/infrastructure/config.py                       |  57 ++++++
 src/infrastructure/discord_adapter.py              | 100 +++++++++++
 src/infrastructure/execution_tracker.py            |  29 +++
 src/infrastructure/rate_limiter.py                 |  28 +++
 src/infrastructure/session_store.py                |  22 +++
 src/interface/__init__.py                          |   0
 src/interface/bot.py                               | 125 +++++++++++++
 src/interface/commands.py                          | 156 +++++++++++++++++
 src/interface/components.py                        |  77 ++++++++
 tests/__init__.py                                  |   0
 tests/application/__init__.py                      |   0
 tests/application/test_approval_service.py         |  65 +++++++
 tests/application/test_prompt_service.py           | 111 ++++++++++++
 tests/conftest.py                                  |  93 ++++++++++
 tests/infrastructure/__init__.py                   |   0
 tests/infrastructure/agents/__init__.py            |   0
 tests/infrastructure/agents/test_kimi_adapter.py   | 136 ++++++++++++++
 tests/infrastructure/agents/test_registry.py       |  24 +++
 .../agents/test_subprocess_runner.py               | 118 +++++++++++++
 tests/infrastructure/test_config.py                |  33 ++++
 tests/infrastructure/test_discord_adapter.py       |  58 ++++++
 tests/infrastructure/test_state_adapters.py        |  54 ++++++
 tests/interface/__init__.py                        |   0
 tests/interface/test_bot_text.py                   |  61 +++++++
 tests/interface/test_commands_guards.py            |  28 +++
 tests/interface/test_components.py                 |  24 +++
 tests/test_domain_models.py                        |  30 ++++
 49 files changed, 2285 insertions(+)

diff --git a/.env.example b/.env.example
new file mode 100644
index 0000000..413d6b8
--- /dev/null
+++ b/.env.example
@@ -0,0 +1,12 @@
+DISCORD_BOT_TOKEN=your_bot_token_here
+ALLOWED_CHANNEL_IDS=123456789,987654321
+ALLOWED_USER_IDS=
+WORKING_DIR=/home/user/projects
+AGENT_TYPE=kimi
+KIMI_COMMAND=kimi
+KIMI_AUTO_APPROVE_FLAG=--yolo
+KIMI_SESSIONS_DIR=~/.kimi-code/sessions
+KIMI_CONTEXT_WINDOW=1048576
+PROMPT_TIMEOUT=300
+RATE_LIMIT_SECONDS=10
+LOG_LEVEL=INFO
diff --git a/.gitignore b/.gitignore
new file mode 100644
index 0000000..ee414c5
--- /dev/null
+++ b/.gitignore
@@ -0,0 +1,12 @@
+.env
+__pycache__/
+*.py[cod]
+.venv/
+venv/
+.pytest_cache/
+.coverage
+htmlcov/
+.ruff_cache/
+*.egg-info/
+dist/
+build/
diff --git a/Dockerfile b/Dockerfile
new file mode 100644
index 0000000..1a616e6
--- /dev/null
+++ b/Dockerfile
@@ -0,0 +1,14 @@
+# syntax=docker/dockerfile:1
+FROM python:3.11-slim AS builder
+WORKDIR /app
+COPY requirements.txt .
+RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
+
+FROM python:3.11-slim
+WORKDIR /app
+COPY --from=builder /install /usr/local
+COPY src/ ./src/
+# The agent CLI is provided by mounting the host's agent home dir (see docker-compose.yml).
+ENV PATH="/root/.kimi-code/bin:${PATH}"
+ENV PYTHONUNBUFFERED=1
+CMD ["python", "-m", "src.interface.bot"]
diff --git a/Makefile b/Makefile
new file mode 100644
index 0000000..894f78d
--- /dev/null
+++ b/Makefile
@@ -0,0 +1,16 @@
+.PHONY: install test coverage run lint
+
+install:
+	pip install -r requirements.txt
+
+test:
+	pytest
+
+coverage:
+	pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60
+
+run:
+	python -m src.interface.bot
+
+lint:
+	ruff check src tests
diff --git a/README.md b/README.md
new file mode 100644
index 0000000..fb34b3d
--- /dev/null
+++ b/README.md
@@ -0,0 +1,195 @@
+# Discord Agent Bot
+
+A Discord bot that drives a pluggable coding-agent CLI (Kimi Code first) from your phone or desktop: slash commands to send prompts, approval buttons on every result, session context tracking, and bidirectional messaging — mentions, DMs, and thread replies all act as prompts.
+
+## Features
+
+- Slash commands: `/prompt`, `/status`, `/cancel`, `/clear`
+- Approve ✅ / Reject ❌ / Retry 🔄 buttons on every result
+- Session resume with context-window usage % in every result footer
+- Mentions, DMs, and replies to bot results all act as prompts
+- Result messages @mention you so you get a push notification
+- Long outputs are attached as `output.md` files
+- Plugin architecture — switch agent CLIs with `AGENT_TYPE`
+- Security: prompt sanitization, per-user rate limiting, channel/user allowlists, subprocess timeouts, no shell (`exec` argv only)
+
+## Project structure
+
+```
+├── src/
+│   ├── domain/              # Entities, exceptions, interfaces (ports)
+│   │   ├── models.py        # Prompt, Response, ApprovalStatus, Execution, ParseResult
+│   │   ├── interfaces.py    # ABCs: AgentRunner, Notifier, ExecutionTracker, SessionStore, RateLimiter
+│   │   └── exceptions.py    # BotError hierarchy
+│   ├── application/         # Use cases (pure business logic)
+│   │   ├── prompt_service.py   # Receive prompt → validate → run → notify; status/cancel/clear
+│   │   ├── approval_service.py # Approve / Reject / Retry
+│   │   └── prompt_history.py   # Last prompt per user (in-memory)
+│   ├── infrastructure/      # Adapters
+│   │   ├── agents/             # Agent plugin system
+│   │   │   ├── base.py         # AgentAdapter (ABC) + SubprocessAgentRunner (shared logic)
+│   │   │   ├── kimi.py         # KimiAdapter (first plugin)
+│   │   │   └── registry.py     # AGENT_ADAPTERS + create_agent_runner(settings)
+│   │   ├── discord_adapter.py  # Notifier with discord.py (Embeds, file attachments, mentions)
+│   │   ├── config.py           # Settings with pydantic-settings
+│   │   ├── rate_limiter.py     # Per-user cooldown (in-memory)
+│   │   ├── session_store.py    # InMemorySessionStore
+│   │   └── execution_tracker.py# InMemoryExecutionTracker
+│   └── interface/           # Entry point and Discord handlers
+│       ├── bot.py             # create_bot(): intents, command sync, on_message listener
+│       ├── commands.py        # /prompt /status /cancel /clear + shared prompt flow
+│       └── components.py      # ApprovalView with buttons
+├── tests/
+├── docs/superpowers/specs/
+├── .env.example
+├── Dockerfile
+├── docker-compose.yml
+├── Makefile
+├── requirements.txt
+└── README.md
+```
+
+## Prerequisites
+
+- Python 3.11+
+- A Discord application/bot (see next section)
+- The agent CLI installed and authenticated (e.g. `kimi` — verify with `kimi doctor` or `kimi -p "hi"`)
+
+## Create the Discord bot
+
+1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
+2. Open **Bot** → **Reset Token** → copy the token (you'll put it in `.env`).
+3. Still under **Bot**, enable the **Message Content** privileged intent — required for mentions, DMs, and replies to work.
+4. Go to **OAuth2 → URL Generator**:
+   - Scopes: `bot` + `applications.commands`
+   - Bot permissions: Send Messages, Embed Links, Attach Files, Read Message History
+5. Open the generated URL to invite the bot to your server.
+
+## Configuration
+
+```bash
+cp .env.example .env
+```
+
+| Variable | Default | Description |
+|---|---|---|
+| `DISCORD_BOT_TOKEN` | *(required)* | Bot token from the Developer Portal |
+| `ALLOWED_CHANNEL_IDS` | *(empty = all)* | Comma-separated channel IDs where the bot operates, e.g. `123456789,987654321` |
+| `ALLOWED_USER_IDS` | *(empty = all)* | Comma-separated user IDs allowed to use the bot, e.g. `123,456` |
+| `WORKING_DIR` | `.` | Working directory the agent CLI runs in (your projects) |
+| `AGENT_TYPE` | `kimi` | Agent adapter to use (see the registry in `src/infrastructure/agents/registry.py`) |
+| `KIMI_COMMAND` | `kimi` | Path/name of the Kimi Code CLI binary |
+| `KIMI_AUTO_APPROVE_FLAG` | `--yolo` | Flag passed when you approve a run |
+| `KIMI_SESSIONS_DIR` | `~/.kimi-code/sessions` | Where the CLI stores sessions (used for context %) |
+| `KIMI_CONTEXT_WINDOW` | `1048576` | Context window size in tokens (for the % calculation) |
+| `PROMPT_TIMEOUT` | `300` | Seconds before a run is killed |
+| `RATE_LIMIT_SECONDS` | `10` | Per-user cooldown between prompts |
+| `LOG_LEVEL` | `INFO` | Logging level |
+
+Notes:
+
+- `ALLOWED_CHANNEL_IDS` and `ALLOWED_USER_IDS` use **comma-separated** format (`123,456`), not JSON arrays.
+- Setting `ALLOWED_USER_IDS` is strongly recommended because the bot accepts DMs from anyone it can see otherwise.
+- `.env` is git-ignored — never commit it.
+
+## Run locally
+
+```bash
+python3.11 -m venv .venv
+source .venv/bin/activate
+make install
+make run        # or: python -m src.interface.bot
+```
+
+## Run with Docker
+
+```bash
+docker compose up -d --build
+```
+
+The compose file mounts two volumes:
+
+- `${WORKING_DIR}` — the bot's working directory, i.e. your projects. Mounted at the same path inside the container so agent session paths stay consistent.
+- `${HOME}/.kimi-code` → `/root/.kimi-code` — the agent home dir, which carries the CLI binary (`bin/`), credentials, and sessions. The Dockerfile puts `/root/.kimi-code/bin` on `PATH`.
+
+Note: the mounted CLI binary runs inside a Linux container, so it must be Linux-compatible (on macOS hosts, install a Linux build of the CLI into the mounted dir or install the CLI inside the image instead).
+
+## Usage
+
+- `/prompt add a health endpoint to app.py` — run a prompt against the agent CLI
+- Mention the bot in an allowed channel, DM it, or reply to one of its results to continue the conversation — all act as prompts
+- On every result, press ✅ to re-run the last prompt with auto-approval, ❌ to discard it, or 🔄 to retry it
+- `/clear` — clear context; the next prompt starts a fresh session
+- `/status` — show the active run and context-window usage %
+- `/cancel` — kill the active run
+
+## Adding a new agent adapter
+
+1. Create `src/infrastructure/agents/claude.py` with a `ClaudeAdapter(AgentAdapter)` implementing `name` and `build_command` (`parse_output` and `get_context_percent` hooks are optional).
+2. Register it: `AGENT_ADAPTERS["claude"] = ClaudeAdapter.from_settings` in `registry.py`.
+3. Set `AGENT_TYPE=claude` in `.env`. Done — services, Discord, and Docker are unchanged.
+
+Minimal example (compiles against the contract in `src/infrastructure/agents/base.py`):
+
+```python
+from src.domain.models import Prompt
+from src.infrastructure.agents.base import AgentAdapter
+from src.infrastructure.config import Settings
+
+
+class ClaudeAdapter(AgentAdapter):
+    def __init__(self, command: str = "claude") -> None:
+        self._command = command
+
+    @classmethod
+    def from_settings(cls, settings: Settings) -> "ClaudeAdapter":
+        return cls()
+
+    @property
+    def name(self) -> str:
+        return "claude"
+
+    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
+        argv = [self._command, "-p", prompt.text]
+        if session_id:
+            argv.extend(["--resume", session_id])
+        return argv
+```
+
+Then in `src/infrastructure/agents/registry.py`:
+
+```python
+AGENT_ADAPTERS: dict[str, Callable[[Settings], AgentAdapter]] = {
+    "kimi": KimiAdapter.from_settings,
+    "claude": ClaudeAdapter.from_settings,
+}
+```
+
+## Free hosting
+
+- **Oracle Cloud Always Free** — ARM VM (up to 4 cores / 24 GB RAM). Install Python and the agent CLI on the VM, then run the bot with systemd or `docker compose up -d`.
+- **Railway** — ~$5/mo free credit; deploy straight from the repo with the included Dockerfile.
+- **Wispbyte** — free bot hosting; works as long as the plan supports a persistent process (and you can install the agent CLI).
+
+## Troubleshooting
+
+| Symptom | Fix |
+|---|---|
+| `Configuration error: DISCORD_BOT_TOKEN is not set` | Create `.env` from `.env.example` and fill in your bot token |
+| Slash commands don't appear | Wait a moment for command sync; re-invite the bot with the `applications.commands` scope |
+| Bot ignores mentions/DMs | Enable the **Message Content** privileged intent in the Developer Portal |
+| `Unknown AGENT_TYPE '...'` | Check spelling against the registry (`src/infrastructure/agents/registry.py`) |
+| Timeout errors | Raise `PROMPT_TIMEOUT` in `.env` |
+| Context shows `n/a` | The agent did not report a session — expected on adapters without session support |
+| `ALLOWED_CHANNEL_IDS` / `ALLOWED_USER_IDS` not applied | Use comma-separated format (`123,456`), not JSON arrays |
+| Agent CLI not found in Docker | Check the mounted agent home dir and that its `bin/` is on `PATH` |
+
+## Development
+
+```bash
+make test       # run the test suite
+make coverage   # coverage gate: ≥60% on src/application + src/infrastructure
+make lint       # ruff check src tests
+```
+
+Tests never touch Discord or the real agent CLI — external boundaries are faked, so the suite runs fully offline.
diff --git a/docker-compose.yml b/docker-compose.yml
new file mode 100644
index 0000000..54586ff
--- /dev/null
+++ b/docker-compose.yml
@@ -0,0 +1,10 @@
+services:
+  bot:
+    build: .
+    env_file: .env
+    volumes:
+      # The bot's working directory (your projects).
+      - ${WORKING_DIR:-.}:${WORKING_DIR:-.}
+      # The agent CLI binary, credentials and sessions (kimi example).
+      - ${HOME}/.kimi-code:/root/.kimi-code
+    restart: unless-stopped
diff --git a/pytest.ini b/pytest.ini
new file mode 100644
index 0000000..8f32afa
--- /dev/null
+++ b/pytest.ini
@@ -0,0 +1,4 @@
+[pytest]
+asyncio_mode = auto
+testpaths = tests
+pythonpath = .
diff --git a/requirements.txt b/requirements.txt
new file mode 100644
index 0000000..f58ca64
--- /dev/null
+++ b/requirements.txt
@@ -0,0 +1,9 @@
+discord.py==2.6.4
+pydantic==2.11.5
+pydantic-settings==2.9.1
+python-dotenv==1.1.0
+structlog==25.3.0
+pytest==8.4.0
+pytest-asyncio==1.0.0
+pytest-cov==6.2.1
+ruff==0.12.0
diff --git a/src/__init__.py b/src/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/application/__init__.py b/src/application/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/application/approval_service.py b/src/application/approval_service.py
new file mode 100644
index 0000000..0781f1f
--- /dev/null
+++ b/src/application/approval_service.py
@@ -0,0 +1,33 @@
+"""Use case: resolve Approve / Reject / Retry button actions."""
+
+from __future__ import annotations
+
+from src.application.prompt_history import PromptHistory
+from src.application.prompt_service import PromptService
+from src.domain.models import ApprovalStatus, Response
+
+
+class ApprovalService:
+    """Handles user decisions on a prompt's result."""
+
+    def __init__(self, prompt_service: PromptService, history: PromptHistory) -> None:
+        self._prompt_service = prompt_service
+        self._history = history
+
+    async def approve(self, user_id: int) -> Response:
+        """Re-run the user's last prompt with auto-approval enabled."""
+        prompt = self._history.get(user_id)
+        return await self._prompt_service.execute(prompt.text, user_id, auto_approve=True)
+
+    async def retry(self, user_id: int) -> Response:
+        """Re-run the user's last prompt unchanged."""
+        prompt = self._history.get(user_id)
+        return await self._prompt_service.execute(
+            prompt.text, user_id, auto_approve=prompt.auto_approve
+        )
+
+    async def reject(self, user_id: int) -> ApprovalStatus:
+        """Discard the user's last prompt."""
+        self._history.get(user_id)  # raises if there is nothing to reject
+        self._history.clear(user_id)
+        return ApprovalStatus.REJECTED
diff --git a/src/application/prompt_history.py b/src/application/prompt_history.py
new file mode 100644
index 0000000..14b8ebb
--- /dev/null
+++ b/src/application/prompt_history.py
@@ -0,0 +1,30 @@
+"""In-memory history of the last prompt per user."""
+
+from src.domain.exceptions import NoPreviousPromptError
+from src.domain.models import Prompt
+
+
+class PromptHistory:
+    """Remembers the most recent prompt each user sent."""
+
+    def __init__(self) -> None:
+        self._last: dict[int, Prompt] = {}
+
+    def record(self, prompt: Prompt) -> None:
+        """Store prompt as the user's most recent one."""
+        self._last[prompt.user_id] = prompt
+
+    def get(self, user_id: int) -> Prompt:
+        """Return the user's last prompt.
+
+        Raises:
+            NoPreviousPromptError: if the user has no recorded prompt.
+        """
+        try:
+            return self._last[user_id]
+        except KeyError as exc:
+            raise NoPreviousPromptError("No previous prompt to act on.") from exc
+
+    def clear(self, user_id: int) -> None:
+        """Forget the user's last prompt, if any."""
+        self._last.pop(user_id, None)
diff --git a/src/application/prompt_service.py b/src/application/prompt_service.py
new file mode 100644
index 0000000..a20461a
--- /dev/null
+++ b/src/application/prompt_service.py
@@ -0,0 +1,101 @@
+"""Use case: run a prompt against the coding agent and notify the result."""
+
+from __future__ import annotations
+
+import structlog
+
+from src.application.prompt_history import PromptHistory
+from src.domain.exceptions import (
+    NoActiveExecutionError,
+    PromptValidationError,
+)
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    Notifier,
+    RateLimiter,
+    SessionStore,
+)
+from src.domain.models import Execution, Prompt, Response
+
+logger = structlog.get_logger(__name__)
+
+
+class PromptService:
+    """Orchestrates validation, rate limiting, execution and notification."""
+
+    FORBIDDEN_TOKENS: tuple[str, ...] = (";", "|", "&&", "`", "$(")
+
+    def __init__(
+        self,
+        runner: AgentRunner,
+        tracker: ExecutionTracker,
+        rate_limiter: RateLimiter,
+        session_store: SessionStore,
+        history: PromptHistory,
+        notifier: Notifier | None = None,
+    ) -> None:
+        self._runner = runner
+        self._tracker = tracker
+        self._rate_limiter = rate_limiter
+        self._session_store = session_store
+        self._history = history
+        self._notifier = notifier
+
+    async def execute(self, text: str, user_id: int, auto_approve: bool = False) -> Response:
+        """Validate and run a prompt, then notify and store the result."""
+        self._validate(text)
+        self._rate_limiter.check(user_id)
+        prompt = Prompt(text=text, user_id=user_id, auto_approve=auto_approve)
+        self._tracker.try_start(prompt)
+        try:
+            session_id = self._session_store.get(user_id)
+            response = await self._runner.run(prompt, session_id)
+        finally:
+            self._tracker.finish()
+        if response.session_id:
+            self._session_store.set(user_id, response.session_id)
+        self._history.record(prompt)
+        if self._notifier:
+            await self._notifier.send_result(prompt, response)
+        logger.info(
+            "prompt_executed",
+            user_id=user_id,
+            success=response.success,
+            duration=round(response.duration_seconds, 2),
+        )
+        return response
+
+    def current_execution(self) -> Execution | None:
+        """Return the active execution, if any."""
+        return self._tracker.current()
+
+    async def cancel(self) -> None:
+        """Cancel the active execution.
+
+        Raises:
+            NoActiveExecutionError: if nothing is running.
+        """
+        if self._tracker.current() is None:
+            raise NoActiveExecutionError("No active execution to cancel.")
+        await self._runner.cancel()
+
+    def clear_context(self, user_id: int) -> None:
+        """Drop the user's session so the next prompt starts fresh."""
+        self._session_store.clear(user_id)
+
+    def context_percent(self, user_id: int) -> float | None:
+        """Return the user's session context usage, or None if unknown."""
+        session_id = self._session_store.get(user_id)
+        if session_id is None:
+            return None
+        return self._runner.get_context_percent(session_id)
+
+    def _validate(self, text: str) -> None:
+        if not text.strip():
+            raise PromptValidationError("The prompt cannot be empty.")
+        found = [token for token in self.FORBIDDEN_TOKENS if token in text]
+        if found:
+            raise PromptValidationError(
+                "The prompt contains forbidden characters: " + ", ".join(found)
+            )
diff --git a/src/domain/__init__.py b/src/domain/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/domain/exceptions.py b/src/domain/exceptions.py
new file mode 100644
index 0000000..33e3877
--- /dev/null
+++ b/src/domain/exceptions.py
@@ -0,0 +1,37 @@
+"""Domain exceptions. All user-facing errors derive from BotError."""
+
+
+class BotError(Exception):
+    """Base class for all expected, user-facing bot errors."""
+
+
+class ConfigError(BotError):
+    """Invalid or missing configuration at startup."""
+
+
+class PromptValidationError(BotError):
+    """The prompt text failed safety validation."""
+
+
+class RateLimitError(BotError):
+    """The user is sending prompts too fast."""
+
+    def __init__(self, retry_after: float) -> None:
+        self.retry_after = retry_after
+        super().__init__(f"Rate limit: try again in {retry_after:.0f}s")
+
+
+class ExecutionBusyError(BotError):
+    """Another execution is already running."""
+
+
+class NoActiveExecutionError(BotError):
+    """No execution is currently running."""
+
+
+class NoPreviousPromptError(BotError):
+    """No earlier prompt exists for this user."""
+
+
+class RunnerError(BotError):
+    """The agent runner failed unexpectedly."""
diff --git a/src/domain/interfaces.py b/src/domain/interfaces.py
new file mode 100644
index 0000000..f14cc2a
--- /dev/null
+++ b/src/domain/interfaces.py
@@ -0,0 +1,79 @@
+"""Ports (abstract interfaces) implemented by the infrastructure layer."""
+
+from __future__ import annotations
+
+from abc import ABC, abstractmethod
+
+from src.domain.models import Execution, Prompt, Response
+
+
+class AgentRunner(ABC):
+    """Runs prompts against a coding agent."""
+
+    @abstractmethod
+    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
+        """Execute a prompt, resuming session_id when provided."""
+
+    @abstractmethod
+    async def cancel(self) -> None:
+        """Cancel the active execution, if any."""
+
+    @abstractmethod
+    def get_context_percent(self, session_id: str) -> float | None:
+        """Return the session's context window usage, or None if unknown."""
+
+
+class Notifier(ABC):
+    """Delivers results and errors back to the user."""
+
+    @abstractmethod
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        """Send a run result."""
+
+    @abstractmethod
+    async def send_error(self, message: str) -> None:
+        """Send a user-facing error message."""
+
+
+class ExecutionTracker(ABC):
+    """Tracks the single active execution."""
+
+    @abstractmethod
+    def try_start(self, prompt: Prompt) -> Execution:
+        """Begin tracking a new execution.
+
+        Raises:
+            ExecutionBusyError: if another execution is active.
+        """
+
+    @abstractmethod
+    def finish(self) -> None:
+        """Mark the active execution as finished."""
+
+    @abstractmethod
+    def current(self) -> Execution | None:
+        """Return the active execution, if any."""
+
+
+class SessionStore(ABC):
+    """Stores the current agent session id per user."""
+
+    @abstractmethod
+    def get(self, user_id: int) -> str | None:
+        """Return the user's session id, if any."""
+
+    @abstractmethod
+    def set(self, user_id: int, session_id: str) -> None:
+        """Store the user's session id."""
+
+    @abstractmethod
+    def clear(self, user_id: int) -> None:
+        """Drop the user's session id."""
+
+
+class RateLimiter(ABC):
+    """Enforces a per-user cooldown between prompts."""
+
+    @abstractmethod
+    def check(self, user_id: int) -> None:
+        """Raise RateLimitError if the user must wait."""
diff --git a/src/domain/models.py b/src/domain/models.py
new file mode 100644
index 0000000..212d600
--- /dev/null
+++ b/src/domain/models.py
@@ -0,0 +1,59 @@
+"""Core domain entities for the Discord agent bot."""
+
+from __future__ import annotations
+
+import time
+from dataclasses import dataclass, field
+from enum import Enum
+
+
+class ApprovalStatus(Enum):
+    """Lifecycle of a prompt's proposed changes."""
+
+    PENDING = "pending"
+    APPROVED = "approved"
+    REJECTED = "rejected"
+
+
+@dataclass(frozen=True)
+class Prompt:
+    """A user request to run against the coding agent."""
+
+    text: str
+    user_id: int
+    auto_approve: bool = False
+    created_at: float = field(default_factory=time.time)
+
+
+@dataclass(frozen=True)
+class Response:
+    """The result of running a prompt through an agent."""
+
+    output: str
+    success: bool
+    duration_seconds: float
+    timed_out: bool = False
+    agent_name: str = "agent"
+    session_id: str | None = None
+    context_percent: float | None = None
+
+
+@dataclass(frozen=True)
+class ParseResult:
+    """Structured data extracted from raw agent output."""
+
+    text: str
+    session_id: str | None = None
+
+
+@dataclass
+class Execution:
+    """Tracks the currently running execution (in-memory)."""
+
+    prompt: Prompt
+    started_at: float = field(default_factory=time.time)
+
+    @property
+    def elapsed_seconds(self) -> float:
+        """Seconds since the execution started."""
+        return time.time() - self.started_at
diff --git a/src/infrastructure/__init__.py b/src/infrastructure/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/infrastructure/agents/__init__.py b/src/infrastructure/agents/__init__.py
new file mode 100644
index 0000000..e69de29
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
index 0000000..6211f7f
--- /dev/null
+++ b/src/infrastructure/agents/kimi.py
@@ -0,0 +1,107 @@
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
+            if not isinstance(event, dict):
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
+        total = sum(v for v in usage.values() if isinstance(v, (int, float)))
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
+                    if not isinstance(event, dict):
+                        continue
+                    if event.get("type") == "usage.record":
+                        candidate = event.get("usage")
+                        if isinstance(candidate, dict):
+                            usage = candidate
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
diff --git a/src/infrastructure/discord_adapter.py b/src/infrastructure/discord_adapter.py
new file mode 100644
index 0000000..2e9c62e
--- /dev/null
+++ b/src/infrastructure/discord_adapter.py
@@ -0,0 +1,100 @@
+"""Discord implementation of the Notifier port."""
+
+from __future__ import annotations
+
+import io
+
+import discord
+
+from src.domain.interfaces import Notifier
+from src.domain.models import Prompt, Response
+
+EMBED_CHAR_LIMIT = 1900
+COLOR_SUCCESS = 0x2ECC71
+COLOR_FAILURE = 0xE74C3C
+COLOR_TIMEOUT = 0xF39C12
+
+
+def build_result_embed(prompt: Prompt, response: Response) -> discord.Embed:
+    """Build the embed for a run result."""
+    if response.timed_out:
+        title, color = f"⏱️ {response.agent_name} — timeout", COLOR_TIMEOUT
+    elif response.success:
+        title, color = f"✅ {response.agent_name} — done", COLOR_SUCCESS
+    else:
+        title, color = f"❌ {response.agent_name} — failed", COLOR_FAILURE
+    embed = discord.Embed(
+        title=title,
+        description=f"```{_truncate(response.output)}```",
+        color=color,
+    )
+    embed.add_field(name="Prompt", value=_truncate(prompt.text, 200), inline=False)
+    embed.set_footer(text=_footer(response))
+    return embed
+
+
+def build_error_embed(message: str) -> discord.Embed:
+    """Build a user-facing error embed."""
+    return discord.Embed(title="⚠️ Error", description=message, color=COLOR_FAILURE)
+
+
+def output_to_file(response: Response) -> discord.File | None:
+    """Attach the full output as a markdown file when it exceeds the embed limit."""
+    if len(response.output) <= EMBED_CHAR_LIMIT:
+        return None
+    buffer = io.BytesIO(response.output.encode())
+    return discord.File(buffer, filename="output.md")
+
+
+def _truncate(text: str, limit: int = EMBED_CHAR_LIMIT) -> str:
+    if len(text) <= limit:
+        return text
+    return text[: limit - 25] + "\n... (see attached file)"
+
+
+def _footer(response: Response) -> str:
+    parts = [f"{response.duration_seconds:.1f}s"]
+    if response.context_percent is not None:
+        parts.append(f"Context: {response.context_percent}%")
+    else:
+        parts.append("Context: n/a")
+    if response.session_id:
+        parts.append(response.session_id[:20])
+    return " · ".join(parts)
+
+
+class DiscordNotifier(Notifier):
+    """Sends results and errors to a Discord interaction or channel."""
+
+    def __init__(
+        self, target: discord.Interaction | discord.abc.Messageable, author_id: int
+    ) -> None:
+        self._target = target
+        self._author_id = author_id
+        self._view: discord.ui.View | None = None
+
+    def attach_view(self, view: discord.ui.View) -> None:
+        """Attach the approval view shown on result messages."""
+        self._view = view
+
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        """Send the run result with mention, embed, optional file and view."""
+        kwargs: dict = {
+            "content": f"<@{self._author_id}>",
+            "embed": build_result_embed(prompt, response),
+            "view": self._view,
+        }
+        file = output_to_file(response)
+        if file is not None:
+            kwargs["file"] = file
+        await self._send(**kwargs)
+
+    async def send_error(self, message: str) -> None:
+        """Send a friendly error message."""
+        await self._send(embed=build_error_embed(message))
+
+    async def _send(self, **kwargs) -> None:
+        if isinstance(self._target, discord.Interaction):
+            await self._target.followup.send(**kwargs)
+        else:
+            await self._target.send(**kwargs)
diff --git a/src/infrastructure/execution_tracker.py b/src/infrastructure/execution_tracker.py
new file mode 100644
index 0000000..9882973
--- /dev/null
+++ b/src/infrastructure/execution_tracker.py
@@ -0,0 +1,29 @@
+"""In-memory single-execution tracker."""
+
+from src.domain.exceptions import ExecutionBusyError
+from src.domain.interfaces import ExecutionTracker
+from src.domain.models import Execution, Prompt
+
+
+class InMemoryExecutionTracker(ExecutionTracker):
+    """Allows exactly one active execution at a time."""
+
+    def __init__(self) -> None:
+        self._current: Execution | None = None
+
+    def try_start(self, prompt: Prompt) -> Execution:
+        """Start tracking; raise ExecutionBusyError when busy."""
+        if self._current is not None:
+            raise ExecutionBusyError(
+                "An execution is already running. Use /status or /cancel."
+            )
+        self._current = Execution(prompt=prompt)
+        return self._current
+
+    def finish(self) -> None:
+        """Clear the active execution."""
+        self._current = None
+
+    def current(self) -> Execution | None:
+        """Return the active execution, if any."""
+        return self._current
diff --git a/src/infrastructure/rate_limiter.py b/src/infrastructure/rate_limiter.py
new file mode 100644
index 0000000..f8c7b40
--- /dev/null
+++ b/src/infrastructure/rate_limiter.py
@@ -0,0 +1,28 @@
+"""In-memory per-user rate limiter."""
+
+from __future__ import annotations
+
+import time
+from typing import Callable
+
+from src.domain.exceptions import RateLimitError
+from src.domain.interfaces import RateLimiter
+
+
+class InMemoryRateLimiter(RateLimiter):
+    """Allows one action per user per cooldown window."""
+
+    def __init__(
+        self, cooldown_seconds: float, clock: Callable[[], float] = time.monotonic
+    ) -> None:
+        self._cooldown = cooldown_seconds
+        self._clock = clock
+        self._last_seen: dict[int, float] = {}
+
+    def check(self, user_id: int) -> None:
+        """Raise RateLimitError if the user is inside the cooldown window."""
+        now = self._clock()
+        last = self._last_seen.get(user_id)
+        if last is not None and now - last < self._cooldown:
+            raise RateLimitError(self._cooldown - (now - last))
+        self._last_seen[user_id] = now
diff --git a/src/infrastructure/session_store.py b/src/infrastructure/session_store.py
new file mode 100644
index 0000000..a6fde81
--- /dev/null
+++ b/src/infrastructure/session_store.py
@@ -0,0 +1,22 @@
+"""In-memory session store."""
+
+from src.domain.interfaces import SessionStore
+
+
+class InMemorySessionStore(SessionStore):
+    """Keeps the current agent session id per user (volatile)."""
+
+    def __init__(self) -> None:
+        self._sessions: dict[int, str] = {}
+
+    def get(self, user_id: int) -> str | None:
+        """Return the user's session id, if any."""
+        return self._sessions.get(user_id)
+
+    def set(self, user_id: int, session_id: str) -> None:
+        """Store the user's session id."""
+        self._sessions[user_id] = session_id
+
+    def clear(self, user_id: int) -> None:
+        """Drop the user's session id."""
+        self._sessions.pop(user_id, None)
diff --git a/src/interface/__init__.py b/src/interface/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/src/interface/bot.py b/src/interface/bot.py
new file mode 100644
index 0000000..cb4b581
--- /dev/null
+++ b/src/interface/bot.py
@@ -0,0 +1,125 @@
+"""Bot factory and entry point."""
+
+from __future__ import annotations
+
+import logging
+import sys
+
+import discord
+import structlog
+from discord.ext import commands
+
+from src.application.prompt_history import PromptHistory
+from src.domain.exceptions import ConfigError
+from src.infrastructure.agents.registry import create_agent_runner
+from src.infrastructure.config import load_settings
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.rate_limiter import InMemoryRateLimiter
+from src.infrastructure.session_store import InMemorySessionStore
+from src.interface.commands import (
+    AgentCog,
+    BotDeps,
+    channel_is_allowed,
+    run_prompt_flow,
+    user_is_allowed,
+)
+
+logger = structlog.get_logger(__name__)
+
+
+def create_bot(deps: BotDeps) -> commands.Bot:
+    """Build the Discord bot with slash commands and the message listener."""
+    intents = discord.Intents.default()
+    intents.message_content = True  # privileged intent: enable it in the Dev Portal
+
+    class AgentBot(commands.Bot):
+        async def setup_hook(self) -> None:
+            await self.add_cog(AgentCog(self, deps))
+            await self.tree.sync()
+
+    bot = AgentBot(command_prefix="!", intents=intents)
+
+    @bot.event
+    async def on_ready() -> None:
+        logger.info("bot_ready", user=str(bot.user), agent=deps.settings.agent_type)
+
+    @bot.event
+    async def on_message(message: discord.Message) -> None:
+        if message.author.bot:
+            return
+        text = _extract_prompt_text(message, bot)
+        if text is None:
+            return
+        if not user_is_allowed(deps.settings, message.author.id):
+            return
+        if message.guild is not None and not channel_is_allowed(
+            deps.settings, message.channel.id
+        ):
+            return
+        async with message.channel.typing():
+            await run_prompt_flow(text, message.author.id, message.channel, deps)
+
+    return bot
+
+
+def _extract_prompt_text(message: discord.Message, bot: commands.Bot) -> str | None:
+    """Return the prompt text when the message addresses the bot, else None."""
+    if message.guild is None:  # DM
+        return message.content.strip() or None
+    if bot.user and bot.user.mentioned_in(message):
+        text = message.content
+        for mention in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
+            text = text.replace(mention, "")
+        return text.strip() or None
+    reference = message.reference
+    if reference and isinstance(reference.resolved, discord.Message):
+        if reference.resolved.author == bot.user:
+            return message.content.strip() or None
+    return None
+
+
+def configure_logging(level: str) -> None:
+    """Configure structlog with a secret-stripping processor."""
+
+    def _strip_secrets(_logger, _method, event_dict):
+        for key in ("token", "discord_bot_token", "password", "secret"):
+            event_dict.pop(key, None)
+        return event_dict
+
+    structlog.configure(
+        processors=[
+            structlog.contextvars.merge_contextvars,
+            structlog.processors.add_log_level,
+            structlog.processors.TimeStamper(fmt="iso"),
+            _strip_secrets,
+            structlog.dev.ConsoleRenderer(),
+        ],
+        wrapper_class=structlog.make_filtering_bound_logger(
+            getattr(logging, level.upper(), logging.INFO)
+        ),
+    )
+
+
+def main() -> None:
+    """Entry point: build everything and run the bot."""
+    try:
+        settings = load_settings()
+        configure_logging(settings.log_level)
+        runner = create_agent_runner(settings)
+    except ConfigError as exc:
+        print(f"Configuration error: {exc}", file=sys.stderr)
+        sys.exit(1)
+    deps = BotDeps(
+        settings=settings,
+        runner=runner,
+        tracker=InMemoryExecutionTracker(),
+        rate_limiter=InMemoryRateLimiter(settings.rate_limit_seconds),
+        session_store=InMemorySessionStore(),
+        history=PromptHistory(),
+    )
+    bot = create_bot(deps)
+    bot.run(settings.discord_bot_token, log_handler=None)
+
+
+if __name__ == "__main__":
+    main()
diff --git a/src/interface/commands.py b/src/interface/commands.py
new file mode 100644
index 0000000..57b1fcc
--- /dev/null
+++ b/src/interface/commands.py
@@ -0,0 +1,156 @@
+"""Slash commands and the shared prompt flow."""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+
+import discord
+import structlog
+from discord import app_commands
+from discord.ext import commands
+
+from src.application.approval_service import ApprovalService
+from src.application.prompt_history import PromptHistory
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import BotError
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    RateLimiter,
+    SessionStore,
+)
+from src.infrastructure.config import Settings
+from src.infrastructure.discord_adapter import DiscordNotifier, build_error_embed
+from src.interface.components import ApprovalView
+
+logger = structlog.get_logger(__name__)
+
+
+@dataclass
+class BotDeps:
+    """Shared dependencies injected into handlers."""
+
+    settings: Settings
+    runner: AgentRunner
+    tracker: ExecutionTracker
+    rate_limiter: RateLimiter
+    session_store: SessionStore
+    history: PromptHistory
+
+
+async def run_prompt_flow(
+    text: str,
+    user_id: int,
+    target: discord.Interaction | discord.abc.Messageable,
+    deps: BotDeps,
+) -> None:
+    """Shared entry point for /prompt and message-based prompts."""
+    notifier = DiscordNotifier(target, author_id=user_id)
+    service = PromptService(
+        runner=deps.runner,
+        tracker=deps.tracker,
+        rate_limiter=deps.rate_limiter,
+        session_store=deps.session_store,
+        history=deps.history,
+        notifier=notifier,
+    )
+    approval = ApprovalService(service, deps.history)
+    notifier.attach_view(ApprovalView(approval, author_id=user_id))
+    try:
+        await service.execute(text, user_id)
+    except BotError as exc:
+        await notifier.send_error(str(exc))
+    except Exception:
+        logger.exception("prompt_flow_failed")
+        await notifier.send_error("Unexpected error. Check the bot logs.")
+
+
+def user_is_allowed(settings: Settings, user_id: int) -> bool:
+    """Return True when no user restriction is set or the user is listed."""
+    return not settings.allowed_user_ids or user_id in settings.allowed_user_ids
+
+
+def channel_is_allowed(settings: Settings, channel_id: int | None) -> bool:
+    """Return True when no channel restriction is set or the channel is listed."""
+    return not settings.allowed_channel_ids or channel_id in settings.allowed_channel_ids
+
+
+class AgentCog(commands.Cog):
+    """Slash commands: /prompt /status /cancel /clear."""
+
+    def __init__(self, bot: commands.Bot, deps: BotDeps) -> None:
+        self.bot = bot
+        self._deps = deps
+
+    def _service(self) -> PromptService:
+        return PromptService(
+            runner=self._deps.runner,
+            tracker=self._deps.tracker,
+            rate_limiter=self._deps.rate_limiter,
+            session_store=self._deps.session_store,
+            history=self._deps.history,
+        )
+
+    async def _guard(self, interaction: discord.Interaction) -> bool:
+        allowed = user_is_allowed(
+            self._deps.settings, interaction.user.id
+        ) and channel_is_allowed(self._deps.settings, interaction.channel_id)
+        if not allowed:
+            await interaction.response.send_message(
+                "This bot does not operate here.", ephemeral=True
+            )
+        return allowed
+
+    @app_commands.command(name="prompt", description="Send a prompt to the coding agent")
+    async def prompt_cmd(self, interaction: discord.Interaction, text: str) -> None:
+        """Handle /prompt."""
+        if not await self._guard(interaction):
+            return
+        await interaction.response.defer()
+        await run_prompt_flow(text, interaction.user.id, interaction, self._deps)
+
+    @app_commands.command(name="status", description="Show the active execution and context usage")
+    async def status_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /status."""
+        if not await self._guard(interaction):
+            return
+        service = self._service()
+        current = service.current_execution()
+        context = service.context_percent(interaction.user.id)
+        context_text = f"{context}%" if context is not None else "n/a"
+        if current is None:
+            description = "No active execution."
+        else:
+            description = (
+                f"Running: `{current.prompt.text[:100]}`\n"
+                f"Elapsed: {current.elapsed_seconds:.0f}s"
+            )
+        embed = discord.Embed(title="📊 Status", description=description, color=0x3498DB)
+        embed.set_footer(text=f"Context: {context_text}")
+        await interaction.response.send_message(embed=embed)
+
+    @app_commands.command(name="cancel", description="Cancel the active execution")
+    async def cancel_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /cancel."""
+        if not await self._guard(interaction):
+            return
+        try:
+            await self._service().cancel()
+        except BotError as exc:
+            await interaction.response.send_message(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+            return
+        await interaction.response.send_message("🛑 Execution cancelled.")
+
+    @app_commands.command(
+        name="clear", description="Clear context: the next prompt starts a fresh session"
+    )
+    async def clear_cmd(self, interaction: discord.Interaction) -> None:
+        """Handle /clear."""
+        if not await self._guard(interaction):
+            return
+        self._service().clear_context(interaction.user.id)
+        await interaction.response.send_message(
+            "🧹 Context cleared. The next prompt starts a fresh session."
+        )
diff --git a/src/interface/components.py b/src/interface/components.py
new file mode 100644
index 0000000..91cb358
--- /dev/null
+++ b/src/interface/components.py
@@ -0,0 +1,77 @@
+"""Discord UI components: approval buttons."""
+
+from __future__ import annotations
+
+from collections.abc import Awaitable, Callable
+
+import discord
+import structlog
+
+from src.application.approval_service import ApprovalService
+from src.domain.exceptions import BotError
+from src.infrastructure.discord_adapter import build_error_embed
+
+logger = structlog.get_logger(__name__)
+
+
+class ApprovalView(discord.ui.View):
+    """Approve / Reject / Retry buttons attached to every run result."""
+
+    def __init__(self, approval_service: ApprovalService, author_id: int) -> None:
+        super().__init__(timeout=900)
+        self._service = approval_service
+        self._author_id = author_id
+
+    async def interaction_check(self, interaction: discord.Interaction) -> bool:
+        """Only the prompt author may use these buttons."""
+        if interaction.user.id == self._author_id:
+            return True
+        await interaction.response.send_message(
+            "Only the prompt author can use these buttons.", ephemeral=True
+        )
+        return False
+
+    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
+    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Re-run the prompt with auto-approval."""
+        await interaction.response.defer()
+        await self._run(interaction, self._service.approve)
+
+    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
+    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Discard the prompt and remove the buttons."""
+        await interaction.response.defer()
+        try:
+            await self._service.reject(interaction.user.id)
+        except BotError as exc:
+            await interaction.followup.send(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+            return
+        if interaction.message:
+            await interaction.message.edit(view=None)
+        await interaction.followup.send("🚫 Rejected.", ephemeral=True)
+
+    @discord.ui.button(label="Retry", style=discord.ButtonStyle.secondary, emoji="🔄")
+    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
+        """Re-run the prompt unchanged."""
+        await interaction.response.defer()
+        await self._run(interaction, self._service.retry)
+
+    async def _run(
+        self,
+        interaction: discord.Interaction,
+        action: Callable[[int], Awaitable[object]],
+    ) -> None:
+        try:
+            await action(interaction.user.id)
+        except BotError as exc:
+            await interaction.followup.send(
+                embed=build_error_embed(str(exc)), ephemeral=True
+            )
+        except Exception:
+            logger.exception("approval_action_failed")
+            await interaction.followup.send(
+                embed=build_error_embed("Unexpected error. Check the bot logs."),
+                ephemeral=True,
+            )
diff --git a/tests/__init__.py b/tests/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/application/__init__.py b/tests/application/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/application/test_approval_service.py b/tests/application/test_approval_service.py
new file mode 100644
index 0000000..4fd386f
--- /dev/null
+++ b/tests/application/test_approval_service.py
@@ -0,0 +1,65 @@
+"""Tests for ApprovalService."""
+
+import pytest
+
+from src.application.approval_service import ApprovalService
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import NoPreviousPromptError
+from src.domain.models import ApprovalStatus, Prompt
+
+
+def make_approval(runner, tracker, rate_limiter, session_store, history, notifier):
+    service = PromptService(
+        runner=runner,
+        tracker=tracker,
+        rate_limiter=rate_limiter,
+        session_store=session_store,
+        history=history,
+        notifier=notifier,
+    )
+    return ApprovalService(service, history)
+
+
+async def test_approve_reruns_with_auto_approve(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    await approval.approve(42)
+    prompt, _ = runner.calls[0]
+    assert prompt.text == "fix"
+    assert prompt.auto_approve is True
+
+
+async def test_retry_reruns_unchanged(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    await approval.retry(42)
+    prompt, _ = runner.calls[0]
+    assert prompt.text == "fix"
+    assert prompt.auto_approve is False
+
+
+async def test_reject_clears_history(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    history.record(Prompt(text="fix", user_id=42))
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    status = await approval.reject(42)
+    assert status is ApprovalStatus.REJECTED
+    with pytest.raises(NoPreviousPromptError):
+        history.get(42)
+
+
+async def test_actions_without_previous_prompt_raise(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    approval = make_approval(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.approve(42)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.retry(42)
+    with pytest.raises(NoPreviousPromptError):
+        await approval.reject(42)
diff --git a/tests/application/test_prompt_service.py b/tests/application/test_prompt_service.py
new file mode 100644
index 0000000..578371f
--- /dev/null
+++ b/tests/application/test_prompt_service.py
@@ -0,0 +1,111 @@
+"""Tests for PromptService."""
+
+import pytest
+
+from src.application.prompt_service import PromptService
+from src.domain.exceptions import (
+    ExecutionBusyError,
+    NoActiveExecutionError,
+    PromptValidationError,
+    RateLimitError,
+)
+from src.domain.interfaces import RateLimiter
+from src.domain.models import Prompt
+
+
+def make_service(runner, tracker, rate_limiter, session_store, history, notifier):
+    return PromptService(
+        runner=runner,
+        tracker=tracker,
+        rate_limiter=rate_limiter,
+        session_store=session_store,
+        history=history,
+        notifier=notifier,
+    )
+
+
+async def test_execute_happy_path(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    response = await service.execute("fix the bug", user_id=42)
+    assert response.success is True
+    assert notifier.results[0][0].text == "fix the bug"
+    assert session_store.get(42) == "sess-1"
+    assert history.get(42).text == "fix the bug"
+    assert tracker.current() is None
+
+
+async def test_execute_resumes_stored_session(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    session_store.set(42, "old-session")
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    await service.execute("continue", user_id=42)
+    assert runner.calls[0][1] == "old-session"
+
+
+@pytest.mark.parametrize(
+    "text",
+    ["rm -rf /; echo", "a | b", "a && b", "`whoami`", "$(whoami)", "   "],
+)
+async def test_execute_rejects_dangerous_text(
+    text, runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(PromptValidationError):
+        await service.execute(text, user_id=42)
+    assert runner.calls == []
+
+
+async def test_execute_enforces_rate_limit(runner, tracker, session_store, history, notifier):
+    class BlockingLimiter(RateLimiter):
+        def check(self, user_id: int) -> None:
+            raise RateLimitError(5.0)
+
+    service = make_service(runner, tracker, BlockingLimiter(), session_store, history, notifier)
+    with pytest.raises(RateLimitError):
+        await service.execute("hello", user_id=42)
+    assert runner.calls == []
+
+
+async def test_execute_rejects_when_busy(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    tracker.try_start(Prompt(text="other", user_id=7))
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(ExecutionBusyError):
+        await service.execute("hello", user_id=42)
+    assert runner.calls == []
+
+
+async def test_cancel_without_execution_raises(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    with pytest.raises(NoActiveExecutionError):
+        await service.cancel()
+
+
+async def test_cancel_delegates_to_runner(
+    runner, tracker, rate_limiter, session_store, history, notifier
+):
+    tracker.try_start(Prompt(text="x", user_id=42))
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    await service.cancel()
+    assert runner.cancelled is True
+
+
+def test_clear_context(runner, tracker, rate_limiter, session_store, history, notifier):
+    session_store.set(42, "sess")
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    service.clear_context(42)
+    assert session_store.get(42) is None
+
+
+def test_context_percent(runner, tracker, rate_limiter, session_store, history, notifier):
+    runner.context = 12.5
+    service = make_service(runner, tracker, rate_limiter, session_store, history, notifier)
+    assert service.context_percent(42) is None
+    session_store.set(42, "sess")
+    assert service.context_percent(42) == 12.5
diff --git a/tests/conftest.py b/tests/conftest.py
new file mode 100644
index 0000000..7b9f556
--- /dev/null
+++ b/tests/conftest.py
@@ -0,0 +1,93 @@
+"""Shared test fixtures and fakes."""
+
+from __future__ import annotations
+
+import pytest
+
+from src.application.prompt_history import PromptHistory
+from src.domain.interfaces import (
+    AgentRunner,
+    ExecutionTracker,
+    Notifier,
+    RateLimiter,
+    SessionStore,
+)
+from src.domain.models import Prompt, Response
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.session_store import InMemorySessionStore
+
+
+class FakeRunner(AgentRunner):
+    """Records run calls and returns a canned response."""
+
+    def __init__(self) -> None:
+        self.calls: list[tuple[Prompt, str | None]] = []
+        self.cancelled = False
+        self.context: float | None = None
+
+    async def run(self, prompt: Prompt, session_id: str | None = None) -> Response:
+        self.calls.append((prompt, session_id))
+        return Response(
+            output="done",
+            success=True,
+            duration_seconds=0.1,
+            agent_name="fake",
+            session_id="sess-1",
+        )
+
+    async def cancel(self) -> None:
+        self.cancelled = True
+
+    def get_context_percent(self, session_id: str) -> float | None:
+        return self.context
+
+
+class FakeNotifier(Notifier):
+    """Captures sent results and errors."""
+
+    def __init__(self) -> None:
+        self.results: list[tuple[Prompt, Response]] = []
+        self.errors: list[str] = []
+
+    async def send_result(self, prompt: Prompt, response: Response) -> None:
+        self.results.append((prompt, response))
+
+    async def send_error(self, message: str) -> None:
+        self.errors.append(message)
+
+
+class AllowAllRateLimiter(RateLimiter):
+    """Never blocks."""
+
+    def check(self, user_id: int) -> None:
+        return None
+
+
+@pytest.fixture
+def runner() -> FakeRunner:
+    return FakeRunner()
+
+
+@pytest.fixture
+def notifier() -> FakeNotifier:
+    return FakeNotifier()
+
+
+@pytest.fixture
+def tracker() -> ExecutionTracker:
+    return InMemoryExecutionTracker()
+
+
+@pytest.fixture
+def session_store() -> SessionStore:
+    return InMemorySessionStore()
+
+
+@pytest.fixture
+def history() -> PromptHistory:
+    return PromptHistory()
+
+
+@pytest.fixture
+def rate_limiter() -> RateLimiter:
+    return AllowAllRateLimiter()
diff --git a/tests/infrastructure/__init__.py b/tests/infrastructure/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/infrastructure/agents/__init__.py b/tests/infrastructure/agents/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/infrastructure/agents/test_kimi_adapter.py b/tests/infrastructure/agents/test_kimi_adapter.py
new file mode 100644
index 0000000..39f8328
--- /dev/null
+++ b/tests/infrastructure/agents/test_kimi_adapter.py
@@ -0,0 +1,136 @@
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
+def test_parse_output_ignores_non_dict_json():
+    raw = "\n".join(
+        [
+            "null",
+            json.dumps({"role": "assistant", "content": "Hello"}),
+            "42",
+            "[1, 2]",
+            json.dumps(
+                {"role": "meta", "type": "session.resume_hint", "session_id": "sess-1"}
+            ),
+        ]
+    )
+    result = KimiAdapter().parse_output(raw)
+    assert result.text == "Hello"
+    assert result.session_id == "sess-1"
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
+
+
+def _write_wire(tmp_path, lines):
+    wire = tmp_path / "wd_x" / "sess-1" / "agents" / "main" / "wire.jsonl"
+    wire.parent.mkdir(parents=True)
+    wire.write_text("\n".join(lines) + "\n")
+    return wire
+
+
+def test_get_context_percent_ignores_non_dict_json_line(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            "null",
+            "42",
+            "[1, 2]",
+            json.dumps({"type": "usage.record", "usage": {"input": 50000, "output": 50000}}),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
+
+
+def test_get_context_percent_ignores_non_numeric_usage_values(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            json.dumps(
+                {
+                    "type": "usage.record",
+                    "usage": {"input": 90000, "output": 10000, "note": "n/a"},
+                }
+            ),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
+
+
+def test_get_context_percent_ignores_non_dict_usage(tmp_path):
+    _write_wire(
+        tmp_path,
+        [
+            json.dumps({"type": "usage.record", "usage": {"input": 90000, "output": 10000}}),
+            json.dumps({"type": "usage.record", "usage": "high"}),
+        ],
+    )
+    adapter = KimiAdapter(sessions_dir=str(tmp_path), context_window=1000000)
+    assert adapter.get_context_percent("sess-1") == 10.0
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
index 0000000..804bfe5
--- /dev/null
+++ b/tests/infrastructure/agents/test_subprocess_runner.py
@@ -0,0 +1,118 @@
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
+    process.pid = 99999  # mocked pid; killpg is patched to fail in kill tests
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
+    with (
+        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
+        # killpg must not signal a real process group if pid 99999 happens to exist
+        patch(
+            "src.infrastructure.agents.base.os.killpg",
+            side_effect=ProcessLookupError,
+        ),
+    ):
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
+    with (
+        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
+        # killpg must not signal a real process group if pid 99999 happens to exist
+        patch(
+            "src.infrastructure.agents.base.os.killpg",
+            side_effect=ProcessLookupError,
+        ),
+    ):
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
diff --git a/tests/infrastructure/test_discord_adapter.py b/tests/infrastructure/test_discord_adapter.py
new file mode 100644
index 0000000..6dc93f3
--- /dev/null
+++ b/tests/infrastructure/test_discord_adapter.py
@@ -0,0 +1,58 @@
+"""Tests for Discord embed/file helpers (no connection needed)."""
+
+import discord
+
+from src.domain.models import Prompt, Response
+from src.infrastructure.discord_adapter import (
+    EMBED_CHAR_LIMIT,
+    build_error_embed,
+    build_result_embed,
+    output_to_file,
+)
+
+
+def make_response(**overrides) -> Response:
+    defaults = dict(output="ok", success=True, duration_seconds=1.5, agent_name="kimi")
+    return Response(**(defaults | overrides))
+
+
+def test_success_embed_is_green():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
+    assert embed.color == discord.Color(0x2ECC71)
+    assert "ok" in embed.description
+
+
+def test_failure_embed_is_red():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response(success=False))
+    assert embed.color == discord.Color(0xE74C3C)
+
+
+def test_timeout_embed_is_orange():
+    embed = build_result_embed(
+        Prompt(text="hi", user_id=1), make_response(success=False, timed_out=True)
+    )
+    assert embed.color == discord.Color(0xF39C12)
+
+
+def test_footer_shows_context_and_session():
+    response = make_response(context_percent=12.5, session_id="sess-abcdef")
+    embed = build_result_embed(Prompt(text="hi", user_id=1), response)
+    assert "12.5%" in embed.footer.text
+    assert "sess-abcdef" in embed.footer.text
+
+
+def test_footer_na_when_no_context():
+    embed = build_result_embed(Prompt(text="hi", user_id=1), make_response())
+    assert "n/a" in embed.footer.text
+
+
+def test_output_to_file_only_when_long():
+    assert output_to_file(make_response(output="short")) is None
+    file = output_to_file(make_response(output="x" * (EMBED_CHAR_LIMIT + 1)))
+    assert file is not None
+    assert file.filename == "output.md"
+
+
+def test_error_embed():
+    embed = build_error_embed("boom")
+    assert "boom" in embed.description
diff --git a/tests/infrastructure/test_state_adapters.py b/tests/infrastructure/test_state_adapters.py
new file mode 100644
index 0000000..a319812
--- /dev/null
+++ b/tests/infrastructure/test_state_adapters.py
@@ -0,0 +1,54 @@
+"""Tests for in-memory state adapters."""
+
+import pytest
+
+from src.domain.exceptions import ExecutionBusyError, RateLimitError
+from src.domain.models import Prompt
+from src.infrastructure.execution_tracker import InMemoryExecutionTracker
+from src.infrastructure.rate_limiter import InMemoryRateLimiter
+from src.infrastructure.session_store import InMemorySessionStore
+
+
+def test_rate_limiter_allows_first_call():
+    InMemoryRateLimiter(10).check(1)  # must not raise
+
+
+def test_rate_limiter_blocks_within_cooldown():
+    limiter = InMemoryRateLimiter(10)
+    limiter.check(1)
+    with pytest.raises(RateLimitError):
+        limiter.check(1)
+
+
+def test_rate_limiter_allows_after_cooldown():
+    now = [100.0]
+    limiter = InMemoryRateLimiter(10, clock=lambda: now[0])
+    limiter.check(1)
+    now[0] += 11
+    limiter.check(1)  # must not raise
+
+
+def test_rate_limiter_users_are_independent():
+    limiter = InMemoryRateLimiter(10)
+    limiter.check(1)
+    limiter.check(2)  # must not raise
+
+
+def test_session_store_roundtrip():
+    store = InMemorySessionStore()
+    assert store.get(1) is None
+    store.set(1, "sess-1")
+    assert store.get(1) == "sess-1"
+    store.clear(1)
+    assert store.get(1) is None
+
+
+def test_tracker_single_execution():
+    tracker = InMemoryExecutionTracker()
+    assert tracker.current() is None
+    execution = tracker.try_start(Prompt(text="a", user_id=1))
+    assert tracker.current() is execution
+    with pytest.raises(ExecutionBusyError):
+        tracker.try_start(Prompt(text="b", user_id=2))
+    tracker.finish()
+    assert tracker.current() is None
diff --git a/tests/interface/__init__.py b/tests/interface/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/interface/test_bot_text.py b/tests/interface/test_bot_text.py
new file mode 100644
index 0000000..6792630
--- /dev/null
+++ b/tests/interface/test_bot_text.py
@@ -0,0 +1,61 @@
+"""Tests for extracting prompt text from incoming messages."""
+
+from unittest.mock import MagicMock
+
+import discord
+
+from src.interface.bot import _extract_prompt_text
+
+
+def make_bot(bot_id: int = 999) -> MagicMock:
+    bot = MagicMock()
+    bot.user.id = bot_id
+    return bot
+
+
+def make_guild_message(content: str = "hi") -> MagicMock:
+    message = MagicMock()
+    message.guild = MagicMock()
+    message.content = content
+    message.reference = None
+    return message
+
+
+def test_dm_returns_content():
+    message = MagicMock()
+    message.guild = None
+    message.content = "hello there"
+    assert _extract_prompt_text(message, make_bot()) == "hello there"
+
+
+def test_mention_is_stripped():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = True
+    message = make_guild_message("<@999> fix the bug")
+    assert _extract_prompt_text(message, bot) == "fix the bug"
+
+
+def test_unrelated_guild_message_is_ignored():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    assert _extract_prompt_text(make_guild_message(), bot) is None
+
+
+def test_reply_to_bot_is_prompt():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    message = make_guild_message("and now do X")
+    resolved = MagicMock(spec=discord.Message)
+    resolved.author = bot.user
+    message.reference = MagicMock(resolved=resolved)
+    assert _extract_prompt_text(message, bot) == "and now do X"
+
+
+def test_reply_to_someone_else_is_ignored():
+    bot = make_bot()
+    bot.user.mentioned_in.return_value = False
+    message = make_guild_message("hello")
+    resolved = MagicMock(spec=discord.Message)
+    resolved.author = MagicMock()  # not the bot
+    message.reference = MagicMock(resolved=resolved)
+    assert _extract_prompt_text(message, bot) is None
diff --git a/tests/interface/test_commands_guards.py b/tests/interface/test_commands_guards.py
new file mode 100644
index 0000000..a8c4188
--- /dev/null
+++ b/tests/interface/test_commands_guards.py
@@ -0,0 +1,28 @@
+"""Tests for channel/user allowance guards."""
+
+from src.infrastructure.config import Settings
+from src.interface.commands import channel_is_allowed, user_is_allowed
+
+
+def settings(**overrides) -> Settings:
+    return Settings(discord_bot_token="x", **overrides)
+
+
+def test_user_allowed_when_no_restriction():
+    assert user_is_allowed(settings(), 1) is True
+
+
+def test_user_restriction():
+    restricted = settings(allowed_user_ids=[1, 2])
+    assert user_is_allowed(restricted, 2) is True
+    assert user_is_allowed(restricted, 3) is False
+
+
+def test_channel_allowed_when_no_restriction():
+    assert channel_is_allowed(settings(), 99) is True
+
+
+def test_channel_restriction():
+    restricted = settings(allowed_channel_ids=[10])
+    assert channel_is_allowed(restricted, 10) is True
+    assert channel_is_allowed(restricted, 99) is False
diff --git a/tests/interface/test_components.py b/tests/interface/test_components.py
new file mode 100644
index 0000000..f43261f
--- /dev/null
+++ b/tests/interface/test_components.py
@@ -0,0 +1,24 @@
+"""Tests for ApprovalView interaction checks."""
+
+from unittest.mock import AsyncMock, MagicMock
+
+from src.interface.components import ApprovalView
+
+
+def make_interaction(user_id: int) -> MagicMock:
+    interaction = MagicMock()
+    interaction.user.id = user_id
+    interaction.response.send_message = AsyncMock()
+    return interaction
+
+
+async def test_author_passes_check():
+    view = ApprovalView(approval_service=MagicMock(), author_id=42)
+    assert await view.interaction_check(make_interaction(42)) is True
+
+
+async def test_other_user_is_blocked():
+    view = ApprovalView(approval_service=MagicMock(), author_id=42)
+    interaction = make_interaction(7)
+    assert await view.interaction_check(interaction) is False
+    interaction.response.send_message.assert_awaited()
diff --git a/tests/test_domain_models.py b/tests/test_domain_models.py
new file mode 100644
index 0000000..9f1bd52
--- /dev/null
+++ b/tests/test_domain_models.py
@@ -0,0 +1,30 @@
+"""Tests for domain models."""
+
+import time
+
+from src.domain.models import ApprovalStatus, Execution, Prompt, Response
+
+
+def test_prompt_defaults():
+    prompt = Prompt(text="hello", user_id=42)
+    assert prompt.auto_approve is False
+    assert prompt.created_at <= time.time()
+
+
+def test_response_defaults():
+    response = Response(output="ok", success=True, duration_seconds=1.0)
+    assert response.timed_out is False
+    assert response.agent_name == "agent"
+    assert response.session_id is None
+    assert response.context_percent is None
+
+
+def test_execution_elapsed_seconds():
+    execution = Execution(prompt=Prompt(text="x", user_id=1), started_at=time.time() - 5)
+    assert 4.0 < execution.elapsed_seconds < 6.0
+
+
+def test_approval_status_values():
+    assert ApprovalStatus.PENDING.value == "pending"
+    assert ApprovalStatus.APPROVED.value == "approved"
+    assert ApprovalStatus.REJECTED.value == "rejected"
