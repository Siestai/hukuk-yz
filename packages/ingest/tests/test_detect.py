from pathlib import Path

import pytest
from conftest import make_ole2, make_zip

from hukuk_ingest.detect import DetectedType, detect

CORPUS_CASES = [
    ("text.pdf", DetectedType.PDF, False),
    ("a.docx", DetectedType.DOCX, False),
    ("b.udf", DetectedType.UDF, False),
    ("sheet.xlsx", DetectedType.XLSX_XLSM, False),
    ("legacy.pdf", DetectedType.DOC, True),
    ("stub.pdf", DetectedType.HTML, True),
    ("pic.jpg", DetectedType.IMAGE, False),
    ("note.txt", DetectedType.TEXT, False),
    ("Thumbs.db", DetectedType.UNKNOWN, False),
]


@pytest.mark.parametrize(("name", "expected", "mismatch"), CORPUS_CASES)
def test_detect_type_and_extension_mismatch(
    corpus: Path, name: str, expected: DetectedType, mismatch: bool
) -> None:
    result = detect(corpus / name)
    assert result.type is expected
    assert result.extension_mismatch is mismatch


def test_detect_ignores_extension(corpus: Path, tmp_path: Path) -> None:
    renamed = tmp_path / "report.docx"
    renamed.write_bytes((corpus / "text.pdf").read_bytes())
    result = detect(renamed)
    assert result.type is DetectedType.PDF
    assert result.extension_mismatch


@pytest.mark.parametrize(
    ("streams", "truncate", "expected"),
    [
        (("WordDocument",), None, DetectedType.DOC),
        (("Workbook",), None, DetectedType.XLS),
        (("Book",), None, DetectedType.XLS),
        (("Catalog",), None, DetectedType.UNKNOWN),
        (("WordDocument",), 100, DetectedType.UNKNOWN),
    ],
)
def test_detect_ole2_subtype_from_stream_names(
    tmp_path: Path, streams: tuple[str, ...], truncate: int | None, expected: DetectedType
) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(make_ole2(*streams)[:truncate])
    assert detect(path).type is expected


@pytest.mark.parametrize("name", ["Thumbs.db", "renamed.bin", "~$lock.docx"])
def test_detect_file_name_never_decides(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_bytes(make_ole2("Catalog"))
    assert detect(tmp_path / name).type is DetectedType.UNKNOWN


def test_detect_office_lock_file_is_unknown(tmp_path: Path) -> None:
    lock = tmp_path / "~$x.docx"
    lock.write_bytes(b"\x0fowner\x00\x00\x00" + b"\x00" * 150)
    assert detect(lock).type is DetectedType.UNKNOWN


@pytest.mark.parametrize("ext", ["odt", "ods"])
def test_detect_odf_is_not_udf(tmp_path: Path, ext: str) -> None:
    path = make_zip(
        tmp_path / f"doc.{ext}",
        {
            "mimetype": "application/vnd.oasis.opendocument.text",
            "content.xml": "<office:document-content/>",
        },
    )
    assert detect(path).type is DetectedType.UNKNOWN


def test_detect_unsigned_udf_needs_content_element(tmp_path: Path) -> None:
    udf = make_zip(
        tmp_path / "ok.udf",
        {"content.xml": "<template><content><![CDATA[x]]></content></template>"},
    )
    other = make_zip(tmp_path / "other.zip", {"content.xml": "<foo/>"})
    assert detect(udf).type is DetectedType.UDF
    assert detect(other).type is DetectedType.UNKNOWN


def test_detect_corrupt_zip_is_unknown(tmp_path: Path) -> None:
    path = tmp_path / "bad.docx"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 40)
    assert detect(path).type is DetectedType.UNKNOWN


@pytest.mark.parametrize(
    "data",
    [
        b"\xef\xbb\xbf  \n<!DOCTYPE HTML PUBLIC>\n<html>",
        b'<?xml version="1.0"?>\n<html xmlns="x"><body>err</body></html>',
        b"<!-- cached -->\n<html><body>err</body></html>",
        b"<head><title>x</title></head><body>err</body>",
        b"<body>Not found</body>",
        b"<HTML><BODY>ERR</BODY></HTML>",
        b"<script>location='/x'</script>",
    ],
)
def test_detect_html_variants(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "stub.pdf"
    path.write_bytes(data)
    assert detect(path).type is DetectedType.HTML


@pytest.mark.parametrize(
    ("name", "data", "expected"),
    [
        ("a.xml", b'<?xml version="1.0"?><a>1</a>', DetectedType.TEXT),
        ("legacy.txt", "İşçi ücreti ğüşiöç ve kıdem".encode("cp1254") * 3, DetectedType.TEXT),
        ("a.gif", b"GIF89a" + b"\x00" * 20, DetectedType.IMAGE),
        ("a.rtf", b"{\\rtf1\\ansi hello}", DetectedType.UNKNOWN),
    ],
)
def test_detect_other_formats(
    tmp_path: Path, name: str, data: bytes, expected: DetectedType
) -> None:
    path = tmp_path / name
    path.write_bytes(data)
    assert detect(path).type is expected
