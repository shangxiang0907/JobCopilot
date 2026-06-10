# Build context: repository root
FROM python:3.11-slim AS build

WORKDIR /build

RUN pip install --no-cache-dir uv

# Install shared package
COPY packages/shared /build/packages/shared
RUN uv pip install --system --no-cache /build/packages/shared

# Install service
COPY services/job /build/services/job
RUN uv pip install --system --no-cache /build/services/job

# ---- runtime ----
FROM python:3.11-slim

RUN useradd -u 1000 -m appuser

WORKDIR /app

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin/uvicorn /usr/local/bin/uvicorn

COPY services/job /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
