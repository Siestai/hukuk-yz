"""Local Tesseract OCR for scanned pages. Text never leaves the machine (KVKK, md. 31)."""

import hashlib
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import pypdfium2 as pdfium

from hukuk_ingest import quality
from hukuk_ingest.quality import PAGE_BREAK, stopword_ratio

LANG = "tur"
DPI = 300
PSM = 3
# Leptonica adaptive Otsu (1) and Sauvola (2); pass 2 tries both. 0 is the default (Otsu).
THRESHOLDING_METHODS = (1, 2)
TIMEOUT_SECONDS = 600
_BINARY_ENV = "HUKUK_TESSERACT"
_TESSDATA_ENV = "TESSDATA_PREFIX"
_TESSDATA_LINE_RE = re.compile(r'"(.+?)"')
_ROTATE_RE = re.compile(r"^Rotate:\s*(\d+)", re.MULTILINE)


class Engine(Protocol):
    """What the page loop needs from an OCR engine; tests substitute a fake."""

    @property
    def extractor_version(self) -> str: ...

    @property
    def fingerprint(self) -> str: ...

    def recognize(self, image: bytes, *, thresholding: int) -> str:
        """`thresholding` is Tesseract's `thresholding_method`; 0 is its default."""
        ...

    def rotation(self, image: bytes) -> int:
        """Clockwise degrees (0/90/180/270) that bring the page upright; 0 when undetectable."""
        ...


@dataclass(frozen=True)
class Tesseract:
    binary: str
    version: str
    model_hash: str

    @property
    def extractor_version(self) -> str:
        return f"{self.version}+{LANG}-{self.model_hash}"

    @property
    def fingerprint(self) -> str:
        """Everything that decides OCR output: engine version, model and settings."""
        settings = (DPI, LANG, PSM, THRESHOLDING_METHODS) + (
            quality.MIN_CHARS_PER_PAGE,
            quality.BAD_OCR_RATIO,
        )
        parts = (self.version, self.model_hash, settings)
        return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]

    def _run(self, args: list[str], image: bytes) -> subprocess.CompletedProcess[bytes]:
        env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
        return subprocess.run(
            [self.binary, "stdin", "stdout", *args],
            input=image,
            capture_output=True,
            env=env,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )

    def recognize(self, image: bytes, *, thresholding: int) -> str:
        args = ["-l", LANG, "--psm", str(PSM)]
        if thresholding:
            args += ["-c", f"thresholding_method={thresholding}"]
        done = self._run(args, image)
        if done.returncode != 0:  # e.g. "Too few characters" on a blank page: a weak page
            return ""
        return done.stdout.decode("utf-8")

    def rotation(self, image: bytes) -> int:
        done = self._run(["-l", "osd", "--psm", "0"], image)
        match = _ROTATE_RE.search(done.stdout.decode("utf-8", errors="replace"))
        return int(match.group(1)) if done.returncode == 0 and match else 0


def _model_dir(binary: str) -> Path | None:
    """Tessdata directory and `tur` availability as reported by the binary itself."""
    done = subprocess.run(
        [binary, "--list-langs"], capture_output=True, text=True, timeout=60, check=False
    )
    lines = (done.stdout or done.stderr).splitlines()
    if done.returncode != 0 or not lines or LANG not in {line.strip() for line in lines[1:]}:
        return None
    match = _TESSDATA_LINE_RE.search(lines[0])
    return Path(match.group(1)) if match else None


@lru_cache(maxsize=1)
def default_engine() -> Tesseract | None:
    """Tesseract from `HUKUK_TESSERACT` (else PATH) with the `tur` model, or None."""
    binary = shutil.which(os.environ.get(_BINARY_ENV) or "tesseract")
    if binary is None:
        return None
    try:
        tessdata = _model_dir(binary)
        if tessdata is None:
            return None
        model = (tessdata / f"{LANG}.traineddata").read_bytes()
        done = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (done.stdout or done.stderr).splitlines()
    if done.returncode != 0 or not lines or not lines[0].strip():
        return None
    return Tesseract(binary, lines[0].strip(), hashlib.sha256(model).hexdigest()[:12])


@dataclass(frozen=True)
class OcrDocument:
    text: str
    # Per page: the pass that produced it (1 default, 2 adaptive thresholding, 3 rotated);
    # None = not OCR'd.
    passes: list[int | None]
    # Per page: the thresholding_method of the winning pass 2 (1 or 2); None otherwise.
    thresholds: list[int | None]


# Renders the page rotated clockwise by the given degrees.
Rotate = Callable[[int], bytes]


def _is_weak(text: str) -> bool:
    visible = sum(not c.isspace() for c in text)
    if visible < quality.MIN_CHARS_PER_PAGE:
        return True
    tokens, ratio = stopword_ratio(text)
    return tokens >= quality.MIN_TOKENS and (ratio or 0.0) < quality.BAD_OCR_RATIO


def _better(new: str, old: str) -> bool:
    if _is_weak(new) != _is_weak(old):
        return _is_weak(old)
    return sum(not c.isspace() for c in new) > sum(not c.isspace() for c in old)


def _ocr_page(engine: Engine, image: bytes, rotate: Rotate | None) -> tuple[str, int, int | None]:
    """(text, pass, thresholding method of pass 2 when it won)."""
    best, best_pass, method = engine.recognize(image, thresholding=0), 1, None
    if not _is_weak(best):
        return best, best_pass, method
    for candidate in THRESHOLDING_METHODS:
        second = engine.recognize(image, thresholding=candidate)
        if _better(second, best):
            best, best_pass, method = second, 2, candidate
    if _is_weak(best) and rotate is not None and (turn := engine.rotation(image)):
        third = engine.recognize(rotate(turn), thresholding=0)
        if _better(third, best):
            best, best_pass, method = third, 3, None
    return best, best_pass, method


def _pgm(bitmap: pdfium.PdfBitmap) -> bytes:
    rows = [
        bytes(bitmap.buffer[i * bitmap.stride : i * bitmap.stride + bitmap.width])
        for i in range(bitmap.height)
    ]
    return b"P5\n%d %d\n255\n" % (bitmap.width, bitmap.height) + b"".join(rows)


def ocr_pdf(engine: Engine, path: Path, layer_pages: list[str] | None = None) -> OcrDocument:
    """OCR every page, or only the pages without text when `layer_pages` (the existing text layer
    per page) is given; the text of the other pages is kept."""
    texts: list[str] = []
    passes: list[int | None] = []
    thresholds: list[int | None] = []
    doc = pdfium.PdfDocument(path)
    try:
        for i in range(len(doc)):
            if layer_pages is not None and layer_pages[i].strip():
                texts.append(layer_pages[i])
                passes.append(None)
                thresholds.append(None)
                continue
            page = doc[i]
            try:

                def render(turn: int, page: pdfium.PdfPage = page) -> bytes:
                    return _pgm(page.render(scale=DPI / 72, grayscale=True, rotation=turn))

                text, used, method = _ocr_page(engine, render(0), render)
            finally:
                page.close()
            texts.append(text)
            passes.append(used)
            thresholds.append(method)
    finally:
        doc.close()
    return OcrDocument(PAGE_BREAK.join(texts), passes, thresholds)


def ocr_image(engine: Engine, path: Path) -> OcrDocument:
    """A photo or scan is one page; rotation is not tried (no imaging library to rotate with)."""
    data = path.read_bytes()
    text, used, method = _ocr_page(engine, data, None)
    return OcrDocument(text, [used], [method])
