from jobcopilot_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "discovery-service"
    version: str = "0.1.0"

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "jobcopilot"
    temporal_task_queue: str = "discovery"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "jobcopilot"

    # Profile Service (internal)
    profile_service_url: str = "http://profile-service:8000"

    # Playwright
    playwright_headless: bool = True


settings = Settings()
