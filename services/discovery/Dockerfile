# Build context: repository root
FROM python:3.11-slim AS build

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY packages/shared /build/packages/shared
RUN uv pip install --system --no-cache /build/packages/shared

COPY services/discovery /build/services/discovery
RUN uv pip install --system --no-cache /build/services/discovery

# Install Playwright and Chromium browser
RUN playwright install --with-deps chromium

# ---- runtime ----
FROM python:3.11-slim

# Install runtime deps for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m appuser

WORKDIR /app

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=build /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

COPY services/discovery /app

RUN chown -R appuser:appuser /home/appuser/.cache

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
