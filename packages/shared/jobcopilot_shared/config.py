from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Base settings inherited by every service. Service-specific settings extend this class."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "jobcopilot"
    environment: str = Field(default="development")
    version: str = "0.1.0"

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "jobcopilot"
    keycloak_client_id: str = "api"

    # LLM — switchable via env var; defaults to DashScope
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-max"

    # LangSmith tracing (optional)
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = False

    # AES-256-GCM key for encrypting LinkedIn cookies and API keys (32-byte hex = 64 chars)
    encryption_key: str
