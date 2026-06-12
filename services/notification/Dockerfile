# Build context: repository root
FROM python:3.11-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/shared ./packages/shared/
COPY services/notification ./services/notification/

RUN uv sync --frozen --package notification-service --no-dev --no-editable --compile-bytecode

# ---- runtime ----
FROM python:3.11-slim

RUN useradd -u 1000 -m appuser
WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY services/notification .

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["uvicorn", "jobcopilot_notification.main:app", "--host", "0.0.0.0", "--port", "8000"]
