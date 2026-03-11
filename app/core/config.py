"""Application configuration via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    ENCRYPTION_KEY: str
    BASE_URL: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"
    DB_ECHO: bool = False
    ALERT_WEBHOOK_URL: str | None = None
    POLL_INTERVAL_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
