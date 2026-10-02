"""Regenerates scan.png and scan.pdf, the synthetic scanned page used by the OCR integration test.

Run from the repo root: `uv run python packages/ingest/tests/fixtures/make_scan_fixtures.py`.
A made-up Turkish sentence is rendered to 300 dpi grayscale pixels, then stored as a bare PNG and
as a PDF whose only content is that image (no text layer). The sentence avoids ş, ğ and İ: the
renderer's standard font lacks those glyphs. No personal data.
"""

import struct
import sys
import zlib
from pathlib import Path

import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from conftest import make_pdf  # noqa: E402

SENTENCE = "ücret ödemesi süresi için kıdem tazminatı ile bu madde hakkında çözüm gerekir"
DPI = 300
CROP_TOP, CROP_BOTTOM = 330, 530  # pixel rows around the text line


def _render() -> tuple[int, int, bytes]:
    doc = pdfium.PdfDocument(make_pdf([SENTENCE]))
    bitmap = doc[0].render(scale=DPI / 72, grayscale=True)
    rows = [
        bytes(bitmap.buffer[i * bitmap.stride : i * bitmap.stride + bitmap.width])
        for i in range(CROP_TOP, CROP_BOTTOM)
    ]
    return bitmap.width, CROP_BOTTOM - CROP_TOP, b"".join(rows)


def _png(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body)
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + pixels[y * width : (y + 1) * width] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _pdf(width: int, height: int, pixels: bytes) -> bytes:
    data = zlib.compress(pixels, 9)
    w_pt, h_pt = width * 72 / DPI, height * 72 / DPI
    content = f"q {w_pt:.2f} 0 0 {h_pt:.2f} 0 0 cm /Im0 Do Q".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w_pt:.2f} {h_pt:.2f}] /Contents 4 0 R "
        f"/Resources << /XObject << /Im0 5 0 R >> >> >>".encode(),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace "
        f"/DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\n"
        "stream\n".encode()
        + data
        + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    w, h, px = _render()
    (HERE / "scan.png").write_bytes(_png(w, h, px))
    (HERE / "scan.pdf").write_bytes(_pdf(w, h, px))
