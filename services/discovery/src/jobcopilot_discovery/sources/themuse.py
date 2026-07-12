"""The Muse — official public API, broad multi-industry coverage.

Docs: https://www.themuse.com/developers/api/v2 (public tier needs no key;
`location` is supported server-side, keywords are filtered locally).
"""

import httpx

from jobcopilot_discovery.sources.base import (
    PER_SOURCE_LIMIT,
    RawJob,
    SearchCriteria,
    matches_keywords,
    strip_html,
)

API_URL = "https://www.themuse.com/api/public/jobs"
_MAX_PAGES = 3  # 20 jobs/page upstream


async def fetch_themuse(client: httpx.AsyncClient, criteria: SearchCriteria) -> list[RawJob]:
    jobs: list[RawJob] = []
    for page in range(1, _MAX_PAGES + 1):
        params: list[tuple[str, str | int | float | bool | None]] = [("page", page)]
        for loc in criteria.locations:
            if loc.strip():
                params.append(("location", loc.strip()))

        resp = await client.get(API_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("results", [])
        if not results:
            break

        for item in results:
            title = item.get("name", "")
            contents = strip_html(item.get("contents", ""))
            if not matches_keywords(criteria, title, contents):
                continue
            locations = ", ".join(loc.get("name", "") for loc in item.get("locations", []))
            jobs.append(
                RawJob(
                    url=(item.get("refs") or {}).get("landing_page", ""),
                    title=title,
                    company_name=(item.get("company") or {}).get("name", ""),
                    location=locations,
                    posted_snippet=item.get("publication_date", ""),
                    raw_text=contents,
                    source="themuse",
                )
            )
            if len(jobs) >= PER_SOURCE_LIMIT:
                return [j for j in jobs if j.url and j.title]
    return [j for j in jobs if j.url and j.title]
