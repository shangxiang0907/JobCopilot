"""Generic single-URL job-page scraper for the manual URL entry path (4b).

Two-stage fetch: plain httpx first (fast, covers static pages), Playwright
render when the response looks like a JS shell. Never raises — the caller
(the AI assistant's add_job_from_url tool) turns failure into the PRD's
graceful degradation: "paste the JD text instead".
"""

from dataclasses import dataclass

import httpx
import structlog

from jobcopilot_discovery.sources.base import RAW_TEXT_LIMIT, USER_AGENT, strip_html

log = structlog.get_logger()

# Below this much extracted text we assume a JS-rendered shell / bot wall.
_MIN_TEXT_CHARS = 300
_FETCH_TIMEOUT = 20.0
_RENDER_TIMEOUT_MS = 25_000


@dataclass
class ScrapeResult:
    ok: bool
    title: str = ""
    text: str = ""
    error: str = ""


def _extract(html: str) -> tuple[str, str]:
    """Return (title, text) from raw HTML."""
    import re

    title = ""
    if m := re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL):
        title = strip_html(m.group(1)).strip()[:300]
    # Drop non-content blocks wholesale before flattening.
    body = re.sub(
        r"<(script|style|nav|header|footer|noscript)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return title, strip_html(body)[:RAW_TEXT_LIMIT]


async def scrape_url(url: str) -> ScrapeResult:
    if not url.startswith(("http://", "https://")):
        return ScrapeResult(ok=False, error="Only http(s) URLs are supported")

    # Stage 1: plain HTTP.
    html = ""
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                html = resp.text
            else:
                log.info("scrape_httpx_rejected", url=url, status=resp.status_code)
    except Exception as exc:
        log.info("scrape_httpx_failed", url=url, error=str(exc)[:200])

    if html:
        title, text = _extract(html)
        if len(text) >= _MIN_TEXT_CHARS:
            return ScrapeResult(ok=True, title=title, text=text)

    # Stage 2: Playwright render (JS-heavy pages).
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=USER_AGENT)
                await page.goto(url, timeout=_RENDER_TIMEOUT_MS, wait_until="networkidle")
                html = await page.content()
            finally:
                await browser.close()
    except Exception as exc:
        log.info("scrape_playwright_failed", url=url, error=str(exc)[:200])
        return ScrapeResult(
            ok=False,
            error="Could not fetch this page (it may require login or block automated access)",
        )

    title, text = _extract(html)
    if len(text) < _MIN_TEXT_CHARS:
        return ScrapeResult(
            ok=False,
            error="Page fetched but no readable job description found (likely behind a login)",
        )
    return ScrapeResult(ok=True, title=title, text=text)
