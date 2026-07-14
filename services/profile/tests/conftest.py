import os

# Set required env vars before any service modules are imported (deps.py builds
# the engine at import time). Integration tests override via the real env.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)
