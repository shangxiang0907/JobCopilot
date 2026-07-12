"""MQ event contract guards — required fields must stay required.

Both publisher and consumer import these models, so drift is structurally
impossible; these tests guard against accidentally relaxing required fields
(the original 2026-07 incident was a missing tenant_id in an event payload).
"""

import pytest
from jobcopilot_shared.events import (
    JobDiscoveredEvent,
    NotificationTriggerEvent,
)
from pydantic import ValidationError


def test_job_discovered_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        JobDiscoveredEvent(user_id="u", tenant_id="t", run_id="r")  # type: ignore[call-arg]
    event = JobDiscoveredEvent(
        user_id="u",
        tenant_id="t",
        run_id="r",
        url="https://example.com/j/1",
        title="Engineer",
        company_name="Acme",
    )
    # Consumers rely on these defaults instead of .get() fallbacks
    assert event.location == ""
    assert event.raw_text == ""


def test_notification_trigger_defaults() -> None:
    event = NotificationTriggerEvent(user_id="u", tenant_id="t")
    assert event.channels == ["in_app"]
    assert event.type == "custom"
