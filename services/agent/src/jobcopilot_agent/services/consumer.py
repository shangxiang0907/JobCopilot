"""
RabbitMQ consumer for job.discovered events.

Ingest is LLM-free (owner decision, 2026-07-13): the consumer only upserts
the job in Job Service (idempotent by URL — the MQ payload carries no job_id,
see the Discovery publisher contract). AnalyzerGraph runs ON DEMAND — when the
user opens the job, clicks analyze, or asks the assistant — never on ingest:
a public-source discovery run yields 100+ jobs and auto-analysis at 2 LLM
calls each made every run a token bomb.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import aio_pika
import httpx
from jobcopilot_shared.events import JOB_DISCOVERED_KEY, JobDiscoveredEvent
from pydantic import ValidationError

from jobcopilot_agent.config import settings

log = logging.getLogger(__name__)

_EXCHANGE = settings.rabbitmq_exchange
_QUEUE = "agent.job.discovered"
_ROUTING_KEY = JOB_DISCOVERED_KEY


async def _process_job_message(body: dict[str, Any]) -> None:
    """Idempotently upsert the discovered job in Job Service. No LLM calls."""
    try:
        event = JobDiscoveredEvent.model_validate(body)
    except ValidationError as exc:
        # Poison message — drop it (redelivery would fail identically).
        log.error("job_message_invalid", extra={"error": str(exc)})
        return
    if not event.user_id or not event.tenant_id or not event.url:
        log.error(
            "job_message_missing_fields",
            extra={"user_id": event.user_id, "tenant_id": event.tenant_id, "url": event.url},
        )
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.job_service_url}/internal/jobs",
            json={
                "tenant_id": event.tenant_id,
                "url": event.url,
                "title": event.title,
                "company_name": event.company_name,
                "location": event.location,
                "raw_jd": event.raw_text,
                "source": "discovery",
                "discovered_at": event.discovered_at or datetime.now(tz=UTC).isoformat(),
            },
        )
    if resp.status_code not in (200, 201):
        log.error(
            "job_upsert_failed",
            extra={"status": resp.status_code, "url": event.url},
        )
        return

    log.info(
        "job_ingested",
        extra={"job_id": resp.json()["job_id"], "user_id": event.user_id, "url": event.url},
    )


async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        try:
            body = json.loads(message.body.decode())
            await _process_job_message(body)
        except Exception as exc:
            log.error("consumer_message_failed", extra={"error": str(exc)})


async def start_consumer() -> None:
    """Connect to RabbitMQ and start consuming job.discovered messages."""
    while True:
        try:
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=5)

                exchange = await channel.declare_exchange(
                    _EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
                )
                queue = await channel.declare_queue(_QUEUE, durable=True)
                await queue.bind(exchange, routing_key=_ROUTING_KEY)

                log.info("consumer_started", extra={"queue": _QUEUE})
                await queue.consume(_on_message)

                # Keep alive until connection closes
                await asyncio.Future()
        except Exception as exc:
            log.error("consumer_connection_lost", extra={"error": str(exc)})
            await asyncio.sleep(5)


def start_consumer_background() -> asyncio.Task[None]:
    return asyncio.ensure_future(start_consumer())
