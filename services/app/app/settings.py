from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Configuration read from environment variables only (no dotenv file). An empty variable
    counts as unset."""

    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    database_url: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    env: str = "dev"
    session_ttl_hours: int = 12
    # False only for plain-http dev; the cookie is then sent without the Secure flag.
    cookie_secure: bool = True
    # Login rate limit (task 10a): failed attempts inside the window that block further logins.
    login_max_fails_per_email: int = 5
    login_max_fails_per_ip: int = 20
    login_window_minutes: int = 15
    # Where `ingest_file.path` is relative to (the Drive copy, `data/drive`); the decision PDFs
    # are served from here. Unset: the file endpoint answers 404.
    archive_root: Path | None = None
    # Largest decision PDF served; bigger files answer 404 (the file is read into memory).
    archive_max_file_bytes: int = 50 * 1024 * 1024

    # The file store of uploaded documents (task 12). Unset: the upload endpoints answer 503
    # and the worker does not scan.
    file_store_root: Path | None = None
    file_max_bytes: int = 50 * 1024 * 1024

    # The language-model fallback of the upload detection (task 13a). The provider is "none" until
    # Orhan decides on provider and region (docs/architecture.md); the key is a secret and the base
    # URL is how a region is chosen. Without a key the step is skipped, silently.
    file_detect_llm_provider: Literal["anthropic", "none"] = "none"
    file_detect_llm_model: str = "claude-haiku-4-5-20251001"
    file_detect_llm_api_key: SecretStr | None = None
    file_detect_llm_base_url: str = "https://api.anthropic.com"
    file_detect_llm_timeout_seconds: float = 30.0

    @field_validator("archive_root", "file_store_root")
    @classmethod
    def _absolute_root(cls, value: Path | None, info: ValidationInfo) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError(f"{(info.field_name or '').upper()} must be an absolute path")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


class VerifySettings(BaseSettings):
    """Official-source verification (task 06). Kept apart from `Settings` so that a run on a
    machine without a database (`--keys`) needs no DATABASE_URL. An empty variable counts as
    unset."""

    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)

    # Optional outbound proxy per source, e.g. VERIFY_PROXY_YARGITAY=http://host:3128; none by
    # default. The source names are the ones of `--court`'s sources: yargitay, emsal (BAM), aym,
    # danistay.
    verify_proxy_yargitay: str | None = None
    verify_proxy_emsal: str | None = None
    verify_proxy_aym: str | None = None
    verify_proxy_danistay: str | None = None
    verify_min_interval_seconds: float = 12.0
    # Goes into the User-Agent so the sites can reach us (task 06 §8); required for live runs.
    verify_contact: str | None = None
    # The raw official answers (gitignored `data/`); absolute, so the run's cwd does not matter.
    verify_cache_dir: Path = REPO_ROOT / "data" / "official"

    @field_validator("verify_cache_dir")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("VERIFY_CACHE_DIR must be an absolute path")
        return value


@lru_cache
def get_verify_settings() -> VerifySettings:
    return VerifySettings()
