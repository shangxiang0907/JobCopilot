"""Remotive — official public API for remote jobs.

Docs: https://remotive.com/api/remote-jobs (no auth; `search` server-side).
"""

import httpx

from jobcopilot_discovery.sources.base import (
    PER_SOURCE_LIMIT,
    RawJob,
    SearchCriteria,
    matches_location,
    strip_html,
)

API_URL = "https://remotive.com/api/remote-jobs"


async def fetch_remotive(client: httpx.AsyncClient, criteria: SearchCriteria) -> list[RawJob]:
    params: dict[str, str | int] = {"limit": PER_SOURCE_LIMIT}
    if criteria.keywords:
        params["search"] = " ".join(criteria.keywords)

    resp = await client.get(API_URL, params=params)
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[RawJob] = []
    for item in payload.get("jobs", []):
        location = item.get("candidate_required_location", "")
        if not matches_location(criteria, location):
            continue
        jobs.append(
            RawJob(
                url=item.get("url", ""),
                title=item.get("title", ""),
                company_name=item.get("company_name", ""),
                location=location,
                posted_snippet=item.get("publication_date", ""),
                raw_text=strip_html(item.get("description", "")),
                source="remotive",
            )
        )
    return [j for j in jobs if j.url and j.title][:PER_SOURCE_LIMIT]
