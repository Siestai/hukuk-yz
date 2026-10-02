"""Per-file pipeline: hash, detect, (cached) extract, quality, clean, write cache."""

import hashlib
import importlib.util
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any

from hukuk_ingest import quality
from hukuk_ingest.clean import clean_text
from hukuk_ingest.detect import DetectedType, detect
from hukuk_ingest.extract import extract
from hukuk_ingest.ocr import Engine, default_engine, ocr_image, ocr_pdf
from hukuk_ingest.quality import PAGE_BREAK, judge, measure

# Bump for pipeline.py logic changes the fingerprint below cannot see (e.g. cache layout).
PIPELINE_VERSION = "2"
_LONE_SURROGATE_RE = re.compile("[\ud800-\udfff]")


@lru_cache(maxsize=1)
def _code_fingerprint() -> str:
    """Source of every module that shapes the cached output, plus extractor library versions."""
    h = hashlib.sha256()
    for name in ("clean", "detect", "extract", "legacy_doc", "ocr", "quality"):
        spec = importlib.util.find_spec(f"hukuk_ingest.{name}")
        h.update(Path(str(spec and spec.origin)).read_bytes())
    h.update(f"{version('pypdfium2')}|{version('python-docx')}|{version('olefile')}".encode())
    return h.hexdigest()[:16]


def cache_key() -> str:
    """Cache entries are valid only for this exact code, thresholds and library set."""
    return f"{PIPELINE_VERSION}-{_code_fingerprint()}-{quality.fingerprint()}"


@dataclass
class FileResult:
    path: str
    sha256: str
    size: int
    ext: str
    detected_type: str
    extension_mismatch: bool
    status: str
    reason: str | None = None
    pages: int | None = None
    chars: int | None = None
    quality: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    signed: bool | None = None
    text_ref: str | None = None
    extractor: str = "none"
    extractor_version: str = ""
    cached: bool = False
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CACHED_FIELDS = (
    "detected_type",
    "status",
    "reason",
    "pages",
    "chars",
    "quality",
    "warnings",
    "signed",
    "text_ref",
    "extractor",
    "extractor_version",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def cache_base(cache_dir: Path, sha: str) -> Path:
    return cache_dir / sha[:2] / sha


def _write_atomic(target: Path, data: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _load_meta(base: Path, ocr_key: str) -> dict[str, Any] | None:
    """The cached entry, or None when it is absent, stale, malformed or incomplete.

    Entries that went through the OCR route are valid only for the OCR setup that produced them
    (`ocr_key`: the engine fingerprint, "off" or "unavailable"); the rest do not depend on it.
    """
    try:
        meta = json.loads(base.with_suffix(".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get("pipeline_version") != cache_key():
        return None
    if not all(key in meta for key in _CACHED_FIELDS):
        return None
    if not isinstance(meta["status"], str) or not isinstance(meta["detected_type"], str):
        return None
    if not isinstance(meta["warnings"], list):
        return None
    if meta.get("ocr_key") not in (None, ocr_key):
        return None
    if meta["text_ref"] and not (
        base.with_suffix(".raw.txt").is_file() and base.with_suffix(".clean.txt").is_file()
    ):
        return None
    return meta


def process_file(
    path: Path, root: Path, cache_dir: Path, force: bool = False, ocr: bool = True
) -> FileResult:
    start = time.perf_counter()
    rel = path.relative_to(root).as_posix()
    result = FileResult(
        path=rel,
        sha256="",
        size=0,
        ext=path.suffix.lower(),
        detected_type="unknown",
        extension_mismatch=False,
        status="error",
    )
    try:
        result.size = path.stat().st_size
        result.sha256 = sha256_file(path)
        detection = detect(path)
        result.detected_type = detection.type.value
        result.extension_mismatch = detection.extension_mismatch
        base = cache_base(cache_dir, result.sha256)
        engine = default_engine() if ocr else None
        ocr_key = engine.fingerprint if engine else ("unavailable" if ocr else "off")

        meta = None if force else _load_meta(base, ocr_key)
        if meta is not None:
            for key in _CACHED_FIELDS:
                setattr(result, key, meta[key])
            result.cached = True
        else:
            _extract_and_store(path, detection.type, base, result, engine, ocr_key)
    except Exception as exc:  # one bad file must not stop the run
        result.status = "error"
        result.reason = "exception"
        result.error = f"{type(exc).__name__}: {exc}"
    result.duration_ms = round((time.perf_counter() - start) * 1000)
    return result


def error_result(path: Path, root: Path, reason: str, message: str) -> FileResult:
    """A result for a file whose worker died before it could report."""
    result = FileResult(
        path=path.relative_to(root).as_posix(),
        sha256="",
        size=0,
        ext=path.suffix.lower(),
        detected_type="unknown",
        extension_mismatch=False,
        status="error",
        reason=reason,
        error=message,
    )
    try:
        result.size = path.stat().st_size
        result.sha256 = sha256_file(path)
    except OSError:
        pass
    return result


def _score(
    result: FileResult,
    text: str,
    pages: int | None,
    *,
    judged: bool,
    ocr_passes: list[int | None] | None = None,
) -> str:
    """Sanitize `text`, record its quality and, for page-based text, route it to OCR if unfit."""
    if _LONE_SURROGATE_RE.search(text):
        text = _LONE_SURROGATE_RE.sub("\ufffd", text)
        result.warnings.append("lone_surrogates")
    q = measure(text, pages)
    result.chars, result.quality = q.chars, q.to_dict()
    if ocr_passes is not None:
        result.quality["ocr_pass"] = ocr_passes
    if judged:
        verdict = judge(q)
        if not verdict.ok:
            result.status = "needs_ocr"
            result.reason = "ocr_low_quality" if ocr_passes is not None else verdict.reason
        result.warnings += verdict.warnings
    return text


def _run_ocr(
    path: Path, detected: DetectedType, text: str | None, result: FileResult, engine: Engine
) -> str:
    """Replace a missing or unfit text layer by OCR text; a partial layer keeps its good pages."""
    if detected is not DetectedType.PDF:
        doc = ocr_image(engine, path)
    else:
        layer = text.split(PAGE_BREAK) if text and result.reason == "partial_text_layer" else None
        doc = ocr_pdf(engine, path, layer)
    result.status, result.reason, result.warnings = "ok", None, []
    result.pages = len(doc.passes)
    result.extractor, result.extractor_version = "tesseract", engine.extractor_version
    scored = _score(result, doc.text, result.pages, judged=True, ocr_passes=doc.passes)
    result.warnings.append("ocr")
    return scored


def _extract_and_store(
    path: Path,
    detected: DetectedType,
    base: Path,
    result: FileResult,
    engine: Engine | None,
    ocr_key: str,
) -> None:
    ex = extract(path, detected)
    result.status, result.reason, result.pages = ex.status, ex.reason, ex.pages
    result.signed, result.extractor = ex.signed, ex.extractor
    result.extractor_version = ex.extractor_version
    text = ex.text
    if text is not None:
        text = _score(result, text, ex.pages, judged=detected is DetectedType.PDF)
    used_ocr_key = None
    if result.status == "needs_ocr":
        used_ocr_key = ocr_key
        if engine is not None:
            text = _run_ocr(path, detected, text, result, engine)
        elif ocr_key == "unavailable":
            result.warnings.append("ocr_unavailable")
    if text is not None:
        # Text is kept even for needs_ocr: a broken layer is still useful for debugging.
        _write_atomic(base.with_suffix(".raw.txt"), text)
        _write_atomic(base.with_suffix(".clean.txt"), clean_text(text))
        result.text_ref = f"{result.sha256[:2]}/{result.sha256}.raw.txt"
    if result.status != "error":
        meta = {k: getattr(result, k) for k in _CACHED_FIELDS}
        meta["pipeline_version"] = cache_key()
        meta["ocr_key"] = used_ocr_key
        _write_atomic(base.with_suffix(".meta.json"), json.dumps(meta, ensure_ascii=False))
