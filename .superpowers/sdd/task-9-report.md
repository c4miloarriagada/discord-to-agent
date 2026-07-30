# Task 9 Report: Packaging, docs, and coverage gate

## Files created

- `Dockerfile` — exact content from the brief (multi-stage `python:3.11-slim`, installs requirements into `/install`, copies `src/`, `PATH` includes `/root/.kimi-code/bin`, `CMD python -m src.interface.bot`).
- `docker-compose.yml` — exact content from the brief (env_file `.env`, mounts `WORKING_DIR` and `~/.kimi-code` → `/root/.kimi-code`, `restart: unless-stopped`).
- `README.md` — all 13 sections from the brief: title/description, features, project structure (tree from the spec), prerequisites, Discord bot creation steps (incl. Message Content intent), configuration, run locally, run with Docker, usage, adding a new agent adapter, free hosting, troubleshooting, development.

### README accuracy points incorporated (from review findings)

- `ALLOWED_CHANNEL_IDS` / `ALLOWED_USER_IDS` documented as **comma-separated** (`123,456`), not JSON arrays — both in the config table notes and the troubleshooting table. Matches `Settings._split_ids` in `src/infrastructure/config.py`.
- Config table built directly from `src/infrastructure/config.py` — all 12 fields with real defaults (`kimi`, `kimi`, `--yolo`, `~/.kimi-code/sessions`, `1048576`, `300`, `10`, `INFO`, etc.).
- Slash commands match `src/interface/commands.py`: `/prompt` `/status` `/cancel` `/clear`.
- Troubleshooting table includes: enabling the Message Content privileged intent; "Unknown AGENT_TYPE" → check the registry; Context `n/a` meaning (agent reported no session — expected on adapters without session support); comma-separated ID format.
- "Adding a new agent adapter" follows the real `AgentAdapter` contract in `src/infrastructure/agents/base.py` (`name` property, `build_command(prompt, session_id)`, optional `from_settings`) and `registry.py`. The `ClaudeAdapter` sketch was extracted and executed against the real code: instantiates, `build_command` returns `['claude', '-p', 'hi', '--resume', 'sess-1']`, and `isinstance(a, AgentAdapter)` is `True`.

## Gate results

1. **Coverage**: `.venv/bin/pytest --cov=src/application --cov=src/infrastructure --cov-report=term-missing --cov-fail-under=60` → **66 passed**, exit 0. Total coverage **93.02%** (application 98–100%, infrastructure 75–100%; lowest: `discord_adapter.py` 75%).
2. **Lint**: `.venv/bin/ruff check src tests` → "All checks passed!", exit 0.
3. **Docker**: docker was available (`/usr/local/bin/docker`). `docker build -t discord-agent-bot .` → **succeeded** (exit 0), image `discord-agent-bot:latest` created.

## Commit

- `61a1b0b feat: docker packaging and readme` on `feat/discord-agent-bot` — Dockerfile, docker-compose.yml, README.md (the plan file `docs/superpowers/plans/2026-07-26-discord-agent-bot.md` was already tracked and unmodified, so only 3 files changed).

## Concerns

- None blocking. Minor notes:
  - Only one harmless deprecation warning in tests (`audioop` deprecation from discord.py on Python 3.13; irrelevant on 3.11).
  - The compose volume `${HOME}/.kimi-code` assumes a Linux host with a Linux-compatible CLI binary, as documented in the README.
  - `.superpowers/` remains untracked, as in previous tasks.
