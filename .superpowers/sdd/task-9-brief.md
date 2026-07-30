### Task 9: Packaging, docs, and coverage gate

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: Docker deployment and user documentation. Final gate: full test suite + coverage ≥ 60% on `src/application` and `src/infrastructure`.

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/
# The agent CLI is provided by mounting the host's agent home dir (see docker-compose.yml).
ENV PATH="/root/.kimi-code/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.interface.bot"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  bot:
    build: .
    env_file: .env
    volumes:
      # The bot's working directory (your projects).
      - ${WORKING_DIR:-.}:${WORKING_DIR:-.}
      # The agent CLI binary, credentials and sessions (kimi example).
      - ${HOME}/.kimi-code:/root/.kimi-code
    restart: unless-stopped
```

- [ ] **Step 3: Write `README.md`**

Write the full README with these sections (match the structure below; keep it accurate to the code):

1. **Title + one-paragraph description** — Discord bot to drive a pluggable coding-agent CLI (Kimi Code first) from your phone: slash commands, approval buttons, session context tracking, bidirectional messaging.
2. **Features** — bullets: `/prompt` `/status` `/cancel` `/clear`; Approve ✅ / Reject ❌ / Retry 🔄 on every result; session resume with context % in every result footer; mentions, DMs, and replies act as prompts; result messages @mention you; long outputs attached as `output.md`; plugin architecture (`AGENT_TYPE`); security: sanitization, rate limit, channel/user allowlists, subprocess timeouts, no shell.
3. **Project structure** — the tree from the spec.
4. **Prerequisites** — Python 3.11+, a Discord application/bot, the agent CLI installed and authenticated (e.g. `kimi` — verify with `kimi doctor` or `kimi -p "hi"`).
5. **Create the Discord bot** — step by step: Discord Developer Portal → New Application → Bot → Reset Token → copy token; **enable the "Message Content" privileged intent** (required for mentions/DMs/replies); OAuth2 → URL Generator → scopes `bot` + `applications.commands`, bot permissions: Send Messages, Embed Links, Attach Files, Read Message History → open the URL to invite.
6. **Configuration** — `cp .env.example .env`, table of every variable with defaults; note `ALLOWED_USER_IDS` is strongly recommended because DMs are accepted; `.env` is git-ignored, never commit it.
7. **Run locally** — `python3.11 -m venv .venv && source .venv/bin/activate`, `make install`, `make run` (or `python -m src.interface.bot`).
8. **Run with Docker** — `docker compose up -d --build`; explain the two mounted volumes (`WORKING_DIR` and the agent home dir carrying the CLI binary + auth + sessions); note the mounted CLI binary must be Linux-compatible.
9. **Usage** — examples: `/prompt add a health endpoint to app.py`; mention the bot in an allowed channel; DM it; reply to one of its results to continue; press ✅ to re-run with auto-approval, ❌ to discard, 🔄 to retry; `/clear` to start a fresh session; `/status` to see the active run and context %; `/cancel` to kill the active run.
10. **Adding a new agent adapter** — the 3-step flow from the spec, with a minimal `ClaudeAdapter` code sketch implementing `name` and `build_command`, and the registry line.
11. **Free hosting** — short notes for Oracle Cloud Always Free (ARM VM, install Python + agent CLI, run with systemd or docker), Railway ($5/mo credit, deploy from repo), Wispbyte (free bot hosting; needs persistent process support).
12. **Troubleshooting** — table: "Configuration error: DISCORD_BOT_TOKEN is not set" → create `.env`; commands not appearing → wait for sync / re-invite with `applications.commands` scope; bot ignores mentions/DMs → enable Message Content intent; "Unknown AGENT_TYPE" → check spelling against the registry; timeout errors → raise `PROMPT_TIMEOUT`; context shows `n/a` → agent did not report a session (expected on adapters without session support); agent CLI not found in Docker → check the mounted home dir and `PATH`.
13. **Development** — `make test`, `make coverage` (≥60% gate on `application/` + `infrastructure/`), `make lint`; note tests never touch Discord or the real agent CLI.

- [ ] **Step 4: Run the full suite with coverage**

Run: `.venv/bin/pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60`
Expected: all tests pass, coverage ≥ 60%, exit code 0

- [ ] **Step 5: Run the linter and fix any findings**

Run: `.venv/bin/ruff check src tests`
Expected: no errors (fix and re-run if any)

- [ ] **Step 6: Verify Docker build (if docker is available)**

Run: `docker build -t discord-agent-bot .`
Expected: build succeeds. If docker is not installed, skip and note it in the final report.

- [ ] **Step 7: Final commit**

```bash
git add Dockerfile docker-compose.yml README.md docs/superpowers/plans/2026-07-26-discord-agent-bot.md
git commit -m "feat: docker packaging and readme"
```
