"""RabbitMQ publisher using aio-pika."""

import json
from datetime import UTC, datetime
from typing import Any

import aio_pika

from jobcopilot_discovery.config import settings

_EXCHANGE = settings.rabbitmq_exchange


async def _get_connection() -> aio_pika.abc.AbstractConnection:
    return await aio_pika.connect_robust(settings.rabbitmq_url)


async def publish_jobs_discovered(
    jobs: list[dict[str, Any]],
    user_id: str,
    tenant_id: str,
    run_id: str,
) -> int:
    """
    Publish each job as a separate message to the job.discovered routing key.
    Returns the number of messages published.
    """
    connection = await _get_connection()
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )

        count = 0
        for job in jobs:
            payload = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "url": job["url"],
                "title": job["title"],
                "company_name": job["company_name"],
                "location": job["location"],
                "raw_text": job.get("raw_text", ""),
                "discovered_at": datetime.now(tz=UTC).isoformat(),
            }
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="job.discovered",
            )
            count += 1

    return count


async def publish_cookie_expired(user_id: str, run_id: str) -> None:
    """Publish a cookie.expired event so Notification Service can alert the user."""
    connection = await _get_connection()
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        payload = {
            "user_id": user_id,
            "run_id": run_id,
            "occurred_at": datetime.now(tz=UTC).isoformat(),
        }
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="cookie.expired",
        )
