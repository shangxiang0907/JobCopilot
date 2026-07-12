"""Greenhouse / Lever public company job boards.

Users paste board URLs into their DiscoveryConfig (`company_boards`); each URL
is polled on every run. Both ATS vendors expose the full board as public JSON:

  Greenhouse: https://boards.greenhouse.io/{token}
              → https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
  Lever:      https://jobs.lever.co/{token}
              → https://api.lever.co/v0/postings/{token}?mode=json
"""

import re

import httpx

from jobcopilot_discovery.sources.base import (
    PER_SOURCE_LIMIT,
    RawJob,
    SearchCriteria,
    matches_keywords,
    strip_html,
)

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
GREENHOUSE_META_API = "https://boards-api.greenhouse.io/v1/boards/{token}"
LEVER_API = "https://api.lever.co/v0/postings/{token}"

_GREENHOUSE_RE = re.compile(
    r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)"
)
_LEVER_RE = re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)")


def parse_board_url(url: str) -> tuple[str, str] | None:
    """Return (provider, token) for a recognized board URL, else None."""
    if m := _GREENHOUSE_RE.search(url):
        return ("greenhouse", m.group(1))
    if m := _LEVER_RE.search(url):
        return ("lever", m.group(1))
    return None


async def fetch_company_board(
    client: httpx.AsyncClient, board_url: str, criteria: SearchCriteria
) -> list[RawJob]:
    parsed = parse_board_url(board_url)
    if parsed is None:
        raise ValueError(f"unrecognized board URL (need Greenhouse or Lever): {board_url}")
    provider, token = parsed
    if provider == "greenhouse":
        return await _fetch_greenhouse(client, token, criteria)
    return await _fetch_lever(client, token, criteria)


async def _fetch_greenhouse(
    client: httpx.AsyncClient, token: str, criteria: SearchCriteria
) -> list[RawJob]:
    meta_resp = await client.get(GREENHOUSE_META_API.format(token=token))
    company = meta_resp.json().get("name", token) if meta_resp.status_code == 200 else token

    resp = await client.get(GREENHOUSE_API.format(token=token), params={"content": "true"})
    resp.raise_for_status()

    jobs: list[RawJob] = []
    for item in resp.json().get("jobs", []):
        title = item.get("title", "")
        content = strip_html(item.get("content", ""))
        if not matches_keywords(criteria, title, content):
            continue
        jobs.append(
            RawJob(
                url=item.get("absolute_url", ""),
                title=title,
                company_name=company,
                location=(item.get("location") or {}).get("name", ""),
                posted_snippet=item.get("updated_at", ""),
                raw_text=content,
                source=f"greenhouse:{token}",
            )
        )
        if len(jobs) >= PER_SOURCE_LIMIT:
            break
    return [j for j in jobs if j.url and j.title]


async def _fetch_lever(
    client: httpx.AsyncClient, token: str, criteria: SearchCriteria
) -> list[RawJob]:
    resp = await client.get(LEVER_API.format(token=token), params={"mode": "json"})
    resp.raise_for_status()

    jobs: list[RawJob] = []
    for item in resp.json():
        title = item.get("text", "")
        description = item.get("descriptionPlain") or strip_html(item.get("description", ""))
        if not matches_keywords(criteria, title, description):
            continue
        categories = item.get("categories") or {}
        jobs.append(
            RawJob(
                url=item.get("hostedUrl", ""),
                title=title,
                company_name=token.replace("-", " ").title(),
                location=categories.get("location", ""),
                posted_snippet=str(item.get("createdAt", "")),
                raw_text=description[:8000],
                source=f"lever:{token}",
            )
        )
        if len(jobs) >= PER_SOURCE_LIMIT:
            break
    return [j for j in jobs if j.url and j.title]
