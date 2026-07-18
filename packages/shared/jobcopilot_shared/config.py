from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Base settings inherited by every service. Service-specific settings extend this class."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "jobcopilot"
    environment: str = Field(default="development")
    version: str = "0.1.0"
    # Git commit baked into the image at build time (CD build-arg -> ENV GIT_SHA);
    # "dev" outside a built image. This is the DEPLOYMENT revision — deliberately
    # separate from `version`, which is the API version shown in OpenAPI info.
    git_sha: str = "dev"

    # Database (required; populated from DATABASE_URL env var at runtime)
    database_url: str = Field(default="")

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "jobcopilot"
    keycloak_client_id: str = "api"

    # LLM — switchable via env var; defaults to DashScope
    # Deployment mode for LLM key sourcing (ADR-007):
    #   byo      — each user saves their own key (self-hosted default; key UI shown)
    #   platform — dashscope_api_key serves every user (hosted site; key UI hidden)
    llm_key_mode: Literal["byo", "platform"] = "byo"
    # Platform mode only: max AI actions (analyze/match/interview/chat message)
    # per tenant per UTC day on the platform key; <= 0 disables the quota.
    # BYO users burn their own key and are never quota-limited.
    llm_daily_quota: int = 20
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-max"
    # Multimodal model for JD screenshot parsing (same OpenAI-compatible endpoint)
    llm_vision_model: str = "qwen-vl-max"

    # LangSmith tracing (optional)
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = False

    # AES-256-GCM key for encrypting LinkedIn cookies and API keys (32-byte hex = 64 chars)
    encryption_key: str = Field(default="")
