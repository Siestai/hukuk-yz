"""Type detection from magic bytes and container structure, never from the extension."""

import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from struct import error as struct_error
from struct import unpack_from

_HEAD_BYTES = 8192
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_OLE2_ENTRY = 128
_OLE2_END = 0xFFFFFFFE
_OLE2_MAX_DIR_SECTORS = 256
_HTML_MARKERS = (b"<!doctype html", b"<html", b"<head", b"<body")
_HTML_STARTS = (*_HTML_MARKERS, b"<script", b"<meta", b"<title")
_HTML_SNIFF_BYTES = 1024


class DetectedType(StrEnum):
    PDF = "pdf"
    DOC = "doc"
    XLS = "xls"
    DOCX = "docx"
    UDF = "udf"
    XLSX_XLSM = "xlsx_xlsm"
    HTML = "html"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"


# Extension -> the types that are consistent with it. Unlisted extensions never mismatch.
_EXPECTED: dict[str, frozenset[DetectedType]] = {
    ".pdf": frozenset({DetectedType.PDF}),
    ".doc": frozenset({DetectedType.DOC}),
    ".docx": frozenset({DetectedType.DOCX}),
    ".udf": frozenset({DetectedType.UDF}),
    ".xlsx": frozenset({DetectedType.XLSX_XLSM}),
    ".xlsm": frozenset({DetectedType.XLSX_XLSM}),
    ".html": frozenset({DetectedType.HTML}),
    ".htm": frozenset({DetectedType.HTML}),
    ".jpg": frozenset({DetectedType.IMAGE}),
    ".jpeg": frozenset({DetectedType.IMAGE}),
    ".png": frozenset({DetectedType.IMAGE}),
    ".txt": frozenset({DetectedType.TEXT}),
}


@dataclass(frozen=True)
class Detection:
    type: DetectedType
    extension_mismatch: bool


def _is_uyap(zf: zipfile.ZipFile, names: set[str]) -> bool:
    """UYAP .udf: content.xml without an ODF mimetype, signed or with a <content> element."""
    if "mimetype" in names and zf.read("mimetype").startswith(
        b"application/vnd.oasis.opendocument"
    ):
        return False
    if "sign.sgn" in names:
        return True
    with zf.open("content.xml") as fh:
        head = fh.read(65536)
    return b"<content>" in head or b"<content " in head


def _detect_zip(path: Path) -> DetectedType:
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "word/document.xml" in names:
                return DetectedType.DOCX
            if any(n.startswith("xl/") for n in names):
                return DetectedType.XLSX_XLSM
            if "content.xml" in names and _is_uyap(zf, names):
                return DetectedType.UDF
    except (zipfile.BadZipFile, KeyError, OSError):
        pass
    return DetectedType.UNKNOWN


def _ole2_stream_names(path: Path) -> set[str]:
    """Directory entry names of an OLE2 compound file (minimal CFB reader, no dependency)."""
    with path.open("rb") as fh:
        header = fh.read(512)
        shift = unpack_from("<H", header, 30)[0]
        if not 7 <= shift <= 16:
            return set()
        size = 1 << shift
        first_dir = unpack_from("<I", header, 48)[0]
        n_fat = unpack_from("<I", header, 44)[0]
        difat = [x for x in unpack_from("<109I", header, 76) if x < _OLE2_END][:n_fat]

        def sector(index: int) -> bytes:
            fh.seek(size * (index + 1))
            return fh.read(size)

        fat: list[int] = []
        for fat_sector in difat:
            data = sector(fat_sector)
            fat.extend(unpack_from(f"<{len(data) // 4}I", data))
        names: set[str] = set()
        current = first_dir
        for _ in range(_OLE2_MAX_DIR_SECTORS):
            if current >= _OLE2_END or current >= len(fat):
                break
            data = sector(current)
            for off in range(0, len(data) - _OLE2_ENTRY + 1, _OLE2_ENTRY):
                name_len = unpack_from("<H", data, off + 64)[0]
                if 2 <= name_len <= 64 and data[off + 66] != 0:
                    names.add(data[off : off + name_len - 2].decode("utf-16-le", "replace"))
            current = fat[current]
    return names


def _detect_ole2(path: Path) -> DetectedType:
    try:
        names = _ole2_stream_names(path)
    except (OSError, struct_error):
        return DetectedType.UNKNOWN
    if "WordDocument" in names:
        return DetectedType.DOC
    if names & {"Workbook", "Book"}:
        return DetectedType.XLS
    return DetectedType.UNKNOWN


def _looks_like_html(head: bytes) -> bool:
    probe = head.removeprefix(b"\xef\xbb\xbf").lstrip(b" \t\r\n\x0c").lower()
    if probe.startswith(_HTML_STARTS):
        return True
    # "<?xml ...?><html>" and "<!-- ... --><html>": only HTML if an HTML tag follows early.
    if probe.startswith((b"<?xml", b"<!--")):
        return any(m in probe[:_HTML_SNIFF_BYTES] for m in _HTML_MARKERS)
    return False


_CONTROL_BYTES = bytes(set(range(32)) - {9, 10, 12, 13}) + b"\x7f"


def _looks_like_text(head: bytes) -> bool:
    if not head or b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte sequence cut by the read window is fine; anything earlier is only
        # text if it is a legacy single-byte (cp1254) file, i.e. free of control bytes.
        if exc.start < len(head) - 4 and head.translate(None, _CONTROL_BYTES) != head:
            return False
    return True


def detect_type(path: Path) -> DetectedType:
    """Content only: the file name (Thumbs.db, ~$ lock files) never decides."""
    with path.open("rb") as fh:
        head = fh.read(_HEAD_BYTES)
    if b"%PDF-" in head[:1024]:
        return DetectedType.PDF
    if head.startswith(_OLE2_MAGIC):
        return _detect_ole2(path)
    if head.startswith(b"PK\x03\x04"):
        return _detect_zip(path)
    if head.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a")):
        return DetectedType.IMAGE
    if head.startswith(b"{\\rtf"):
        return DetectedType.UNKNOWN
    if _looks_like_html(head):
        return DetectedType.HTML
    if _looks_like_text(head):
        return DetectedType.TEXT
    return DetectedType.UNKNOWN


def detect(path: Path) -> Detection:
    detected = detect_type(path)
    expected = _EXPECTED.get(path.suffix.lower())
    mismatch = expected is not None and detected not in expected
    return Detection(type=detected, extension_mismatch=mismatch)
