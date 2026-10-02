from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import REPO_ROOT, VerifySettings


def test_the_cache_dir_defaults_to_the_gitignored_data_dir_whatever_the_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("VERIFY_CACHE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert VerifySettings().verify_cache_dir == REPO_ROOT / "data" / "official"
    assert (REPO_ROOT / "services").is_dir()


def test_a_relative_cache_dir_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_CACHE_DIR", "data/official")
    with pytest.raises(ValidationError, match="absolute"):
        VerifySettings()
