"""Integration tests: Redis and RabbitMQ connectivity via shared utilities."""

import os

import aio_pika
import pytest

from jobcopilot_shared.redis_client import build_redis


@pytest.mark.integration
async def test_redis_set_get_delete() -> None:
    redis = build_redis(os.environ["REDIS_URL"])
    try:
        await redis.set("jobcopilot:test:ping", "pong", ex=10)
        value = await redis.get("jobcopilot:test:ping")
        assert value == "pong"
        await redis.delete("jobcopilot:test:ping")
        assert await redis.get("jobcopilot:test:ping") is None
    finally:
        await redis.aclose()


@pytest.mark.integration
async def test_rabbitmq_connectivity() -> None:
    connection = await aio_pika.connect_robust(os.environ["RABBITMQ_URL"])
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "jobcopilot.test", aio_pika.ExchangeType.TOPIC, durable=False, auto_delete=True
        )
        assert exchange.name == "jobcopilot.test"
