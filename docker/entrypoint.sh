#!/bin/sh
# Generic container entrypoint: run the per-agent hook, then the bot.
#
# Hooks live in /opt/agent-hooks/<AGENT_TYPE>.sh (mounted from
# ./docker/agents/). A hook sets up whatever the agent CLI needs:
# PATH, env vars, config checks. Adding support for a new agent means
# dropping a <agent>.sh file in docker/agents/ — no rebuild needed
# (the directory is a bind mount), just `docker compose restart`.
set -e

AGENT_TYPE="${AGENT_TYPE:-kimi}"
HOOK="/opt/agent-hooks/${AGENT_TYPE}.sh"

if [ -f "$HOOK" ]; then
    echo "entrypoint: loading agent hook ${HOOK}"
    . "$HOOK"
else
    echo "entrypoint: no hook for AGENT_TYPE=${AGENT_TYPE} (continuing without one)"
fi

exec python -m src.interface.bot
