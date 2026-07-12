"""
Shared MQ event contracts.

Publishers construct these models and consumers validate incoming payloads
with them, so payload drift between services is impossible without editing
this file — the single source of truth for every RabbitMQ routing key.
"""

from typing import Any

from pydantic import BaseModel, Field

JOB_DISCOVERED_KEY = "job.discovered"
NOTIFICATION_TRIGGER_KEY = "notification.trigger"


class JobDiscoveredEvent(BaseModel):
    """One discovered job posting. Carries NO job_id — the consumer upserts the
    job in Job Service first (idempotent by URL) and keys records by the
    returned job_id."""

    user_id: str
    tenant_id: str
    run_id: str
    url: str
    title: str
    company_name: str
    location: str = ""
    raw_text: str = ""
    discovered_at: str | None = None


class NotificationTriggerEvent(BaseModel):
    """Generic notification request forwarded to the dispatcher."""

    user_id: str
    tenant_id: str
    type: str = "custom"
    title: str = "JobCopilot Notification"
    body: str = ""
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    metadata: dict[str, Any] | None = None
