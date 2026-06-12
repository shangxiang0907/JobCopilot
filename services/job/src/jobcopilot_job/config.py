from jobcopilot_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "job-service"
    version: str = "0.1.0"


settings = Settings()
