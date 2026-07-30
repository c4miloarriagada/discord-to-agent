# Agent hook for Kimi Code.
# Sourced by docker/entrypoint.sh. AGENT_HOME_DIR comes from the environment
# (default .kimi-code), which docker-compose mounts at /root/<AGENT_HOME_DIR>.

export PATH="/root/${AGENT_HOME_DIR:-.kimi-code}/bin:${PATH}"
