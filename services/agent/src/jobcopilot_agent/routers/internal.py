"""
/internal/* — service-to-service endpoints (blocked by Kong for external traffic).
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from jobcopilot_agent.deps import DbDep
from jobcopilot_agent.repositories.analysis_repo import AnalysisRepository
from jobcopilot_agent.schemas.agent import AnalysisResponse

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/analyses/{job_id}", response_model=AnalysisResponse)
async def get_analysis_internal(
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    db: DbDep,
) -> AnalysisResponse:
    """Retrieve analysis results for inter-service use (e.g., Job Service enrichment)."""
    repo = AnalysisRepository(db)
    analysis = await repo.get_by_job_user(job_id, user_id, tenant_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return AnalysisResponse.model_validate(analysis)
