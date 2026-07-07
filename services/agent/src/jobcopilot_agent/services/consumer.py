"""
RabbitMQ consumer for job.discovered events.

Order matters: the job is upserted in Job Service FIRST so the analysis is
keyed by the real job_id (the MQ payload carries no job_id — see the
Discovery publisher contract). Then AnalyzerGraph runs and the structured
analysis is pushed back onto the job record.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
import httpx

from jobcopilot_agent.config import settings
from jobcopilot_agent.deps import open_db_session
from jobcopilot_agent.services.analysis import run_job_analysis

log = logging.getLogger(__name__)

_EXCHANGE = settings.rabbitmq_exchange
_QUEUE = "agent.job.discovered"
_ROUTING_KEY = "job.discovered"


async def _process_job_message(body: dict[str, Any]) -> None:
    """Upsert the job, run AnalyzerGraph keyed by the real job_id, persist results."""
    user_id = body.get("user_id", "")
    tenant_id = body.get("tenant_id", "")
    url = body.get("url", "")
    if not user_id or not tenant_id or not url:
        log.error(
            "job_message_missing_fields",
            extra={"user_id": user_id, "tenant_id": tenant_id, "url": url},
        )
        return

    # 1. Idempotent upsert in Job Service → authoritative job_id
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.job_service_url}/internal/jobs",
            json={
                "tenant_id": tenant_id,
                "url": url,
                "title": body.get("title", ""),
                "company_name": body.get("company_name", ""),
                "location": body.get("location", ""),
                "raw_jd": body.get("raw_text", ""),
                "source": "discovery",
                "discovered_at": body.get("discovered_at") or datetime.now(tz=UTC).isoformat(),
            },
        )
    if resp.status_code not in (200, 201):
        log.error(
            "job_upsert_failed",
            extra={"status": resp.status_code, "url": url},
        )
        return
    job_id = resp.json()["job_id"]

    # 2. Analyze and persist, keyed by the real job_id
    async with open_db_session() as session:
        outcome = await run_job_analysis(
            session,
            job_id=uuid.UUID(job_id),
            user_id=uuid.UUID(user_id),
            tenant_id=uuid.UUID(tenant_id),
            url=url,
            title=body.get("title", ""),
            company_name=body.get("company_name", ""),
            location=body.get("location", ""),
            raw_text=body.get("raw_text", ""),
        )

    # 3. Push the structured analysis back onto the job record
    if outcome.jd_structured:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{settings.job_service_url}/internal/jobs/{job_id}",
                    json={"analysis": outcome.jd_structured},
                )
        except Exception as exc:
            log.warning("job_analysis_patch_failed", extra={"error": str(exc), "job_id": job_id})

    log.info(
        "job_analyzed",
        extra={
            "job_id": job_id,
            "user_id": user_id,
            "match_score": outcome.match_score,
        },
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
