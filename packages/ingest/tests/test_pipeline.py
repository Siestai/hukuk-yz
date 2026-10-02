import json
import os
from pathlib import Path

import pytest
from conftest import FIXTURES, GOOD, WEAK, FakeEngine, make_ole2, make_pdf

from hukuk_ingest import pipeline, quality
from hukuk_ingest.extract import Extraction
from hukuk_ingest.ocr import Tesseract
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


def test_process_file_resolves_the_ocr_engine_only_for_files_that_need_ocr(
    one_text_file: OneFile, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise AssertionError("engine resolved")

    monkeypatch.setattr(pipeline, "default_engine", boom)
    root, path, cache = one_text_file
    assert process_file(path, root, cache).status == "ok"
    assert process_file(path, root, cache).cached


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


def _scan_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "c"
    root.mkdir()
    (root / "scan.pdf").write_bytes(make_pdf(["", ""]))
    (root / "a.txt").write_text("işçi ve işveren ile ilgili madde " * 5, encoding="utf-8")
    return root, root / "scan.pdf", tmp_path / "cache"


def _use_engine(monkeypatch: pytest.MonkeyPatch, engine: FakeEngine | None) -> None:
    monkeypatch.setattr(pipeline, "default_engine", lambda: engine)


def test_process_file_ocr_replaces_missing_text_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, scan, cache = _scan_corpus(tmp_path)
    _use_engine(monkeypatch, FakeEngine([GOOD, WEAK, GOOD]))  # page 2: weak, then Sauvola
    result = process_file(scan, root, cache)
    assert (result.status, result.reason, result.pages) == ("ok", None, 2)
    assert (result.extractor, result.extractor_version) == ("tesseract", "fake 1+tur-abc")
    assert "ocr" in result.warnings
    assert result.quality is not None
    assert result.quality["ocr_pass"] == [1, 2]
    raw = pipeline.cache_base(cache, result.sha256).with_suffix(".raw.txt")
    assert raw.read_text(encoding="utf-8") == GOOD + "\f" + GOOD


def test_process_file_ocr_with_unusable_text_is_ocr_low_quality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, scan, cache = _scan_corpus(tmp_path)
    _use_engine(monkeypatch, FakeEngine([WEAK] * 4))
    result = process_file(scan, root, cache)
    assert (result.status, result.reason) == ("needs_ocr", "ocr_low_quality")
    assert "ocr" in result.warnings


def test_process_file_ocr_of_partial_layer_keeps_text_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "p.pdf").write_bytes(make_pdf([GOOD[:200], "", GOOD[:200]]))
    engine = FakeEngine([GOOD])
    _use_engine(monkeypatch, engine)
    first = process_file(root / "p.pdf", root, tmp_path / "cache")
    assert first.status == "ok"
    assert first.quality is not None
    assert first.quality["ocr_pass"] == [None, 1, None]
    assert len(engine.calls) == 1


def test_process_file_ocr_reads_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "c"
    root.mkdir()
    (root / "pic.png").write_bytes((FIXTURES / "scan.png").read_bytes())
    _use_engine(monkeypatch, FakeEngine([GOOD]))
    result = process_file(root / "pic.png", root, tmp_path / "cache")
    assert (result.detected_type, result.status, result.pages) == ("image", "ok", 1)


def test_process_file_without_engine_stays_needs_ocr_and_says_why(tmp_path: Path) -> None:
    root, scan, cache = _scan_corpus(tmp_path)
    result = process_file(scan, root, cache)
    assert (result.status, result.reason) == ("needs_ocr", "no_text_layer")
    assert result.warnings == ["ocr_unavailable"]


def test_process_file_no_ocr_flag_skips_ocr_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, scan, cache = _scan_corpus(tmp_path)
    engine = FakeEngine([GOOD])
    _use_engine(monkeypatch, engine)
    result = process_file(scan, root, cache, ocr=False)
    assert (result.status, result.reason, result.warnings) == ("needs_ocr", "no_text_layer", [])
    assert not engine.calls


def test_ocr_result_is_cached_until_the_ocr_setup_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, scan, cache = _scan_corpus(tmp_path)
    engine = FakeEngine([GOOD, GOOD])
    _use_engine(monkeypatch, engine)
    assert not process_file(scan, root, cache).cached
    assert process_file(scan, root, cache).cached
    assert len(engine.calls) == 2  # the second run did not OCR again
    engine.fingerprint = "fp2"
    engine.texts = [GOOD, GOOD]
    assert not process_file(scan, root, cache).cached
    assert process_file(scan, root, cache).cached
    _use_engine(monkeypatch, None)  # Tesseract disappeared: the OCR'd entry no longer applies
    assert not process_file(scan, root, cache).cached


def test_files_without_ocr_stay_cached_when_the_ocr_setup_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, cache = _scan_corpus(tmp_path)
    engine = FakeEngine([])
    _use_engine(monkeypatch, engine)
    assert not process_file(root / "a.txt", root, cache).cached
    engine.fingerprint = "fp2"
    assert process_file(root / "a.txt", root, cache).cached


def test_real_tesseract_ocrs_synthetic_scans_to_ok(
    tmp_path: Path, real_tesseract: Tesseract
) -> None:
    root = tmp_path / "c"
    root.mkdir()
    for name in ("scan.pdf", "scan.png"):
        (root / name).write_bytes((FIXTURES / name).read_bytes())
    for name in ("scan.pdf", "scan.png"):
        result = process_file(root / name, root, tmp_path / "cache")
        assert (result.status, result.extractor) == ("ok", "tesseract")
        assert result.extractor_version == real_tesseract.extractor_version
        assert "ocr" in result.warnings
        clean = pipeline.cache_base(tmp_path / "cache", result.sha256).with_suffix(".clean.txt")
        text = clean.read_text(encoding="utf-8")
        assert all(w in text for w in ("kıdem", "tazminatı", "ücret"))
