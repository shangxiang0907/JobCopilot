# Build context: repository root
FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/shared ./packages/shared/
COPY services/discovery ./services/discovery/

RUN uv sync --frozen --package discovery-service --no-dev --no-editable --compile-bytecode

# Download Chromium to a fixed path (independent of which user runs the container)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN /app/.venv/bin/playwright install chromium

# ---- runtime ----
FROM python:3.14-slim

# Runtime system libs required by Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m appuser
WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY --from=build /opt/playwright /opt/playwright
COPY services/discovery .

ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# Git revision baked in by CD (build-arg; also stamped as OCI label
# org.opencontainers.image.revision). Surfaced via /healthz `revision`, the
# jobcopilot_build_info metric, and deploy.sh post-deploy verification.
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["uvicorn", "jobcopilot_discovery.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
