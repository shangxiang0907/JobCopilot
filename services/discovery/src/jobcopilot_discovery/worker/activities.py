"""
Temporal activities for the Discovery workflow.

Each activity is independently retried by Temporal — see workflows.py for
timeout and retry_policy settings applied at the call site.
"""

from dataclasses import dataclass, field

import httpx
import structlog
from jobcopilot_shared.crypto import decrypt
from jobcopilot_shared.db import build_engine, build_session_factory
from jobcopilot_shared.redis_client import build_redis
from temporalio import activity

from jobcopilot_discovery.config import settings
from jobcopilot_discovery.repositories.run_repo import RunRepository
from jobcopilot_discovery.services import linkedin_scraper
from jobcopilot_discovery.services.linkedin_scraper import RawJob, SearchConfig
from jobcopilot_discovery.services.publisher import publish_cookie_expired, publish_jobs_discovered

log = structlog.get_logger()

# ── Input / Output dataclasses ────────────────────────────────────────────────


@dataclass
class ValidateCookieInput:
    user_id: str
    run_id: str


@dataclass
class ValidateCookieResult:
    is_valid: bool
    cookie: str  # decrypted; empty string if invalid


@dataclass
class SearchLinkedInInput:
    user_id: str
    cookie: str
    keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    salary_min: int | None = None


@dataclass
class RawJobData:
    url: str
    title: str
    company_name: str
    location: str
    posted_snippet: str
    raw_text: str


@dataclass
class SearchLinkedInResult:
    raw_jobs: list[RawJobData] = field(default_factory=list)


@dataclass
class DeduplicateInput:
    user_id: str
    raw_jobs: list[RawJobData] = field(default_factory=list)


@dataclass
class DeduplicateResult:
    new_jobs: list[RawJobData] = field(default_factory=list)


@dataclass
class PublishJobsInput:
    user_id: str
    tenant_id: str
    run_id: str
    jobs: list[RawJobData] = field(default_factory=list)


@dataclass
class PublishJobsResult:
    published_count: int


@dataclass
class UpdateRunStatusInput:
    run_id: str
    status: str
    jobs_discovered: int = 0
    error_message: str | None = None


@dataclass
class PublishCookieExpiredInput:
    user_id: str
    run_id: str


# ── Activities ────────────────────────────────────────────────────────────────


@activity.defn
async def validate_cookie_activity(inp: ValidateCookieInput) -> ValidateCookieResult:
    """Fetch the user's LinkedIn cookie from Profile Service, then validate it against LinkedIn."""
    url = f"{settings.profile_service_url}/internal/profiles/{inp.user_id}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        log.warning("profile_fetch_failed", user_id=inp.user_id, status=resp.status_code)
        return ValidateCookieResult(is_valid=False, cookie="")

    profile_data = resp.json()
    cookie_enc = profile_data.get("linkedin_cookie_enc") or ""
    if not cookie_enc:
        return ValidateCookieResult(is_valid=False, cookie="")

    cookie = decrypt(cookie_enc, settings.encryption_key)
    is_valid = await linkedin_scraper.validate_cookie(cookie)

    log.info("cookie_validated", user_id=inp.user_id, is_valid=is_valid)
    return ValidateCookieResult(is_valid=is_valid, cookie=cookie if is_valid else "")


@activity.defn
async def search_linkedin_activity(inp: SearchLinkedInInput) -> SearchLinkedInResult:
    """Run Playwright to scrape LinkedIn job search results."""
    config = SearchConfig(
        cookie=inp.cookie,
        keywords=inp.keywords,
        locations=inp.locations,
        job_types=inp.job_types,
        salary_min=inp.salary_min,
    )
    raw_jobs: list[RawJob] = await linkedin_scraper.scrape_jobs(
        config, headless=settings.playwright_headless
    )
    log.info("linkedin_scraped", user_id=inp.user_id, count=len(raw_jobs))

    result_jobs = [
        RawJobData(
            url=j.url,
            title=j.title,
            company_name=j.company_name,
            location=j.location,
            posted_snippet=j.posted_snippet,
            raw_text=j.raw_text,
        )
        for j in raw_jobs
    ]
    return SearchLinkedInResult(raw_jobs=result_jobs)


@activity.defn
async def deduplicate_activity(inp: DeduplicateInput) -> DeduplicateResult:
    """Filter out URLs already seen for this user (stored in Redis SET)."""
    if not inp.raw_jobs:
        return DeduplicateResult(new_jobs=[])

    redis = build_redis(settings.redis_url)
    key = f"dedup:discovery:{inp.user_id}"

    new_jobs: list[RawJobData] = []
    try:
        pipe = redis.pipeline()
        for job in inp.raw_jobs:
            pipe.sismember(key, job.url)
        results = await pipe.execute()

        new_urls: list[str] = []
        for job, is_member in zip(inp.raw_jobs, results, strict=True):
            if not is_member:
                new_jobs.append(job)
                new_urls.append(job.url)

        if new_urls:
            # TTL 30 days — keeps dedup window without growing unbounded
            pipe = redis.pipeline()
            pipe.sadd(key, *new_urls)
            pipe.expire(key, 60 * 60 * 24 * 30)
            await pipe.execute()
    finally:
        await redis.aclose()

    log.info("deduplicated", user_id=inp.user_id, total=len(inp.raw_jobs), new=len(new_jobs))
    return DeduplicateResult(new_jobs=new_jobs)


@activity.defn
async def publish_jobs_activity(inp: PublishJobsInput) -> PublishJobsResult:
    """Batch-publish new jobs to RabbitMQ job.discovered queue."""
    jobs_dicts = [
        {
            "url": j.url,
            "title": j.title,
            "company_name": j.company_name,
            "location": j.location,
            "raw_text": j.raw_text,
        }
        for j in inp.jobs
    ]
    count = await publish_jobs_discovered(
        jobs=jobs_dicts,
        user_id=inp.user_id,
        tenant_id=inp.tenant_id,
        run_id=inp.run_id,
    )
    log.info("jobs_published", user_id=inp.user_id, run_id=inp.run_id, count=count)
    return PublishJobsResult(published_count=count)


@activity.defn
async def publish_cookie_expired_activity(inp: PublishCookieExpiredInput) -> None:
    """Notify Notification Service that the user's LinkedIn cookie has expired."""
    await publish_cookie_expired(user_id=inp.user_id, run_id=inp.run_id)
    log.warning("cookie_expired_published", user_id=inp.user_id, run_id=inp.run_id)


@activity.defn
async def update_run_status_activity(inp: UpdateRunStatusInput) -> None:
    """Persist workflow run status back to PostgreSQL."""
    import uuid

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    async with session_factory() as session:
        async with session.begin():
            repo = RunRepository(session)
            await repo.update_status(
                run_id=uuid.UUID(inp.run_id),
                status=inp.status,
                jobs_discovered=inp.jobs_discovered,
                error_message=inp.error_message,
            )

    await engine.dispose()
