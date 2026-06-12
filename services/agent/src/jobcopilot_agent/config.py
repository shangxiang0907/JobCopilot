from jobcopilot_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "agent-service"
    version: str = "0.1.0"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "jobcopilot"

    # Internal service URLs
    profile_service_url: str = "http://profile-service:8000"
    job_service_url: str = "http://job-service:8000"


settings = Settings()
