"""Run summary: summary.json (machine) and summary.md (human)."""

import json
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any

from hukuk_ingest.pipeline import FileResult


def _folder(rel: str) -> str:
    parent = PurePosixPath(rel).parent.parts[:2]
    return "/".join(parent) or "."


def _ocr_section(results: list[FileResult]) -> dict[str, Any]:
    ocred = [r for r in results if r.quality and "ocr_pass" in r.quality]
    passes = Counter(p for r in ocred for p in (r.quality or {})["ocr_pass"] if p is not None)
    return {
        "files": len(ocred),
        "pages": sum(passes.values()),
        "passes": {str(n): passes[n] for n in (1, 2, 3)},
        "seconds": round(sum(r.duration_ms for r in ocred) / 1000, 1),
        "low_quality": [r.path for r in ocred if r.reason == "ocr_low_quality"],
        "unavailable": [r.path for r in results if "ocr_unavailable" in r.warnings],
    }


def _doc_section(results: list[FileResult]) -> dict[str, Any]:
    docs = [r for r in results if r.detected_type == "doc"]
    return {
        "read": [r.path for r in docs if r.status == "ok"],
        "unreadable": [
            {"path": r.path, "status": r.status, "reason": r.reason}
            for r in docs
            if r.status != "ok"
        ],
    }


def build_summary(results: list[FileResult], total_seconds: float) -> dict[str, Any]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for r in results:
        matrix[r.detected_type][r.status] += 1
    needs_ocr: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r.status == "needs_ocr":
            needs_ocr[_folder(r.path)][r.reason or "?"].append(r.path)
    slowest = sorted(results, key=lambda r: r.duration_ms, reverse=True)[:10]
    return {
        "files": len(results),
        "total_seconds": round(total_seconds, 1),
        "cache_hits": sum(r.cached for r in results),
        "type_status": {t: dict(c) for t, c in sorted(matrix.items())},
        "extension_mismatches": [
            {"path": r.path, "ext": r.ext, "detected_type": r.detected_type, "status": r.status}
            for r in results
            if r.extension_mismatch
        ],
        "needs_ocr": {f: dict(v) for f, v in sorted(needs_ocr.items())},
        "ocr": _ocr_section(results),
        "legacy_doc": _doc_section(results),
        "borderline_quality": [r.path for r in results if "borderline_quality" in r.warnings],
        "slowest": [{"path": r.path, "duration_ms": r.duration_ms} for r in slowest],
        "errors": [{"path": r.path, "error": r.error} for r in results if r.status == "error"],
    }


def render_markdown(s: dict[str, Any]) -> str:
    statuses = sorted({st for row in s["type_status"].values() for st in row})
    out = [
        "# Ingest summary",
        "",
        f"Files: {s['files']}; duration: {s['total_seconds']} s; cache hits: {s['cache_hits']}",
        "",
        "## Type x status",
        "",
        "| type | " + " | ".join(statuses) + " |",
        "|---|" + "---|" * len(statuses),
    ]
    for t, row in s["type_status"].items():
        out.append(f"| {t} | " + " | ".join(str(row.get(st, 0)) for st in statuses) + " |")
    out += ["", f"## Extension mismatches ({len(s['extension_mismatches'])})", ""]
    out += [
        f"- `{m['path']}`: {m['ext']} is {m['detected_type']} ({m['status']})"
        for m in s["extension_mismatches"]
    ]
    out += ["", "## needs_ocr by folder", ""]
    for folder, reasons in s["needs_ocr"].items():
        total = sum(len(v) for v in reasons.values())
        out.append(f"### {folder} ({total})")
        for reason, paths in sorted(reasons.items()):
            out += ["", f"{reason} ({len(paths)}):", ""] + [f"- `{p}`" for p in paths]
        out.append("")
    ocr = s["ocr"]
    out += [
        "## OCR",
        "",
        f"Files: {ocr['files']}; pages: {ocr['pages']}; duration: {ocr['seconds']} s",
        "",
        "Pass distribution (1 default, 2 Sauvola, 3 rotated): "
        + ", ".join(f"{n}: {c}" for n, c in ocr["passes"].items()),
        "",
        f"### ocr_low_quality ({len(ocr['low_quality'])}): ask the partners for a clean copy",
        "",
    ]
    out += [f"- `{p}`" for p in ocr["low_quality"]]
    out += ["", f"### OCR unavailable ({len(ocr['unavailable'])})", ""]
    out += [f"- `{p}`" for p in ocr["unavailable"]]
    doc = s["legacy_doc"]
    out += ["", f"## Legacy .doc read ({len(doc['read'])})", ""]
    out += [f"- `{p}`" for p in doc["read"]]
    out += ["", f"## Legacy .doc unreadable ({len(doc['unreadable'])})", ""]
    out += [f"- `{d['path']}`: {d['status']}/{d['reason']}" for d in doc["unreadable"]]
    out += ["", "Decision-archive `.doc` files are only read here; parsing/loading is a later run."]
    out += ["", f"## Borderline quality ({len(s['borderline_quality'])})", ""]
    out += [f"- `{p}`" for p in s["borderline_quality"]]
    out += ["", "## Slowest 10", ""]
    out += [f"- {x['duration_ms']} ms `{x['path']}`" for x in s["slowest"]]
    out += ["", f"## Errors ({len(s['errors'])})", ""]
    out += [f"- `{e['path']}`: {e['error']}" for e in s["errors"]]
    return "\n".join(out) + "\n"


def dump_json(s: dict[str, Any]) -> str:
    return json.dumps(s, ensure_ascii=False, indent=2)
