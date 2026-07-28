# Design: Discord Bot for Remote Control of Coding Agents

**Date:** 2026-07-26
**Status:** Approved by user (v3: plugin architecture, sessions/context tracking, bidirectional messaging, all artifacts in English)

## Goal

A Discord bot that lets the user drive a coding agent (Kimi Code, or others) remotely from their phone. It receives prompts via Discord, runs them against the agent's CLI on the user's machine, and returns results as Embeds with Approve / Reject / Retry buttons. The bot is bidirectional: it can be "woken up" with a mention, DM, or reply, and it pings the user when a run finishes.

**No vendor lock-in:** the agent is a plugin. The bot only knows the `AgentRunner` port. The concrete adapter is selected via config (`AGENT_TYPE`). Adding support for another agent = one new file in `infrastructure/agents/` + one registry entry. Services and the Discord layer stay untouched.

**Language:** specs, plans, code, comments, and docs are all in English.

## Key decisions (confirmed with user / verified against the real CLI)

1. **Agent invocation:** one-shot async subprocess per prompt (no shell). Each run is independent. Approve re-runs the same prompt with the agent's auto-approve flag.
2. **Approval buttons:** shown on **every** result. Approve = re-run with auto-approval; Reject = discard; Retry = re-run as-is. No output parsing to decide whether to show buttons.
3. **Execution model:** one-shot subprocess (no persistent process, no job queue). One active execution at a time (personal bot).
4. **Plugin architecture:** interchangeable adapters selected by env var. Kimi Code is the first implemented adapter.
5. **Sessions & context (verified against `kimi --help` and real output):**
   - `kimi -p "..."` runs one prompt non-interactively; `-S <session_id>` resumes a session; omitting it starts a fresh one. **Clearing context = dropping the stored session id.**
   - `--output-format stream-json` emits JSON lines: assistant text and a `session.resume_hint` meta line carrying `session_id`.
   - Context % is not in the CLI output, but each session persists `~/.kimi-code/sessions/**/<session_id>/agents/main/wire.jsonl` with `usage.record` token counts. The KimiAdapter computes context % from the last record divided by a configurable context window. If anything is missing, the bot reports `n/a` (never a fake number).
6. **Bidirectional:** an `on_message` listener treats (a) mentions of the bot in allowed channels, (b) DMs, and (c) replies to the bot's own messages as prompts. Every result message mentions the author (`<@user_id>`) so the phone gets a push notification. Requires the privileged **Message Content Intent** (documented in README).

## Architecture

Clean Architecture, 4 layers. Dependencies point inwards: `interface` → `application` → `domain`; `infrastructure` implements `domain` ports.

```
├── src/
│   ├── domain/              # Entities, exceptions, interfaces (ports)
│   │   ├── models.py        # Prompt, Response, ApprovalStatus, Execution, ParseResult
│   │   ├── interfaces.py    # ABCs: AgentRunner, Notifier, ExecutionTracker, SessionStore, RateLimiter
│   │   └── exceptions.py    # BotError hierarchy
│   ├── application/         # Use cases (pure business logic)
│   │   ├── prompt_service.py   # Receive prompt → validate → run → notify; status/cancel/clear
│   │   ├── approval_service.py # Approve / Reject / Retry
│   │   └── prompt_history.py   # Last prompt per user (in-memory)
│   ├── infrastructure/      # Adapters
│   │   ├── agents/             # Agent plugin system
│   │   │   ├── base.py         # AgentAdapter (ABC) + SubprocessAgentRunner (shared logic)
│   │   │   ├── kimi.py         # KimiAdapter (first plugin)
│   │   │   └── registry.py     # AGENT_ADAPTERS + create_agent_runner(settings)
│   │   ├── discord_adapter.py  # Notifier with discord.py (Embeds, file attachments, mentions)
│   │   ├── config.py           # Settings with pydantic-settings
│   │   ├── rate_limiter.py     # Per-user cooldown (in-memory)
│   │   ├── session_store.py    # InMemorySessionStore
│   │   └── execution_tracker.py# InMemoryExecutionTracker
│   └── interface/           # Entry point and Discord handlers
│       ├── bot.py             # create_bot(): intents, command sync, on_message listener
│       ├── commands.py        # /prompt /status /cancel /clear + shared prompt flow
│       └── components.py      # ApprovalView with buttons
├── tests/
├── docs/superpowers/specs/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── README.md
```

## The plugin contract

```python
class AgentAdapter(ABC):
    """Minimal contract to support a coding agent."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
        """Full argv (no shell) to run the prompt, resuming session_id if given."""

    def parse_output(self, raw: str) -> ParseResult:
        """Extract display text and session id from raw stdout. Default: raw text, no session."""

    def get_context_percent(self, session_id: str) -> float | None:
        """Optional: % of context window used by the session. Default: None (reported as n/a)."""
```

`SubprocessAgentRunner` (implements `AgentRunner`) wraps an `AgentAdapter` and owns everything else: spawn via `asyncio.create_subprocess_exec` (`shell=False`, `cwd=WORKING_DIR`), timeout, stdout/stderr capture, cancellation with process-group kill. A new adapter **never touches subprocess code**: it only defines `name` and `build_command` (and optionally the two hooks).

Registry maps `AGENT_TYPE` → factory:

```python
AGENT_ADAPTERS: dict[str, Callable[[Settings], AgentAdapter]] = {
    "kimi": KimiAdapter.from_settings,
}
```

Unknown `AGENT_TYPE` → `ConfigError` at startup listing available adapters.

### KimiAdapter (first plugin)

- `name = "kimi"`.
- `build_command`: `[command, "-p", prompt.text, "--output-format", "stream-json"]` + `[auto_approve_flag]` if `prompt.auto_approve` + `["-S", session_id]` if resuming.
- `parse_output`: parses stream-json lines; concatenates assistant `content`; extracts `session_id` from the `session.resume_hint` meta line. Falls back to raw text if no JSON parses.
- `get_context_percent`: reads the session's `wire.jsonl` under `KIMI_SESSIONS_DIR`, takes the last `usage.record`, sums its token counts, divides by `KIMI_CONTEXT_WINDOW`. Any failure → `None`.
- Config: `KIMI_COMMAND` (default `kimi`), `KIMI_AUTO_APPROVE_FLAG` (default `--yolo`), `KIMI_SESSIONS_DIR` (default `~/.kimi-code/sessions`), `KIMI_CONTEXT_WINDOW` (default `1048576`).

## Components

### Domain

- **`Prompt`**: text, user_id, auto_approve, created_at.
- **`Response`**: output, success, duration_seconds, timed_out, agent_name, session_id, context_percent.
- **`ApprovalStatus`**: enum PENDING / APPROVED / REJECTED.
- **`Execution`**: active execution state (prompt, started_at, elapsed_seconds property). In-memory.
- **`ParseResult`**: text + session_id (adapter output parsing).
- **Ports (ABCs)**:
  - `AgentRunner`: `run(prompt, session_id) -> Response`, `cancel() -> None`, `get_context_percent(session_id) -> float | None`.
  - `Notifier`: `send_result(prompt, response) -> None`, `send_error(message) -> None`.
  - `ExecutionTracker`: `try_start(prompt) -> Execution` (raises if busy), `finish()`, `current() -> Execution | None`.
  - `SessionStore`: `get(user_id) -> str | None`, `set(user_id, session_id)`, `clear(user_id)`.
  - `RateLimiter`: `check(user_id) -> None` (raises `RateLimitError`).
- No imports of discord.py or subprocess. Pure and testable.

### Application

- **`PromptService`** orchestrates the prompt flow:
  1. Sanitizes text: rejects `;`, `|`, `&&`, backticks, `$()` → `PromptValidationError`.
  2. Per-user rate limit (`RATE_LIMIT_SECONDS`, default 10s).
  3. Acquires the single-execution lock → `ExecutionBusyError` if busy.
  4. Loads `session_id` from `SessionStore`; runs via `AgentRunner`.
  5. Stores the returned `session_id`; records prompt in `PromptHistory`; notifies via `Notifier`.
  - Also exposes `status()`, `cancel()`, `clear_context(user_id)` (drops the stored session id), and `context_percent(user_id)`.
- **`ApprovalService`**: resolves buttons using `PromptHistory`:
  - **Approve** → re-runs with `auto_approve=True` (via PromptService).
  - **Reject** → clears history entry, returns REJECTED.
  - **Retry** → re-runs the prompt as-is.
- Only the prompt author may press its buttons (enforced in the interface layer).
- Services know nothing about the concrete agent: they only talk to ports.

### Infrastructure

- **`agents/base.py`**: `AgentAdapter` (plugin ABC) + `SubprocessAgentRunner`:
  - `asyncio.create_subprocess_exec(*adapter.build_command(...), shell=False, cwd=WORKING_DIR, start_new_session=True)`.
  - Timeout via `asyncio.wait_for` (`PROMPT_TIMEOUT`, default 300s). On timeout or cancel: kill the process group (no zombies).
  - Captures stdout+stderr; delegates parsing to `adapter.parse_output`; fills `context_percent` via `adapter.get_context_percent`.
  - Never logs secrets.
- **`agents/kimi.py`**: `KimiAdapter` per the contract above.
- **`agents/registry.py`**: `AGENT_ADAPTERS` + `create_agent_runner(settings) -> AgentRunner`.
- **`DiscordAdapter`** (implements `Notifier`):
  - Accepts either a `discord.Interaction` (slash commands, uses `followup`) or a `discord.abc.Messageable` channel (message flow, uses `send`).
  - Embeds: green success, red error, orange timeout. Title with agent name, duration, output formatted in code blocks.
  - Output > 1900 chars → `.md` file attachment; the embed shows an excerpt.
  - Result messages include `content="<@user_id>"` (phone push) and the `ApprovalView`.
  - Embed footer: `Context: 12.3% · session_abc123` or `Context: n/a`.
  - Friendly errors to the user; stack traces only in logs.
- **`Settings`** (pydantic-settings): `DISCORD_BOT_TOKEN` (required, fail fast with clear message), `ALLOWED_CHANNEL_IDS` (list[int]), `ALLOWED_USER_IDS` (list[int], default empty = no user restriction), `WORKING_DIR`, `AGENT_TYPE` (`kimi`), `KIMI_COMMAND`, `KIMI_AUTO_APPROVE_FLAG`, `KIMI_SESSIONS_DIR`, `KIMI_CONTEXT_WINDOW`, `PROMPT_TIMEOUT` (300), `RATE_LIMIT_SECONDS` (10), `LOG_LEVEL` (INFO).
- **`RateLimiter`**: in-memory dict user_id → last timestamp.
- **`SessionStore`**: in-memory dict user_id → session_id.
- **Logging**: structlog, configurable level, processor that strips token-like keys.

### Interface

- **`bot.py`**: factory `create_bot(settings, runner, tracker, rate_limiter, session_store, history)`:
  - Intents: default + `message_content` (privileged; required for mentions/DMs/replies).
  - `setup_hook`: adds the cog, syncs slash commands.
  - `on_message` listener: ignores bots; treats DMs, mentions in allowed channels, and replies to the bot's own messages as prompts, routed through the same shared flow as `/prompt`.
- **`commands.py`**:
  - `run_prompt_flow(text, user_id, target, deps)`: shared by slash commands and `on_message`. Builds the per-request notifier/service/approval/view, executes, maps `BotError` to friendly embeds.
  - `/prompt <text>`, `/status` (active execution + elapsed + session/context info), `/cancel`, `/clear` (drops session context, confirms the next prompt starts fresh).
- **`components.py`**: `ApprovalView(discord.ui.View)` with Approve ✅ / Reject ❌ / Retry 🔄. `interaction_check` restricts to the prompt author. View timeout 900s (aligned with the 15-minute interaction token lifetime); buttons disabled on timeout.
- **DI (Factory)**: `python -m src.interface.bot` builds Settings → `create_agent_runner(settings)` → adapters/stores → bot.

## Design patterns

- **Plugin / Registry**: interchangeable agent adapters selected by config.
- **Repository**: `AgentRunner` abstracts execution (can become a REST API later).
- **Command**: each slash command is a decoupled handler.
- **Observer**: `Notifier` decouples notification from the runner.
- **Factory**: service construction with DI at the entry point and in the registry.
- **Template Method**: `SubprocessAgentRunner` fixes the execution cycle; the adapter only defines the command and parsing hooks.

## Error handling

| Error | Behavior |
|---|---|
| Missing `DISCORD_BOT_TOKEN` | Immediate startup failure with a clear message |
| Unknown `AGENT_TYPE` | Startup failure listing available adapters |
| Prompt with dangerous characters | Red embed explaining which characters are not allowed |
| Rate limit active | Embed showing remaining seconds |
| Execution busy | Embed saying a run is active (suggests `/status` or `/cancel`) |
| Agent timeout | Orange embed "timeout after Ns", process killed |
| Subprocess error | Generic red embed; stack trace only in logs |
| Channel/user not allowed | Ephemeral reply saying the bot does not operate there |
| Context % unavailable | Footer shows `Context: n/a` (never a fabricated number) |

## Security (non-negotiable)

- No hardcoded secrets; everything via env vars. `.env` in `.gitignore`.
- Strict config validation at startup.
- Input sanitization before subprocess. Always `shell=False` with an argv list. Never `os.system()` or `shell=True`.
- Timeout on every run; process-group kill on cancel/timeout.
- Per-user rate limit.
- Bot restricted to `ALLOWED_CHANNEL_IDS`; optional `ALLOWED_USER_IDS` restricts who can use it at all (strongly recommended since DMs are accepted).
- Never log tokens or secrets.

## Testing

pytest + pytest-asyncio. No real Discord or agent processes:

- **`PromptService`**: sanitization, rate limit, busy lock, happy path with mocked ports, session id load/store, `clear_context`.
- **`ApprovalService`**: approve re-runs with auto_approve, reject clears, retry re-runs, no previous prompt.
- **`SubprocessAgentRunner`**: mocked `asyncio.create_subprocess_exec` — success, timeout (kills), cancel, output capture, cwd, never shell=True. Uses a fake adapter.
- **`KimiAdapter`**: `build_command` with/without auto_approve and session resume; `parse_output` on stream-json lines; `get_context_percent` from a temp `wire.jsonl` and `None` when missing.
- **`registry`**: `AGENT_TYPE=kimi` returns a runner wrapping KimiAdapter; unknown type → `ConfigError`.
- **`RateLimiter`**, **`SessionStore`**, **`ExecutionTracker`**: unit tests.
- **`Settings`**: fails without token, parses id lists.
- **Discord helpers**: embed builders and file attachment logic (pure functions, no connection).

Coverage target: ≥60% on `application/` and `infrastructure/`.

## Code style

- Type hints on all signatures. Functions < 30 lines. Google-style docstrings on public classes.
- Discord logic separated from business logic (testable without the bot).
- All code, comments, specs, plans, and docs in English.

## Adding a new agent (e.g. "claude")

1. Create `src/infrastructure/agents/claude.py` with a `ClaudeAdapter(AgentAdapter)` implementing `name` and `build_command` (hooks optional).
2. Register it: `AGENT_ADAPTERS["claude"] = ClaudeAdapter.from_settings`.
3. Set `AGENT_TYPE=claude` in `.env`. Done — services, Discord, and Docker unchanged.

The README documents this flow with a complete example.

## Deployment

- **Local**: `pip install -r requirements.txt`, configure `.env`, `make run` (`python -m src.interface.bot`).
- **Docker**: multi-stage Dockerfile on `python:3.11-slim`; docker-compose mounts `WORKING_DIR` and the agent's home dir (e.g. `~/.kimi-code`, which carries the CLI binary, auth, and sessions), `env_file: .env`.
- **Free cloud**: README covers Oracle Cloud Always Free, Railway, and Wispbyte.
- **Makefile**: `install`, `test`, `run`, `lint`.

## Out of scope (YAGNI)

- Databases (in-memory state).
- Job queue / concurrent runs.
- Persistent agent process.
- Parsing output to detect "proposed changes".
- `!` prefix commands (slash commands + mentions/DMs/replies only).
- Adapters for agents other than kimi (the system supports them; built when needed).
