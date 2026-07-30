# Agent hook for Claude Code (example — adjust to your installation).
# Sourced by docker/entrypoint.sh when AGENT_TYPE=claude.
# docker-compose mounts AGENT_HOME_DIR (e.g. .claude) at /root/<AGENT_HOME_DIR>.

export PATH="/root/${AGENT_HOME_DIR:-.claude}/bin:${PATH}"

# If the agent needs specific env vars, set them here, e.g.:
# export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
