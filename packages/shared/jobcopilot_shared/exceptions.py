from http import HTTPStatus


class JobCopilotError(Exception):
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(JobCopilotError):
    status_code = HTTPStatus.NOT_FOUND
    error_code = "not_found"


class PermissionDeniedError(JobCopilotError):
    status_code = HTTPStatus.FORBIDDEN
    error_code = "permission_denied"


class TenantIsolationError(JobCopilotError):
    """Raised when a query would access data outside the caller's tenant."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "tenant_isolation_violation"


class ConflictError(JobCopilotError):
    status_code = HTTPStatus.CONFLICT
    error_code = "conflict"


class ValidationError(JobCopilotError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class ExternalServiceError(JobCopilotError):
    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "external_service_error"


class CookieExpiredError(ExternalServiceError):
    """LinkedIn session cookie has expired or been invalidated."""

    error_code = "linkedin_cookie_expired"


class QuotaExceededError(JobCopilotError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "quota_exceeded"
