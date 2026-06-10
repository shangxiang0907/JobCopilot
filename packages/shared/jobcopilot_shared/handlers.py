from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jobcopilot_shared.exceptions import JobCopilotError
from jobcopilot_shared.logging import get_logger
from jobcopilot_shared.schemas.common import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(JobCopilotError)
    async def handle_jobcopilot_error(request: Request, exc: JobCopilotError) -> JSONResponse:
        logger.warning(
            "request_error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(code=exc.error_code, message=exc.message)
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(code="internal_error", message="An unexpected error occurred.")
            ).model_dump(),
        )
