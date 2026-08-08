# syntax=docker/dockerfile:1
# Stage 1: build — install deps with uv
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install uv --quiet

COPY pyproject.toml .
COPY agent/ agent/

RUN uv sync --no-dev

# Stage 2: final — minimal runtime image
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Context Drift Agent" \
      org.opencontainers.image.description="AI agent that detects stale metadata context in DataHub after schema changes" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/agent /app/agent

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    DATAHUB_GMS_URL="http://localhost:8080" \
    LLM_PROVIDER="anthropic" \
    LLM_MODEL="claude-sonnet-4-6"

ENTRYPOINT ["python", "-m", "agent"]
