from jobcopilot_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    service_name: str = "notification-service"
    version: str = "0.1.0"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_exchange: str = "jobcopilot"

    # SMTP (optional — email channel disabled if not set)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = "noreply@jobcopilot.ai"
    smtp_use_tls: bool = True


settings = Settings()
