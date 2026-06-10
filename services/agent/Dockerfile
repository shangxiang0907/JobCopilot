FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files needed for the shared package
COPY packages/shared /workspace/packages/shared
COPY pyproject.toml uv.lock* /workspace/

COPY services/agent/pyproject.toml /app/

RUN cd /workspace && uv pip install --system /workspace/packages/shared
RUN uv pip install --system -r /app/pyproject.toml --no-deps || true
RUN cd /app && uv pip install --system .

COPY services/agent/ /app/

RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/healthz/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
