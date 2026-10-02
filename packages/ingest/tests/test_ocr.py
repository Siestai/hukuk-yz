import hashlib
import os
import stat
from pathlib import Path

import pytest
from conftest import FIXTURES, GOOD, WEAK, WEAKER_LONG, FakeEngine, make_pdf

from hukuk_ingest import ocr
from hukuk_ingest.ocr import Tesseract, default_engine, ocr_image, ocr_pdf
from hukuk_ingest.quality import PAGE_BREAK


def _pdf(tmp_path: Path, pages: list[str]) -> Path:
    path = tmp_path / "x.pdf"
    path.write_bytes(make_pdf(pages))
    return path


def test_ocr_pdf_keeps_first_pass_when_page_is_sound(tmp_path: Path) -> None:
    engine = FakeEngine([GOOD, GOOD])
    doc = ocr_pdf(engine, _pdf(tmp_path, ["", ""]))
    assert doc.passes == [1, 1]
    assert doc.text == GOOD + PAGE_BREAK + GOOD
    assert [sauvola for sauvola, _ in engine.calls] == [False, False]
    assert engine.osd_calls == 0


def test_ocr_pdf_retries_weak_page_with_sauvola(tmp_path: Path) -> None:
    engine = FakeEngine([WEAK, GOOD])
    doc = ocr_pdf(engine, _pdf(tmp_path, [""]))
    assert (doc.text, doc.passes) == (GOOD, [2])
    assert [sauvola for sauvola, _ in engine.calls] == [False, True]
    assert engine.osd_calls == 0


def test_ocr_pdf_keeps_first_pass_when_sauvola_is_no_better(tmp_path: Path) -> None:
    engine = FakeEngine([WEAKER_LONG, WEAK])
    doc = ocr_pdf(engine, _pdf(tmp_path, [""]))  # OSD finds no rotation
    assert (doc.text, doc.passes) == (WEAKER_LONG, [1])


def test_ocr_pdf_falls_back_to_rotated_render_after_osd(tmp_path: Path) -> None:
    engine = FakeEngine([WEAK, WEAK, GOOD], turn=90)
    doc = ocr_pdf(engine, _pdf(tmp_path, [""]))
    assert (doc.text, doc.passes) == (GOOD, [3])
    assert engine.osd_calls == 1
    (_, plain), (_, sauvola), (rotated_sauvola, rotated) = engine.calls
    assert plain == sauvola == rotated[::-1]  # width and height swapped
    assert rotated_sauvola is False


def test_ocr_pdf_without_rotation_keeps_best_earlier_pass(tmp_path: Path) -> None:
    engine = FakeEngine([WEAK, WEAKER_LONG], turn=0)
    doc = ocr_pdf(engine, _pdf(tmp_path, [""]))
    assert (doc.text, doc.passes) == (WEAKER_LONG, [2])
    assert len(engine.calls) == 2


def test_ocr_pdf_partial_layer_ocrs_only_textless_pages(tmp_path: Path) -> None:
    engine = FakeEngine([GOOD])
    layer = ["metin katmanı", "", "metin katmanı"]
    doc = ocr_pdf(engine, _pdf(tmp_path, ["", "", ""]), layer)
    assert doc.text == PAGE_BREAK.join(["metin katmanı", GOOD, "metin katmanı"])
    assert doc.passes == [None, 1, None]
    assert len(engine.calls) == 1


def test_ocr_image_never_tries_rotation() -> None:
    engine = FakeEngine([WEAK, WEAK], turn=90)
    doc = ocr_image(engine, FIXTURES / "scan.png")
    assert doc.passes == [1]
    assert len(engine.calls) == 2
    assert engine.osd_calls == 0


def test_tesseract_fingerprint_changes_with_version_model_and_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = Tesseract("t", "tesseract 5.5.3", "aaaaaaaaaaaa")
    assert base.fingerprint == Tesseract("t", "tesseract 5.5.3", "aaaaaaaaaaaa").fingerprint
    assert base.fingerprint != Tesseract("t", "tesseract 5.5.4", "aaaaaaaaaaaa").fingerprint
    assert base.fingerprint != Tesseract("t", "tesseract 5.5.3", "bbbbbbbbbbbb").fingerprint
    before = base.fingerprint
    monkeypatch.setattr(ocr, "DPI", 200)
    assert base.fingerprint != before
    assert base.extractor_version == "tesseract 5.5.3+tur-aaaaaaaaaaaa"


def _fake_binary(tmp_path: Path, script: str) -> Path:
    path = tmp_path / "tesseract"
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_default_engine_reads_version_and_model_hash_from_the_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "tur.traineddata").write_bytes(b"model")
    binary = _fake_binary(
        tmp_path,
        f'case "$1" in\n--version) echo "tesseract 9.9.9";;\n'
        f"--list-langs) echo 'List of available languages in \"{tessdata}/\" (2):'; "
        f"echo eng; echo tur;;\nesac\n",
    )
    monkeypatch.setenv("HUKUK_TESSERACT", str(binary))
    engine = default_engine()
    assert engine is not None
    assert engine.version == "tesseract 9.9.9"
    assert engine.model_hash == hashlib.sha256(b"model").hexdigest()[:12]


def test_default_engine_is_none_without_binary_or_tur_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert default_engine() is None  # HUKUK_TESSERACT points nowhere
    binary = _fake_binary(
        tmp_path, "echo 'List of available languages in \"/tmp/\" (1):'; echo eng\n"
    )
    monkeypatch.setenv("HUKUK_TESSERACT", str(binary))
    default_engine.cache_clear()
    assert default_engine() is None


@pytest.mark.parametrize("script", ["", "echo; echo tesseract 9", "exit 2\n"])
def test_default_engine_is_none_when_version_output_is_unusable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str
) -> None:
    tessdata = tmp_path / "tessdata"
    tessdata.mkdir()
    (tessdata / "tur.traineddata").write_bytes(b"model")
    langs = f"echo 'List of available languages in \"{tessdata}/\" (2):'; echo eng; echo tur"
    binary = _fake_binary(
        tmp_path, f'case "$1" in\n--version) {script or "true"};;\n--list-langs) {langs};;\nesac\n'
    )
    monkeypatch.setenv("HUKUK_TESSERACT", str(binary))
    assert default_engine() is None


def test_tesseract_rotation_parses_osd_and_defaults_to_zero(tmp_path: Path) -> None:
    osd = _fake_binary(
        tmp_path, 'printf "Page number: 0\\nOrientation in degrees: 90\\nRotate: 270\\n"\n'
    )
    assert Tesseract(str(osd), "v", "m").rotation(b"img") == 270
    failing = _fake_binary(tmp_path, "echo 'Too few characters' >&2; exit 1\n")
    assert Tesseract(str(failing), "v", "m").rotation(b"img") == 0


def test_tesseract_runs_with_one_openmp_thread(tmp_path: Path) -> None:
    binary = _fake_binary(tmp_path, 'echo "threads=$OMP_THREAD_LIMIT"\n')
    assert Tesseract(str(binary), "v", "m").recognize(b"img", sauvola=False).strip() == "threads=1"


def test_tesseract_nonzero_exit_is_an_empty_page_so_later_passes_still_run(
    tmp_path: Path,
) -> None:
    binary = _fake_binary(tmp_path, "echo 'Too few characters' >&2; exit 1\n")
    assert Tesseract(str(binary), "v", "m").recognize(b"img", sauvola=False) == ""


@pytest.mark.parametrize("name", ["scan.pdf", "scan.png"])
def test_real_tesseract_reads_synthetic_scan(real_tesseract: Tesseract, name: str) -> None:
    path = FIXTURES / name
    doc = (
        ocr_pdf(real_tesseract, path) if name.endswith(".pdf") else ocr_image(real_tesseract, path)
    )
    assert doc.passes == [1]
    for word in ("ücret", "süresi", "kıdem", "tazminatı", "çözüm"):
        assert word in doc.text


def test_default_engine_finds_real_binary(real_tesseract: Tesseract) -> None:
    assert os.path.isabs(real_tesseract.binary)
    assert real_tesseract.version.startswith("tesseract ")
    assert len(real_tesseract.model_hash) == 12
