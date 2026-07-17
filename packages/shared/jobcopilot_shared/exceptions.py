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


class QuotaExceededError(JobCopilotError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "quota_exceeded"


class QuotaUnavailableError(JobCopilotError):
    """Quota accounting is down (Redis unreachable). The quota is a cost gate on
    the operator's platform LLM key, so it fails CLOSED: no counting, no spend."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "quota_unavailable"


class LLMKeyNotConfiguredError(JobCopilotError):
    """BYO deployment mode (ADR-007): the user has not saved an LLM API key yet."""

    status_code = HTTPStatus.CONFLICT
    error_code = "llm_key_not_configured"


class NoActiveResumeError(JobCopilotError):
    """The user has no active resume; resume-dependent flows must fail before any LLM call."""

    status_code = HTTPStatus.CONFLICT
    error_code = "no_active_resume"
