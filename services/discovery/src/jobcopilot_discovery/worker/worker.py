"""Temporal worker — runs co-located with the FastAPI process."""

import asyncio

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from jobcopilot_discovery.config import settings
from jobcopilot_discovery.worker.activities import (
    deduplicate_activity,
    publish_cookie_expired_activity,
    publish_jobs_activity,
    search_linkedin_activity,
    update_run_status_activity,
    validate_cookie_activity,
)
from jobcopilot_discovery.worker.workflows import DiscoveryWorkflow

log = structlog.get_logger()


async def run_worker() -> None:
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[DiscoveryWorkflow],
        activities=[
            validate_cookie_activity,
            search_linkedin_activity,
            deduplicate_activity,
            publish_jobs_activity,
            publish_cookie_expired_activity,
            update_run_status_activity,
        ],
    )

    log.info("temporal_worker_started", task_queue=settings.temporal_task_queue)
    await worker.run()


def start_worker_background() -> asyncio.Task:  # type: ignore[type-arg]
    """Schedule the Temporal worker as an asyncio background task."""
    return asyncio.create_task(run_worker())
