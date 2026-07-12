"""RemoteOK — official public API for remote jobs.

API: https://remoteok.com/api (no auth). ToS asks for a link back to the
job's URL, which we keep as the job's canonical `url`. The first array
element is a legal notice, not a job.
"""

import httpx

from jobcopilot_discovery.sources.base import (
    PER_SOURCE_LIMIT,
    RawJob,
    SearchCriteria,
    matches_keywords,
    matches_location,
    strip_html,
)

API_URL = "https://remoteok.com/api"


async def fetch_remoteok(client: httpx.AsyncClient, criteria: SearchCriteria) -> list[RawJob]:
    resp = await client.get(API_URL)
    resp.raise_for_status()
    payload = resp.json()

    jobs: list[RawJob] = []
    for item in payload:
        if not isinstance(item, dict) or "position" not in item:
            continue  # legal-notice element and any malformed entries
        title = item.get("position", "")
        tags = " ".join(item.get("tags", []) or [])
        description = strip_html(item.get("description", ""))
        location = item.get("location", "")
        if not matches_keywords(criteria, title, tags, description):
            continue
        if not matches_location(criteria, location):
            continue
        jobs.append(
            RawJob(
                url=item.get("url", ""),
                title=title,
                company_name=item.get("company", ""),
                location=location,
                posted_snippet=str(item.get("date", "")),
                raw_text=description,
                source="remoteok",
            )
        )
        if len(jobs) >= PER_SOURCE_LIMIT:
            break
    return [j for j in jobs if j.url and j.title]
