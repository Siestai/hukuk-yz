from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables only (no dotenv file)."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+asyncpg://hukuk:change-me@localhost:5432/hukuk"
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
