from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables only (no dotenv file)."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
