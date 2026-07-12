"""Hacker News "Ask HN: Who is hiring?" — via the open Algolia HN API.

Monthly thread by the `whoishiring` bot; each top-level comment is one job
post in free text (convention: "Company | Role | Location | ..."). The text
is unstructured by design — the downstream AnalyzerGraph LLM extraction is
what turns it into structured JD data.
"""

import httpx

from jobcopilot_discovery.sources.base import (
    PER_SOURCE_LIMIT,
    RawJob,
    SearchCriteria,
    matches_keywords,
    strip_html,
)

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{item_id}"


async def fetch_hn_whoishiring(client: httpx.AsyncClient, criteria: SearchCriteria) -> list[RawJob]:
    resp = await client.get(
        SEARCH_URL,
        params={
            "query": "Ask HN: Who is hiring?",
            "tags": "story,author_whoishiring",
            "hitsPerPage": 1,
        },
    )
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    if not hits:
        return []
    story_id = hits[0]["objectID"]

    resp = await client.get(ITEM_URL.format(item_id=story_id))
    resp.raise_for_status()
    children = resp.json().get("children", [])

    jobs: list[RawJob] = []
    for child in children:
        text = strip_html(child.get("text") or "")
        if not text:
            continue
        if not matches_keywords(criteria, text):
            continue
        first_line = text.splitlines()[0]
        # Thread convention: "Company | Role | Location | ..."
        parts = [p.strip() for p in first_line.split("|")]
        company = parts[0][:120] if parts else ""
        title = parts[1][:200] if len(parts) > 1 else first_line[:200]
        jobs.append(
            RawJob(
                url=f"https://news.ycombinator.com/item?id={child.get('id')}",
                title=title or "Untitled posting",
                company_name=company or "Unknown (HN)",
                location=parts[2][:120] if len(parts) > 2 else "",
                posted_snippet=child.get("created_at", ""),
                raw_text=text,
                source="hn_whoishiring",
            )
        )
        if len(jobs) >= PER_SOURCE_LIMIT:
            break
    return jobs
