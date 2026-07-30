#!/bin/sh
# Prepend the mounted agent CLI dir to PATH, then run the bot.
# AGENT_HOME_DIR names the agent's config home (e.g. ".kimi-code", ".claude"),
# mounted at /root/<AGENT_HOME_DIR> by docker-compose.
set -e

AGENT_HOME_DIR="${AGENT_HOME_DIR:-.kimi-code}"
export PATH="/root/${AGENT_HOME_DIR}/bin:${PATH}"
exec python -m src.interface.bot
