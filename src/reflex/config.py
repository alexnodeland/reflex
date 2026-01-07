"""Application configuration with environment variable loading."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://reflex:reflex@localhost:5432/reflex"
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10

    # API
    api_host: str = "0.0.0.0"  # noqa: S104 - Intentional for Docker container binding
    api_port: int = 8000
    api_reload: bool = False

    # Observability
    logfire_token: str | None = None
    log_level: str = "INFO"

    # Agent
    openai_api_key: str | None = None
    default_model: str = "openai:gpt-4o-mini"

    # Event processing
    event_max_attempts: int = 3
    event_retry_base_delay: float = 1.0
    event_retry_max_delay: float = 60.0

    # App
    environment: str = "development"
    version: str = "0.1.0"


settings = Settings()
