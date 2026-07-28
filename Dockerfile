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
