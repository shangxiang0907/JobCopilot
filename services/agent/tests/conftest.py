import os

# Set required env vars before any service modules are imported
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)
