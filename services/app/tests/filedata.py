"""Small real files for the file store, files API and worker tests."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCAN_PNG = REPO / "packages" / "ingest" / "tests" / "fixtures" / "scan.png"

SENTENCE = (
    "Isci kidem tazminatina hak kazanmak icin ayni isyerinde en az bir yil calismis olmalidir. "
    "Is sozlesmesinin haklı nedenle feshi halinde ihbar suresi aranmaz ve odeme yapilir. "
)


def make_pdf(text: str = SENTENCE * 6) -> bytes:
    """A one-page PDF with a text layer (ASCII text; Helvetica)."""
    escaped = text.encode("ascii", "replace").replace(b"(", b"\\(").replace(b")", b"\\)")
    lines = [escaped[i : i + 90] for i in range(0, len(escaped), 90)]
    stream = b"BT /F1 10 Tf 12 TL 40 750 Td " + b" T* ".join(b"(" + x + b") Tj" for x in lines)
    stream += b" ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R "
        b"/Resources << /Font << /F1 3 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
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
