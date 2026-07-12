from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from jobcopilot_discovery.worker.activities import (
        DeduplicateInput,
        FetchSourcesInput,
        PublishJobsInput,
        UpdateRunStatusInput,
        deduplicate_activity,
        fetch_sources_activity,
        publish_jobs_activity,
        update_run_status_activity,
    )


@dataclass
class DiscoveryWorkflowInput:
    user_id: str
    tenant_id: str
    config_id: str
    run_id: str
    keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    salary_min: int | None = None
    company_boards: list[str] = field(default_factory=list)


@dataclass
class DiscoveryWorkflowResult:
    status: str
    jobs_discovered: int


_2_RETRIES = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=2))
_3_RETRIES = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))


@workflow.defn
class DiscoveryWorkflow:
    @workflow.run
    async def run(self, inp: DiscoveryWorkflowInput) -> DiscoveryWorkflowResult:
        await workflow.execute_activity(
            update_run_status_activity,
            UpdateRunStatusInput(run_id=inp.run_id, status="running"),
            start_to_close_timeout=timedelta(seconds=10),
        )

        try:
            # ── 1. Fetch from all public sources (ADR-006) ────────────────────
            fetch_result = await workflow.execute_activity(
                fetch_sources_activity,
                FetchSourcesInput(
                    user_id=inp.user_id,
                    keywords=inp.keywords,
                    locations=inp.locations,
                    job_types=inp.job_types,
                    salary_min=inp.salary_min,
                    company_boards=inp.company_boards,
                ),
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=_3_RETRIES,
            )

            # ── 2. Deduplicate ────────────────────────────────────────────────
            dedup_result = await workflow.execute_activity(
                deduplicate_activity,
                DeduplicateInput(
                    user_id=inp.user_id,
                    raw_jobs=fetch_result.raw_jobs,
                ),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=_2_RETRIES,
            )

            # ── 3. Publish to RabbitMQ ────────────────────────────────────────
            published_count = 0
            if dedup_result.new_jobs:
                publish_result = await workflow.execute_activity(
                    publish_jobs_activity,
                    PublishJobsInput(
                        user_id=inp.user_id,
                        tenant_id=inp.tenant_id,
                        run_id=inp.run_id,
                        jobs=dedup_result.new_jobs,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_3_RETRIES,
                )
                published_count = publish_result.published_count

            # ── 4. Mark complete ──────────────────────────────────────────────
            await workflow.execute_activity(
                update_run_status_activity,
                UpdateRunStatusInput(
                    run_id=inp.run_id,
                    status="completed",
                    jobs_discovered=published_count,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

            return DiscoveryWorkflowResult(status="completed", jobs_discovered=published_count)

        except Exception as exc:
            await workflow.execute_activity(
                update_run_status_activity,
                UpdateRunStatusInput(
                    run_id=inp.run_id,
                    status="failed",
                    error_message=str(exc)[:500],
                ),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            raise
