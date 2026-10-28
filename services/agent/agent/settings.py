from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SERVICE_KEY_LENGTH = 16


class LlmSettings(BaseSettings):
    """The part of the configuration the eval runner needs too: the models and the tracing. Read
    from environment variables only; an empty variable counts as unset."""

    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    # Pydantic AI model names (provider:model). Fast: intake and holding map. Strong: the draft.
    agent_model_fast: str = "anthropic:claude-haiku-4-5-20251001"
    agent_model_strong: str = "anthropic:claude-sonnet-5-5"
    # Langfuse over OpenTelemetry; without the keys only the structured log is written.
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None


class KbSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    # `app`, where /kb/search lives, and the key the agent sends to it in `X-Service-Key`.
    app_base_url: str = "http://app:8000"
    kb_service_key: SecretStr
    kb_timeout_seconds: float = 20.0


class Settings(LlmSettings, KbSettings):
    # The same database as `app`; the graph state lives in its own schema, `agent`. Either the
    # SQLAlchemy form (postgresql+asyncpg://...) or a plain postgresql:// URL.
    database_url: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # What `app` sends in `X-Service-Key` to POST /run.
    agent_service_key: SecretStr

    @field_validator("agent_service_key")
    @classmethod
    def _real_key(cls, key: SecretStr) -> SecretStr:
        value = key.get_secret_value()
        if len(value) < MIN_SERVICE_KEY_LENGTH or value.lower().startswith("change"):
            raise ValueError(
                f"AGENT_SERVICE_KEY must be a real secret of at least {MIN_SERVICE_KEY_LENGTH} "
                "characters, not a placeholder"
            )
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
