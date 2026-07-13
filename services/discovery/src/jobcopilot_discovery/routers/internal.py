"""Internal routes — container DNS only. Kong blocks external access."""

from fastapi import APIRouter
from pydantic import BaseModel

from jobcopilot_discovery.services.scraper import scrape_url

router = APIRouter(prefix="/internal", tags=["internal"])


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    ok: bool
    title: str = ""
    text: str = ""
    error: str = ""


@router.post("/scrape", response_model=ScrapeResponse)
async def internal_scrape(body: ScrapeRequest) -> ScrapeResponse:
    """Fetch and text-extract a job posting URL for the manual entry path.

    Never errors at the HTTP layer — failures come back as {ok: false, error}
    so the AI assistant can degrade gracefully (prompt the user to paste text).
    """
    result = await scrape_url(body.url)
    return ScrapeResponse(ok=result.ok, title=result.title, text=result.text, error=result.error)
