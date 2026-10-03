from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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

    @field_validator("archive_root")
    @classmethod
    def _absolute_archive_root(cls, value: Path | None) -> Path | None:
        if value is not None and not value.is_absolute():
            raise ValueError("ARCHIVE_ROOT must be an absolute path")
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
