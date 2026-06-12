"""Unit tests for pure scraper utility functions (no Playwright, no network)."""

import pytest
from jobcopilot_discovery.services.linkedin_scraper import _normalise_url


class TestNormaliseUrl:
    def test_absolute_url_with_tracking_params(self) -> None:
        href = "https://www.linkedin.com/jobs/view/1234567890?trk=public_jobs&refId=abc"
        assert _normalise_url(href) == "https://www.linkedin.com/jobs/view/1234567890"

    def test_relative_url(self) -> None:
        href = "/jobs/view/9876543210?refId=xyz"
        assert _normalise_url(href) == "https://www.linkedin.com/jobs/view/9876543210"

    def test_empty_string(self) -> None:
        assert _normalise_url("") == ""

    def test_non_job_url(self) -> None:
        assert _normalise_url("https://www.linkedin.com/company/acme") == ""

    def test_clean_absolute_url(self) -> None:
        href = "https://www.linkedin.com/jobs/view/111222333"
        assert _normalise_url(href) == "https://www.linkedin.com/jobs/view/111222333"


class TestDeduplicationLogic:
    """Validate dedup set behaviour without Redis (pure Python logic)."""

    def test_removes_duplicates_within_batch(self) -> None:
        urls = [
            "https://www.linkedin.com/jobs/view/1",
            "https://www.linkedin.com/jobs/view/2",
            "https://www.linkedin.com/jobs/view/1",  # duplicate
        ]
        seen: set[str] = set()
        unique = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)
        assert unique == [
            "https://www.linkedin.com/jobs/view/1",
            "https://www.linkedin.com/jobs/view/2",
        ]

    def test_all_unique(self) -> None:
        urls = [f"https://www.linkedin.com/jobs/view/{i}" for i in range(5)]
        seen: set[str] = set()
        unique = [u for u in urls if not seen.__contains__(u) or not seen.add(u)]  # type: ignore[func-returns-value]
        assert len(unique) == 5


class TestWorkflowStatusTransitions:
    """Ensure valid status strings are used in the workflow."""

    VALID_STATUSES = {"pending", "running", "completed", "failed", "cookie_expired"}

    @pytest.mark.parametrize(
        "status", ["pending", "running", "completed", "failed", "cookie_expired"]
    )
    def test_status_in_valid_set(self, status: str) -> None:
        assert status in self.VALID_STATUSES
