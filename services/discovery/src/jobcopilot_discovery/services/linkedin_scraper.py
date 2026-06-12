"""
LinkedIn scraper using Playwright.

LinkedIn's DOM structure changes periodically — selectors may need updating.
Current selectors target the public job search results page as of 2026-Q2.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx
from playwright.async_api import async_playwright

log = logging.getLogger(__name__)

_LINKEDIN_HOST = "https://www.linkedin.com"
_SEARCH_URL = _LINKEDIN_HOST + "/jobs/search/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class RawJob:
    url: str
    title: str
    company_name: str
    location: str
    posted_snippet: str
    raw_text: str


@dataclass
class SearchConfig:
    cookie: str
    keywords: list[str]
    locations: list[str]
    job_types: list[str] = field(default_factory=list)
    salary_min: int | None = None
    max_pages: int = 3


# LinkedIn f_JT filter values
_JOB_TYPE_MAP = {
    "full-time": "F",
    "part-time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
}


async def validate_cookie(cookie: str) -> bool:
    """HEAD request to LinkedIn feed; 200 means the cookie is still valid."""
    headers = {
        "User-Agent": _USER_AGENT,
        "Cookie": f"li_at={cookie}",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=8.0) as client:
            resp = await client.head(_LINKEDIN_HOST + "/feed/", headers=headers)
        return resp.status_code == 200
    except Exception:
        return False


async def scrape_jobs(config: SearchConfig, headless: bool = True) -> list[RawJob]:
    """
    Run Playwright to collect raw job listings.
    Iterates over each keyword+location combination and each page up to max_pages.
    """
    jobs: list[RawJob] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1440, "height": 900},
        )
        # Inject LinkedIn session cookie
        await context.add_cookies(
            [
                {
                    "name": "li_at",
                    "value": config.cookie,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                }
            ]
        )

        page = await context.new_page()

        for keyword in config.keywords:
            for location in config.locations:
                page_jobs = await _scrape_keyword_location(
                    page, keyword, location, config, headless
                )
                jobs.extend(page_jobs)

        await browser.close()

    # Deduplicate by URL within this scrape batch
    seen: set[str] = set()
    unique: list[RawJob] = []
    for job in jobs:
        if job.url not in seen:
            seen.add(job.url)
            unique.append(job)
    return unique


async def _scrape_keyword_location(
    page, keyword: str, location: str, config: SearchConfig, headless: bool
) -> list[RawJob]:
    jobs: list[RawJob] = []

    jt_param = ",".join(
        _JOB_TYPE_MAP[jt.lower()] for jt in config.job_types if jt.lower() in _JOB_TYPE_MAP
    )
    params = f"?keywords={quote_plus(keyword)}&location={quote_plus(location)}&sortBy=DD"
    if jt_param:
        params += f"&f_JT={jt_param}"

    for page_num in range(config.max_pages):
        url = _SEARCH_URL + params + f"&start={page_num * 25}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Brief pause to let JS render job cards
            await asyncio.sleep(2)
            page_jobs = await _extract_job_cards(page)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
        except Exception:
            break

    return jobs


async def _extract_job_cards(page) -> list[RawJob]:
    """Extract job data from the current search results page."""
    jobs: list[RawJob] = []

    # Primary selector for logged-in job search results
    cards = await page.query_selector_all("li.jobs-search-results__list-item")

    # Fallback to public-facing selectors
    if not cards:
        cards = await page.query_selector_all("li.job-search-card")

    for card in cards:
        try:
            job = await _parse_card(card)
            if job:
                jobs.append(job)
        except Exception as exc:
            log.debug("skipping unparseable job card", exc_info=exc)
            continue

    return jobs


async def _parse_card(card) -> RawJob | None:
    # Title + link — try multiple selector variants
    link_el = await card.query_selector("a.job-card-container__link")
    if not link_el:
        link_el = await card.query_selector("a.job-search-card__title-link")
    if not link_el:
        return None

    href = await link_el.get_attribute("href") or ""
    url = _normalise_url(href)
    if not url:
        return None

    title = (await link_el.inner_text()).strip()

    # Company name
    company_el = await card.query_selector(
        ".job-card-container__company-name, .job-search-card__company-name"
    )
    company_name = (await company_el.inner_text()).strip() if company_el else ""

    # Location
    location_el = await card.query_selector(
        ".job-card-container__metadata-item, .job-search-card__location"
    )
    location = (await location_el.inner_text()).strip() if location_el else ""

    # Posted date snippet
    time_el = await card.query_selector("time")
    posted_snippet = await time_el.get_attribute("datetime") or "" if time_el else ""

    raw_text = (await card.inner_text()).strip()

    return RawJob(
        url=url,
        title=title,
        company_name=company_name,
        location=location,
        posted_snippet=posted_snippet,
        raw_text=raw_text,
    )


def _normalise_url(href: str) -> str:
    """Return a canonical LinkedIn job URL, stripping tracking params."""
    if not href:
        return ""
    # Extract the /jobs/view/<id> path
    match = re.search(r"(https://www\.linkedin\.com/jobs/view/\d+)", href)
    if match:
        return match.group(1)
    if href.startswith("/jobs/view/"):
        return _LINKEDIN_HOST + href.split("?")[0]
    return ""
