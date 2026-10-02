"""Run summary: summary.json (machine) and summary.md (human)."""

import json
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any

from hukuk_ingest.pipeline import FileResult


def _folder(rel: str) -> str:
    parent = PurePosixPath(rel).parent.parts[:2]
    return "/".join(parent) or "."


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
    out += [f"## Borderline quality ({len(s['borderline_quality'])})", ""]
    out += [f"- `{p}`" for p in s["borderline_quality"]]
    out += ["", "## Slowest 10", ""]
    out += [f"- {x['duration_ms']} ms `{x['path']}`" for x in s["slowest"]]
    out += ["", f"## Errors ({len(s['errors'])})", ""]
    out += [f"- `{e['path']}`: {e['error']}" for e in s["errors"]]
    return "\n".join(out) + "\n"


def dump_json(s: dict[str, Any]) -> str:
    return json.dumps(s, ensure_ascii=False, indent=2)
