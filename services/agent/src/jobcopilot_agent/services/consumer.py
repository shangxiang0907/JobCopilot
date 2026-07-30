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
from jobcopilot_shared.metrics import record_degradation
from pydantic import ValidationError

from jobcopilot_agent.config import settings

log = logging.getLogger(__name__)

_EXCHANGE = settings.rabbitmq_exchange
_QUEUE = "agent.job.discovered"
_ROUTING_KEY = JOB_DISCOVERED_KEY


class TransientIngestError(Exception):
    """Ingest failed for a reason a redelivery could plausibly fix.

    Separated from poison messages on purpose: a malformed payload will fail
    identically forever and must be dropped, while a Job Service restart must
    NOT cost the user the jobs a discovery run just found.
    """


async def _process_job_message(body: dict[str, Any]) -> None:
    """Idempotently upsert the discovered job in Job Service. No LLM calls.

    Returns normally when the message is poison (already logged and counted —
    redelivery cannot help), raises TransientIngestError when a retry might.
    """
    try:
        event = JobDiscoveredEvent.model_validate(body)
    except ValidationError as exc:
        log.error("job_message_invalid", extra={"error": str(exc)})
        record_degradation(operation="job_ingest", reason="invalid_payload")
        return
    if not event.user_id or not event.tenant_id or not event.url:
        log.error(
            "job_message_missing_fields",
            extra={"user_id": event.user_id, "tenant_id": event.tenant_id, "url": event.url},
        )
        record_degradation(operation="job_ingest", reason="missing_fields")
        return

    try:
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
    except httpx.HTTPError as exc:
        # The Job Service is down or unreachable. This used to be swallowed by
        # the blanket handler below and acked, so the job vanished between a
        # discovery run reporting "42 found" and 41 appearing in the library.
        raise TransientIngestError(f"job service unreachable: {exc}") from exc

    if resp.status_code >= 500:
        raise TransientIngestError(f"job service returned {resp.status_code}")
    if resp.status_code not in (200, 201):
        # A 4xx means this specific payload is unacceptable — retrying it would
        # fail the same way, so it is dropped, loudly.
        log.error("job_upsert_rejected", extra={"status": resp.status_code, "url": event.url})
        record_degradation(operation="job_ingest", reason="upsert_rejected")
        return

    log.info(
        "job_ingested",
        extra={"job_id": resp.json()["job_id"], "user_id": event.user_id, "url": event.url},
    )


async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Ack only what was actually handled.

    The previous version wrapped everything in `message.process()` and caught
    every exception inside it, so a failed ingest was acknowledged exactly like
    a successful one: the message was gone, the job was not in the library, and
    the only trace was one log line with no metric behind it.
    """
    try:
        body = json.loads(message.body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.error("job_message_undecodable", extra={"error": str(exc)})
        record_degradation(operation="job_ingest", reason="undecodable_payload")
        await message.ack()
        return

    try:
        await _process_job_message(body)
    except TransientIngestError as exc:
        # Retried exactly once. RabbitMQ redelivery is unbounded by default, and
        # a permanently-down dependency would otherwise spin this queue hot.
        if message.redelivered:
            log.error("job_ingest_dropped_after_retry", extra={"error": str(exc)})
            record_degradation(operation="job_ingest", reason="dropped_after_retry")
            await message.reject(requeue=False)
        else:
            log.warning("job_ingest_requeued", extra={"error": str(exc)})
            record_degradation(operation="job_ingest", reason="requeued")
            await message.reject(requeue=True)
        return
    except Exception as exc:
        # Unknown failure: not provably retryable, so drop rather than risk a
        # loop — but count it, because this is the branch that means "the
        # consumer has a bug nobody has classified yet".
        log.exception("job_ingest_unexpected_error", extra={"error": str(exc)})
        record_degradation(operation="job_ingest", reason="unexpected_error")
        await message.reject(requeue=False)
        return

    await message.ack()


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
