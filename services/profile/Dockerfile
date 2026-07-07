# Build context: repository root
FROM python:3.11-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/shared ./packages/shared/
COPY services/profile ./services/profile/

RUN uv sync --frozen --package profile-service --no-dev --no-editable --compile-bytecode

# ---- runtime ----
FROM python:3.11-slim

RUN useradd -u 1000 -m appuser
# Resume storage mount point — must exist appuser-owned BEFORE the named volume
# is first mounted: Docker copies this ownership into a fresh volume, and the
# container runs non-root so it cannot chown at runtime.
RUN mkdir -p /data/resumes && chown -R appuser:appuser /data
WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY services/profile .

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"
# Required for correct metrics with --workers 2: each uvicorn worker is a
# separate process, so /metrics must aggregate via the multiprocess registry.
ENV PROMETHEUS_MULTIPROC_DIR="/tmp/prometheus-metrics"

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["uvicorn", "jobcopilot_profile.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
