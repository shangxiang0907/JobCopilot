from jobcopilot_shared.config import BaseServiceSettings
from pydantic import Field


class Settings(BaseServiceSettings):
    service_name: str = "profile-service"
    version: str = "0.1.0"

    qdrant_url: str = "http://localhost:6333"
    qdrant_resume_collection: str = "resumes"
    embedding_model: str = "text-embedding-v3"
    embedding_dimensions: int = 1024

    # Local filesystem path for resume file storage (override with S3 URL prefix in prod)
    resume_storage_path: str = Field(default="/tmp/jobcopilot/resumes")  # noqa: S108
    max_resume_size_mb: int = 10

    # Client secret of the `admin-api` service account (created by keycloak-init;
    # scoped to view-users + manage-users only). Powers /v1/admin/users.
    keycloak_admin_api_secret: str = ""


settings = Settings()
