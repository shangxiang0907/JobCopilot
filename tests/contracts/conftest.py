"""Environment defaults so service apps import offline (engines are lazy)."""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://placeholder:placeholder@localhost:5432/placeholder"
)
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("DASHSCOPE_API_KEY", "placeholder")
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
