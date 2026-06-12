"""
RabbitMQ consumer for job.discovered events.

Each message triggers AnalyzerGraph → saves JobAnalysis → notifies Job Service.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import aio_pika
import httpx
from jobcopilot_shared.db import build_engine, build_session_factory

from jobcopilot_agent.config import settings
from jobcopilot_agent.graphs.analyzer_graph import AnalyzerState, analyzer_graph
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository

log = logging.getLogger(__name__)

_EXCHANGE = settings.rabbitmq_exchange
_QUEUE = "agent.job.discovered"
_ROUTING_KEY = "job.discovered"


async def _process_job_message(body: dict[str, Any]) -> None:
    """Run AnalyzerGraph for a single discovered job and persist results."""
    user_id = body.get("user_id", "")
    tenant_id = body.get("tenant_id", "")
    job_id_str = body.get("job_id") or str(uuid.uuid4())

    state: AnalyzerState = {
        "job_id": job_id_str,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "url": body.get("url", ""),
        "title": body.get("title", ""),
        "company_name": body.get("company_name", ""),
        "location": body.get("location", ""),
        "raw_text": body.get("raw_text", ""),
        "resume_text": "",
        "jd_structured": {},
        "skills_required": [],
        "match_score": 0.0,
        "error": None,
    }

    result = await analyzer_graph.ainvoke(state)

    # Persist analysis to DB
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                repo = AnalysisRepository(session)
                analysis = await repo.get_or_create(
                    job_id=uuid.UUID(job_id_str),
                    user_id=uuid.UUID(user_id),
                    tenant_id=uuid.UUID(tenant_id),
                )
                await repo.update_analysis(
                    analysis,
                    jd_structured=result.get("jd_structured"),
                    skills_required=result.get("skills_required"),
                    match_score=result.get("match_score"),
                    status="done" if not result.get("error") else "error",
                    error_message=result.get("error"),
                )
    finally:
        await engine.dispose()

    # Notify Job Service to store the job record
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.job_service_url}/internal/jobs",
                json={
                    "tenant_id": tenant_id,
                    "url": body.get("url", ""),
                    "title": body.get("title", ""),
                    "company_name": body.get("company_name", ""),
                    "location": body.get("location", ""),
                    "raw_jd": body.get("raw_text", ""),
                    "analysis": result.get("jd_structured"),
                    "source": "discovery",
                    "discovered_at": body.get("discovered_at") or datetime.now(tz=UTC).isoformat(),
                },
            )
    except Exception as exc:
        log.warning("job_service_notify_failed", extra={"error": str(exc), "url": body.get("url")})

    log.info(
        "job_analyzed",
        extra={
            "job_id": job_id_str,
            "user_id": user_id,
            "match_score": result.get("match_score"),
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
