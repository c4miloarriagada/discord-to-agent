# Discord Agent Bot

A Discord bot that drives a pluggable coding-agent CLI (Kimi Code first) from your phone or desktop: slash commands to send prompts, approval buttons on every result, session context tracking, and bidirectional messaging — mentions, DMs, and thread replies all act as prompts.

## Features

- Slash commands: `/prompt`, `/status`, `/cancel`, `/clear`
- Approve ✅ / Reject ❌ / Retry 🔄 buttons on every result
- Session resume with context-window usage % in every result footer
- Mentions, DMs, and replies to bot results all act as prompts
- Result messages @mention you so you get a push notification
- Long outputs are attached as `output.md` files
- Plugin architecture — switch agent CLIs with `AGENT_TYPE`
- Security: prompt sanitization, per-user rate limiting, channel/user allowlists, subprocess timeouts, no shell (`exec` argv only)

## Project structure

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
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.11+
- A Discord application/bot (see next section)
- The agent CLI installed and authenticated (e.g. `kimi` — verify with `kimi doctor` or `kimi -p "hi"`)

## Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Open **Bot** → **Reset Token** → copy the token (you'll put it in `.env`).
3. Still under **Bot**, enable the **Message Content** privileged intent — required for mentions, DMs, and replies to work.
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot permissions: Send Messages, Embed Links, Attach Files, Read Message History
5. Open the generated URL to invite the bot to your server.

## Configuration

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `DISCORD_BOT_TOKEN` | *(required)* | Bot token from the Developer Portal |
| `ALLOWED_CHANNEL_IDS` | *(empty = all)* | Comma-separated channel IDs where the bot operates, e.g. `123456789,987654321` |
| `ALLOWED_USER_IDS` | *(empty = all)* | Comma-separated user IDs allowed to use the bot, e.g. `123,456` |
| `WORKING_DIR` | `.` | Working directory the agent CLI runs in (your projects) |
| `AGENT_TYPE` | `kimi` | Agent adapter to use (see the registry in `src/infrastructure/agents/registry.py`) |
| `KIMI_COMMAND` | `kimi` | Path/name of the Kimi Code CLI binary |
| `KIMI_AUTO_APPROVE_FLAG` | `--yolo` | Flag passed when you approve a run |
| `KIMI_SESSIONS_DIR` | `~/.kimi-code/sessions` | Where the CLI stores sessions (used for context %) |
| `KIMI_CONTEXT_WINDOW` | `1048576` | Context window size in tokens (for the % calculation) |
| `PROMPT_TIMEOUT` | `300` | Seconds before a run is killed |
| `RATE_LIMIT_SECONDS` | `10` | Per-user cooldown between prompts |
| `LOG_LEVEL` | `INFO` | Logging level |

Notes:

- `ALLOWED_CHANNEL_IDS` and `ALLOWED_USER_IDS` use **comma-separated** format (`123,456`), not JSON arrays.
- Setting `ALLOWED_USER_IDS` is strongly recommended because the bot accepts DMs from anyone it can see otherwise.
- `.env` is git-ignored — never commit it.

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
make install
make run        # or: python -m src.interface.bot
```

## Run with Docker

```bash
docker compose up -d --build
```

The compose file mounts two volumes:

- `${WORKING_DIR}` — the bot's working directory, i.e. your projects. Mounted at the same path inside the container so agent session paths stay consistent.
- `${HOME}/.kimi-code` → `/root/.kimi-code` — the agent home dir, which carries the CLI binary (`bin/`), credentials, and sessions. The Dockerfile puts `/root/.kimi-code/bin` on `PATH`.

For full agent capabilities (clone, commit, push, GitHub MCP), the image already includes `git`, `gh`, and the `github-mcp-server` binary, and compose additionally mounts:

- `${HOME}/.gitconfig`, `${HOME}/.config/gh`, `${HOME}/.ssh` (read-only) — git identity and GitHub auth.
- `./docker/mcp.json` → `/root/.kimi-code/mcp.json` — a container-specific MCP config that runs `github-mcp-server` as a local process (no docker socket needed). It reads `GITHUB_PERSONAL_ACCESS_TOKEN` from the container environment, so set it in `.env`.

Note: the mounted CLI binary runs inside a Linux container, so it must be Linux-compatible (on macOS hosts, install a Linux build of the CLI into the mounted dir or install the CLI inside the image instead).

## Usage

- `/prompt add a health endpoint to app.py` — run a prompt against the agent CLI
- Mention the bot in an allowed channel, DM it, or reply to one of its results to continue the conversation — all act as prompts
- On every result, press ✅ to re-run the last prompt with auto-approval, ❌ to discard it, or 🔄 to retry it
- `/clear` — clear context; the next prompt starts a fresh session
- `/status` — show the active run and context-window usage %
- `/cancel` — kill the active run

## PR comment notifications (optional)

The bot can poll GitHub and notify you in Discord when someone comments on open PRs in your repos, so you can iterate on reviews with the agent from your phone.

Configuration (`.env`):

| Variable | Description | Default |
|---|---|---|
| `GITHUB_TOKEN` | GitHub PAT with PR read access. If empty, the bot falls back to the token in `~/.kimi-code/mcp.json` (the GitHub MCP server, if configured). | `""` |
| `GITHUB_REPOS` | Comma-separated `owner/repo` list to watch. Feature is disabled when empty. | `[]` |
| `GITHUB_USERNAME` | Your GitHub login; your own comments are not notified. | `""` |
| `GITHUB_POLL_INTERVAL` | Seconds between polls. | `60` |
| `NOTIFY_CHANNEL_ID` | Channel for notifications. Defaults to the first `ALLOWED_CHANNEL_IDS` entry. | unset |

How it works:

- Every `GITHUB_POLL_INTERVAL` seconds the bot lists open PRs in each repo and fetches issue comments, review comments, and reviews newer than the last poll.
- The first poll after startup sets a silent baseline (no spam with old comments).
- Each new comment posts an embed (repo, PR, author, body, link) mentioning the first `ALLOWED_USER_IDS` entry, so your phone pings.
- **Reply to the notification** and your reply becomes a prompt in your session — the agent (which has its own GitHub access via the kimi MCP config) can then fix the PR.

## Adding a new agent adapter

1. Create `src/infrastructure/agents/claude.py` with a `ClaudeAdapter(AgentAdapter)` implementing `name` and `build_command` (`parse_output` and `get_context_percent` hooks are optional).
2. Register it: `AGENT_ADAPTERS["claude"] = ClaudeAdapter.from_settings` in `registry.py`.
3. Set `AGENT_TYPE=claude` in `.env`. Done — services, Discord, and Docker are unchanged.

Minimal example (compiles against the contract in `src/infrastructure/agents/base.py`):

```python
from src.domain.models import Prompt
from src.infrastructure.agents.base import AgentAdapter
from src.infrastructure.config import Settings


class ClaudeAdapter(AgentAdapter):
    def __init__(self, command: str = "claude") -> None:
        self._command = command

    @classmethod
    def from_settings(cls, settings: Settings) -> "ClaudeAdapter":
        return cls()

    @property
    def name(self) -> str:
        return "claude"

    def build_command(self, prompt: Prompt, session_id: str | None) -> list[str]:
        argv = [self._command, "-p", prompt.text]
        if session_id:
            argv.extend(["--resume", session_id])
        return argv
```

Then in `src/infrastructure/agents/registry.py`:

```python
AGENT_ADAPTERS: dict[str, Callable[[Settings], AgentAdapter]] = {
    "kimi": KimiAdapter.from_settings,
    "claude": ClaudeAdapter.from_settings,
}
```

## Free hosting

- **Oracle Cloud Always Free** — ARM VM (up to 4 cores / 24 GB RAM). Install Python and the agent CLI on the VM, then run the bot with systemd or `docker compose up -d`.
- **Railway** — ~$5/mo free credit; deploy straight from the repo with the included Dockerfile.
- **Wispbyte** — free bot hosting; works as long as the plan supports a persistent process (and you can install the agent CLI).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Configuration error: DISCORD_BOT_TOKEN is not set` | Create `.env` from `.env.example` and fill in your bot token |
| Slash commands don't appear | Wait a moment for command sync; re-invite the bot with the `applications.commands` scope |
| Bot ignores mentions/DMs | Enable the **Message Content** privileged intent in the Developer Portal |
| `Unknown AGENT_TYPE '...'` | Check spelling against the registry (`src/infrastructure/agents/registry.py`) |
| Timeout errors | Raise `PROMPT_TIMEOUT` in `.env` |
| Context shows `n/a` | The agent did not report a session — expected on adapters without session support |
| `ALLOWED_CHANNEL_IDS` / `ALLOWED_USER_IDS` not applied | Use comma-separated format (`123,456`), not JSON arrays |
| Agent CLI not found in Docker | Check the mounted agent home dir and that its `bin/` is on `PATH` |

## Development

```bash
make test       # run the test suite
make coverage   # coverage gate: ≥60% on src/application + src/infrastructure
make lint       # ruff check src tests
```

Tests never touch Discord or the real agent CLI — external boundaries are faked, so the suite runs fully offline.
