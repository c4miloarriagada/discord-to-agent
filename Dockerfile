# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
# git: clone/push repos. openssh-client: SSH remotes. gh: GitHub auth
# (installed to /usr/bin/gh to match the host .gitconfig credential helper).
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client ca-certificates curl \
 && curl -fsSL https://github.com/cli/cli/releases/download/v2.62.0/gh_2.62.0_linux_amd64.tar.gz \
    | tar xz -C /usr/bin --strip-components=2 gh_2.62.0_linux_amd64/bin/gh \
 && curl -fsSL https://github.com/github/github-mcp-server/releases/download/v1.8.0/github-mcp-server_Linux_x86_64.tar.gz \
    | tar xz -C /usr/local/bin github-mcp-server \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY src/ ./src/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
# The agent CLI is provided by mounting the host's agent home dir
# (AGENT_HOME_DIR, e.g. .kimi-code) — see docker-compose.yml and entrypoint.sh.
ENV PYTHONUNBUFFERED=1
CMD ["entrypoint.sh"]
