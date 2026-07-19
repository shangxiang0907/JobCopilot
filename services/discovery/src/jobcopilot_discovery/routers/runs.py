import uuid

from fastapi import APIRouter, status
from jobcopilot_shared.schemas.common import PaginatedResponse
from temporalio.client import Client

from jobcopilot_discovery.config import settings
from jobcopilot_discovery.deps import SessionDep, TenantIdDep, UserIdDep
from jobcopilot_discovery.repositories.config_repo import ConfigRepository
from jobcopilot_discovery.repositories.run_repo import RunRepository
from jobcopilot_discovery.schemas.discovery import DiscoveryRunResponse, TriggerRunRequest
from jobcopilot_discovery.worker.workflows import DiscoveryWorkflow, DiscoveryWorkflowInput

router = APIRouter(prefix="/v1/discovery/runs", tags=["discovery-runs"])


@router.post("", response_model=DiscoveryRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    body: TriggerRunRequest,
    session: SessionDep,
    user_id: UserIdDep,
    tenant_id: TenantIdDep,
) -> DiscoveryRunResponse:
    config_repo = ConfigRepository(session)
    config = await config_repo.get(user_id, body.config_id)

    run_repo = RunRepository(session)
    run = await run_repo.create(user_id=user_id, config_id=config.config_id)
    # Workflow activities read this row by run_id — it must be committed before
    # the workflow starts, or the worker can race an uncommitted row.
    await session.commit()

    temporal_client = await Client.connect(
        settings.temporal_host, namespace=settings.temporal_namespace
    )

    workflow_input = DiscoveryWorkflowInput(
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        config_id=str(config.config_id),
        run_id=str(run.run_id),
        keywords=config.keywords,
        locations=config.locations,
        job_types=config.job_types,
        salary_min=config.salary_min,
        company_boards=config.company_boards,
    )

    handle = await temporal_client.start_workflow(
        DiscoveryWorkflow.run,
        workflow_input,
        id=f"discovery-{run.run_id}",
        task_queue=settings.temporal_task_queue,
    )

    run = await run_repo.update_status(run.run_id, status="pending")
    run.temporal_run_id = handle.result_run_id
    await session.commit()

    return DiscoveryRunResponse.model_validate(run)


@router.get("", response_model=PaginatedResponse[DiscoveryRunResponse])
async def list_runs(
    session: SessionDep, user_id: UserIdDep
) -> PaginatedResponse[DiscoveryRunResponse]:
    """All /v1 collection endpoints return PaginatedResponse — see CLAUDE.md."""
    repo = RunRepository(session)
    runs = await repo.list(user_id)
    items = [DiscoveryRunResponse.model_validate(r) for r in runs]
    return PaginatedResponse(
        items=items, total=len(items), page=1, size=max(len(items), 1), has_next=False
    )


@router.get("/{run_id}", response_model=DiscoveryRunResponse)
async def get_run(
    run_id: uuid.UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> DiscoveryRunResponse:
    repo = RunRepository(session)
    run = await repo.get(user_id, run_id)
    return DiscoveryRunResponse.model_validate(run)
