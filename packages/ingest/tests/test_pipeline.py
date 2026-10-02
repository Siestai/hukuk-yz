import json
import os
from pathlib import Path

import pytest
from conftest import make_ole2, make_pdf

from hukuk_ingest import pipeline, quality
from hukuk_ingest.extract import Extraction
from hukuk_ingest.pipeline import FileResult, process_file

OneFile = tuple[Path, Path, Path]


def _meta_path(cache: Path, result: FileResult) -> Path:
    return pipeline.cache_base(cache, result.sha256).with_suffix(".meta.json")


def test_process_file_routes_broken_pdf_text_layer_to_ocr(tmp_path: Path) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "bad.pdf").write_bytes(make_pdf(["xkq zzt brm plv wnd plm qrs tvw " * 12]))
    result = process_file(root / "bad.pdf", root, tmp_path / "cache")
    assert (result.status, result.reason) == ("needs_ocr", "bad_ocr_layer")
    assert result.text_ref is not None  # the broken text is kept for inspection


def test_process_file_writes_raw_and_clean_text(one_text_file: OneFile) -> None:
    root, path, cache = one_text_file
    result = process_file(path, root, cache)
    base = pipeline.cache_base(cache, result.sha256)
    assert result.text_ref == f"{result.sha256[:2]}/{result.sha256}.raw.txt"
    assert base.with_suffix(".raw.txt").is_file()
    assert base.with_suffix(".clean.txt").is_file()


def test_process_file_second_call_is_cached_and_force_bypasses(one_text_file: OneFile) -> None:
    root, path, cache = one_text_file
    assert not process_file(path, root, cache).cached
    assert process_file(path, root, cache).cached
    assert not process_file(path, root, cache, force=True).cached


def test_process_file_same_content_other_name_hits_cache(tmp_path: Path) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "Thumbs.db").write_bytes(make_ole2("Catalog"))
    (root / "x.doc").write_bytes(make_ole2("Catalog"))
    first = process_file(root / "Thumbs.db", root, tmp_path / "cache")
    second = process_file(root / "x.doc", root, tmp_path / "cache")
    assert (first.detected_type, first.status) == ("unknown", "skipped")
    assert (second.detected_type, second.status) == ("unknown", "skipped")
    assert second.cached


def test_process_file_flags_lone_surrogates(
    one_text_file: OneFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, cache = one_text_file
    monkeypatch.setattr(
        pipeline, "extract", lambda p, t: Extraction("ok", "işçi \ud800 ve", extractor="x")
    )
    result = process_file(path, root, cache)
    assert result.status == "ok"
    assert "lone_surrogates" in result.warnings


@pytest.mark.parametrize("damage", ["garbage", "[]", "{}", '{"pipeline_version": 1}', ""])
def test_cache_entry_with_unusable_meta_is_re_extracted_and_healed(
    one_text_file: OneFile, damage: str
) -> None:
    root, path, cache = one_text_file
    _meta_path(cache, process_file(path, root, cache)).write_text(damage)
    again = process_file(path, root, cache)
    assert again.status == "ok"
    assert not again.cached
    assert process_file(path, root, cache).cached


def test_cache_entry_missing_a_field_is_re_extracted(one_text_file: OneFile) -> None:
    root, path, cache = one_text_file
    meta_path = _meta_path(cache, process_file(path, root, cache))
    meta = json.loads(meta_path.read_text())
    del meta["quality"]
    meta_path.write_text(json.dumps(meta))
    assert not process_file(path, root, cache).cached


@pytest.mark.parametrize("suffix", [".raw.txt", ".clean.txt"])
def test_cache_entry_missing_text_file_is_re_extracted(one_text_file: OneFile, suffix: str) -> None:
    root, path, cache = one_text_file
    first = process_file(path, root, cache)
    pipeline.cache_base(cache, first.sha256).with_suffix(suffix).unlink()
    again = process_file(path, root, cache)
    assert again.status == "ok"
    assert not again.cached


def test_cache_entry_is_invalidated_by_pipeline_version(
    one_text_file: OneFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, cache = one_text_file
    process_file(path, root, cache)
    monkeypatch.setattr(pipeline, "PIPELINE_VERSION", "999")
    assert not process_file(path, root, cache).cached


def test_cache_entry_is_invalidated_by_quality_constants(
    one_text_file: OneFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, path, cache = one_text_file
    process_file(path, root, cache)
    monkeypatch.setattr(quality, "BAD_OCR_RATIO", 0.04)
    assert not process_file(path, root, cache).cached


def test_write_atomic_removes_temp_file_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", boom)
    with pytest.raises(OSError):
        pipeline._write_atomic(tmp_path / "d" / "x.txt", "data")
    assert not list((tmp_path / "d").glob("*.tmp"))
