"""
Temporal activities for the Discovery workflow.

Each activity is independently retried by Temporal — see workflows.py for
timeout and retry_policy settings applied at the call site.
"""

from dataclasses import dataclass, field

import httpx
import structlog
from jobcopilot_shared.db import build_engine, build_session_factory
from jobcopilot_shared.redis_client import build_redis
from temporalio import activity

from jobcopilot_discovery.config import settings
from jobcopilot_discovery.repositories.run_repo import RunRepository
from jobcopilot_discovery.services.publisher import publish_jobs_discovered
from jobcopilot_discovery.sources import GLOBAL_SOURCES, SearchCriteria, fetch_company_board
from jobcopilot_discovery.sources.base import USER_AGENT

log = structlog.get_logger()

# ── Input / Output dataclasses ────────────────────────────────────────────────


@dataclass
class FetchSourcesInput:
    user_id: str
    keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    salary_min: int | None = None
    company_boards: list[str] = field(default_factory=list)


@dataclass
class RawJobData:
    url: str
    title: str
    company_name: str
    location: str
    posted_snippet: str
    raw_text: str


@dataclass
class FetchSourcesResult:
    raw_jobs: list[RawJobData] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    source_errors: dict[str, str] = field(default_factory=dict)


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


# ── Activities ────────────────────────────────────────────────────────────────


@activity.defn
async def fetch_sources_activity(inp: FetchSourcesInput) -> FetchSourcesResult:
    """Fetch from every public source; one failing source never kills the run.

    Raises (→ Temporal retry) only when *every* source errored, which points
    at a systemic problem (network egress, DNS) rather than one flaky feed.
    """
    criteria = SearchCriteria(
        keywords=inp.keywords,
        locations=inp.locations,
        job_types=inp.job_types,
        salary_min=inp.salary_min,
    )

    raw_jobs: list[RawJobData] = []
    counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(
        timeout=20.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        fetchers = [(name, fetcher(client, criteria)) for name, fetcher in GLOBAL_SOURCES.items()]
        fetchers += [
            (f"board:{url}", fetch_company_board(client, url, criteria))
            for url in inp.company_boards
            if url.strip()
        ]

        for name, coro in fetchers:
            try:
                jobs = await coro
            except Exception as exc:
                errors[name] = f"{type(exc).__name__}: {exc}"[:300]
                log.warning("source_fetch_failed", source=name, error=errors[name])
                continue
            counts[name] = len(jobs)
            for j in jobs:
                if j.url in seen_urls:
                    continue  # cross-source duplicate within this run
                seen_urls.add(j.url)
                raw_jobs.append(
                    RawJobData(
                        url=j.url,
                        title=j.title,
                        company_name=j.company_name,
                        location=j.location,
                        posted_snippet=j.posted_snippet,
                        raw_text=j.raw_text,
                    )
                )

    if errors and not counts:
        raise RuntimeError(f"all sources failed: {errors}")

    log.info(
        "sources_fetched",
        user_id=inp.user_id,
        total=len(raw_jobs),
        counts=counts,
        errors=errors,
    )
    return FetchSourcesResult(raw_jobs=raw_jobs, source_counts=counts, source_errors=errors)


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
