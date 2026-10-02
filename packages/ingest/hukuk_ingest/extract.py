"""Per-type raw text extraction. Raw text is stored as produced (CRLF etc.); see clean.py."""

import re
import zipfile
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import pypdfium2 as pdfium
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from hukuk_ingest.detect import DetectedType
from hukuk_ingest.quality import PAGE_BREAK

_CDATA_RE = re.compile(r"<content>\s*<!\[CDATA\[(.*?)\]\]>\s*</content>", re.DOTALL)


@dataclass(frozen=True)
class Extraction:
    """Outcome of one extractor. `text is None` means nothing was extracted (see status)."""

    status: str
    text: str | None = None
    reason: str | None = None
    pages: int | None = None
    signed: bool | None = None
    extractor: str = "none"
    extractor_version: str = ""


def _pdf(path: Path) -> Extraction:
    pages: list[str] = []
    doc = pdfium.PdfDocument(path)
    try:
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            try:
                pages.append(textpage.get_text_range())
            finally:
                textpage.close()
                page.close()
    finally:
        doc.close()
    return Extraction(
        "ok",
        PAGE_BREAK.join(pages),
        pages=len(pages),
        extractor="pypdfium2",
        extractor_version=version("pypdfium2"),
    )


def _docx(path: Path) -> Extraction:
    document = Document(str(path))
    parts: list[str] = []
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            parts.append(block.text)
        elif isinstance(block, Table):
            for row in block.rows:
                parts.append("\t".join(cell.text for cell in row.cells))
    return Extraction(
        "ok", "\n".join(parts), extractor="python-docx", extractor_version=version("python-docx")
    )


def _udf(path: Path) -> Extraction:
    with zipfile.ZipFile(path) as zf:
        content = zf.read("content.xml").decode("utf-8")
        signed = "sign.sgn" in zf.namelist()
    match = _CDATA_RE.search(content)
    if match is None:
        return Extraction("error", reason="udf_no_content", signed=signed, extractor="udf-zip")
    return Extraction(
        "ok", match.group(1), signed=signed, extractor="udf-zip", extractor_version="1"
    )


def _text(path: Path) -> Extraction:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1254", errors="replace")
    return Extraction("ok", text, extractor="plain-text", extractor_version="1")


def extract(path: Path, detected: DetectedType) -> Extraction:
    match detected:
        case DetectedType.PDF:
            return _pdf(path)
        case DetectedType.DOCX:
            return _docx(path)
        case DetectedType.UDF:
            return _udf(path)
        case DetectedType.TEXT:
            return _text(path)
        case DetectedType.DOC:
            return Extraction("unsupported", reason="legacy_doc")
        case DetectedType.HTML:
            return Extraction("rejected", reason="html_stub")
        case DetectedType.IMAGE:
            return Extraction("needs_ocr", reason="image")
        case _:
            return Extraction("skipped", reason=f"type_{detected.value}")
