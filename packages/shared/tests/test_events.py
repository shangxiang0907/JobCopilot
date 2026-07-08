"""MQ event contract guards — required fields must stay required.

Both publisher and consumer import these models, so drift is structurally
impossible; these tests guard against accidentally relaxing required fields
(the original cookie.expired bug was a missing tenant_id).
"""

import pytest
from jobcopilot_shared.events import (
    CookieExpiredEvent,
    JobDiscoveredEvent,
    NotificationTriggerEvent,
)
from pydantic import ValidationError


def test_cookie_expired_requires_identity() -> None:
    with pytest.raises(ValidationError):
        CookieExpiredEvent(user_id="u", run_id="r")  # type: ignore[call-arg]
    event = CookieExpiredEvent(user_id="u", tenant_id="t", run_id="r")
    assert event.occurred_at is None


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
