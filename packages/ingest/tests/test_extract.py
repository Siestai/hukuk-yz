from pathlib import Path

import pytest
from conftest import make_ole2

from hukuk_ingest.detect import DetectedType, detect
from hukuk_ingest.extract import extract


def test_extract_pdf_keeps_turkish_letters_and_page_breaks(corpus: Path) -> None:
    ex = extract(corpus / "text.pdf", DetectedType.PDF)
    assert ex.status == "ok"
    assert ex.pages == 2
    assert ex.text is not None
    assert ex.text.count("\f") == 1
    for fragment in ("İşçinin", "kıdem", "çalışması", "ğş çöü"):
        assert fragment in ex.text


def test_extract_docx_includes_paragraphs_and_tables(corpus: Path) -> None:
    ex = extract(corpus / "a.docx", DetectedType.DOCX)
    assert ex.text is not None
    assert "İşveren ve işçi ğış" in ex.text
    assert "ücret\tıslak" in ex.text


def test_extract_udf_reads_cdata_and_signature(corpus: Path) -> None:
    ex = extract(corpus / "b.udf", DetectedType.UDF)
    assert ex.text is not None
    assert "T.C. İŞÇİ" in ex.text
    assert ex.signed is True


def test_extract_text_decodes_legacy_cp1254(tmp_path: Path) -> None:
    sentence = "İşçi ücreti ğüşiöç ve kıdem"
    path = tmp_path / "legacy.txt"
    path.write_bytes(sentence.encode("cp1254") * 3)
    assert extract(path, DetectedType.TEXT).text == sentence * 3


@pytest.mark.parametrize(
    ("name", "detected", "status", "reason"),
    [
        ("stub.pdf", DetectedType.HTML, "rejected", "html_stub"),
        ("pic.jpg", DetectedType.IMAGE, "needs_ocr", "image"),
        ("sheet.xlsx", DetectedType.XLSX_XLSM, "skipped", "type_xlsx_xlsm"),
        ("Thumbs.db", DetectedType.UNKNOWN, "skipped", "type_unknown"),
    ],
)
def test_extract_without_text_reports_status(
    corpus: Path, name: str, detected: DetectedType, status: str, reason: str
) -> None:
    ex = extract(corpus / name, detected)
    assert ex.text is None
    assert (ex.status, ex.reason) == (status, reason)


def test_extract_legacy_xls_is_skipped_not_doc(tmp_path: Path) -> None:
    path = tmp_path / "x.doc"
    path.write_bytes(make_ole2("Workbook"))
    ex = extract(path, detect(path).type)
    assert (ex.status, ex.reason) == ("skipped", "type_xls")
