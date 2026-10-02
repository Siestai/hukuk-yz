from pathlib import Path
from typing import Any

import pytest
from word_doc import make_doc

from hukuk_ingest.detect import DetectedType, detect
from hukuk_ingest.extract import extract
from hukuk_ingest.legacy_doc import UnsupportedDoc, read_doc


def _write(
    tmp_path: Path,
    name: str = "a.doc",
    pieces: list[tuple[str, bool]] | None = None,
    **kwargs: Any,
) -> Path:
    path = tmp_path / name
    path.write_bytes(make_doc(pieces or [("Madde 1 - işçi\r", True)], **kwargs))
    return path


def test_read_doc_joins_8bit_cp1254_and_utf16_pieces(tmp_path: Path) -> None:
    pieces = [("Madde 1 - İşçi ücreti ğüşiöç\r", True), ("Çalışma süresi ıİ\r", False)]
    text = read_doc(_write(tmp_path, pieces=pieces))
    assert text == "Madde 1 - İşçi ücreti ğüşiöç\nÇalışma süresi ıİ\n"


def test_read_doc_keeps_field_results_and_drops_instructions(tmp_path: Path) -> None:
    pieces = [
        ('a \x13 HYPERLINK "x" \x14sonuç \x13 PAGE \x14metni\x15\x15 b\x13 SEQ 1\x15 c\r', False)
    ]
    assert read_doc(_write(tmp_path, pieces=pieces)) == "a sonuç metni b c\n"


def test_read_doc_maps_table_cells_to_tabs_and_strips_controls(tmp_path: Path) -> None:
    pieces = [("ücret\x07ıslak\x07\x07\x01\x02sonra\x0bsatır\r", True)]
    assert read_doc(_write(tmp_path, pieces=pieces)) == "ücret\tıslak\t\tsonra\nsatır\n"


def test_read_doc_uses_1table_stream_when_flagged(tmp_path: Path) -> None:
    path = _write(tmp_path, table_stream="1Table")
    assert read_doc(path) == "Madde 1 - işçi\n"


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [({"encrypted": True}, "encrypted_doc"), ({"n_fib": 0x65}, "legacy_doc_pre97")],
)
def test_read_doc_rejects_unsupported_variants(
    tmp_path: Path, kwargs: dict[str, Any], reason: str
) -> None:
    with pytest.raises(UnsupportedDoc) as exc:
        read_doc(_write(tmp_path, **kwargs))
    assert exc.value.reason == reason


def test_extract_doc_is_ok_even_when_named_pdf(tmp_path: Path) -> None:
    path = _write(tmp_path, "scan.pdf")
    detection = detect(path)
    assert (detection.type, detection.extension_mismatch) == (DetectedType.DOC, True)
    ex = extract(path, detection.type)
    assert (ex.status, ex.extractor) == ("ok", "olefile-piece-table")
    assert ex.text == "Madde 1 - işçi\n"
    assert ex.extractor_version


def test_extract_encrypted_doc_is_unsupported(tmp_path: Path) -> None:
    ex = extract(_write(tmp_path, encrypted=True), DetectedType.DOC)
    assert (ex.status, ex.reason, ex.text) == ("unsupported", "encrypted_doc", None)
