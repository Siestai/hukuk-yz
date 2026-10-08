"""`hukuk-ingest statutes`: snapshots of 4857 and 5510 -> statutes.jsonl + report (task 11a)."""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from hukuk_ingest.legacy_doc import read_doc
from hukuk_ingest.statutes import confidence, report
from hukuk_ingest.statutes.acts import Registry
from hukuk_ingest.statutes.annotations import Annotation, parse_annotations
from hukuk_ingest.statutes.diff import diff_snapshots
from hukuk_ingest.statutes.split import split_statute
from hukuk_ingest.statutes.timeline import SnapshotInput, build_article, find_overlaps

STATUTE_DIR = "Mevzuat/Kanunlar/"
_NUMBER_RE = re.compile(r"(?<!\d)(4857|5510)(?!\d)")
_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.((?:19|20)\d{2})(?!\d)")


@dataclass
class SnapshotFile:
    path: str
    sha256: str
    date: date | None
    text: str
    duplicates: list[str] = field(default_factory=list)


def _file_date(path: str) -> date | None:
    matches = _DATE_RE.findall(Path(path).name)
    if not matches:
        return None
    m = matches[-1]
    try:
        return date(int(m[2]), int(m[1]), int(m[0]))
    except ValueError:
        return None


def discover(scan_report: Path, text_cache: Path, raw_dir: Path) -> list[SnapshotFile]:
    """The statute snapshot files of the scan report (task 03), duplicates (same sha256) merged."""
    by_sha: dict[str, SnapshotFile] = {}
    rows = [json.loads(line) for line in scan_report.read_text(encoding="utf-8").splitlines()]
    for row in sorted(rows, key=lambda r: ("Eskiler" in r["path"], r["path"])):
        path = row["path"]
        if not path.startswith(STATUTE_DIR) or not _NUMBER_RE.search(Path(path).name):
            continue
        if row["status"] == "ok" and row.get("text_ref"):
            text = (text_cache / row["text_ref"]).read_text(encoding="utf-8")
        elif row["status"] == "unsupported" and row["reason"] == "legacy_doc":
            text = read_doc(raw_dir / path)
        else:
            continue
        if row["sha256"] in by_sha:
            by_sha[row["sha256"]].duplicates.append(path)
            continue
        by_sha[row["sha256"]] = SnapshotFile(path, row["sha256"], _file_date(path), text)
    return sorted(by_sha.values(), key=lambda s: s.path)


def _inputs_for(files: list[SnapshotFile]) -> dict[str, list[SnapshotInput]]:
    """Split and annotate every snapshot; grouped by the statute number of its header."""
    groups: dict[str, list[SnapshotInput]] = {}
    for f in files:
        snap = split_statute(f.text)
        notes: dict[str, list[Annotation]] = {}
        unparsed: dict[str, list[str]] = {}
        for art in snap.articles:
            notes[art.article_no], unparsed[art.article_no] = parse_annotations(art.text)
        when, inferred = f.date, False
        if when is None:
            all_dates = [n.date for ns in notes.values() for n in ns]
            if not all_dates:
                continue
            when, inferred = max(all_dates), True
            snap.warnings.append("snapshot_date_inferred")
        if snap.number is None:
            snap.warnings.append("statute_number_missing")
            continue
        groups.setdefault(snap.number, []).append(
            SnapshotInput(f.path, f.sha256, when, inferred, snap, notes, unparsed)
        )
    for inputs in groups.values():
        inputs.sort(key=lambda i: i.date)
    return groups


def _article_order(inputs: list[SnapshotInput]) -> list[str]:
    order: list[str] = []
    for inp in reversed(inputs):
        for art in inp.snapshot.articles:
            if art.article_no not in order:
                order.append(art.article_no)
    return order


def _statute_record(
    number: str, inputs: list[SnapshotInput], registry: Registry, duplicates: dict[str, list[str]]
) -> dict[str, Any]:
    latest = inputs[-1].snapshot
    original = (number, inputs[0].snapshot.kabul_tarihi)
    articles = []
    for no in _article_order(inputs):
        rec = build_article(no, inputs, number, original, registry)
        for inp in inputs:
            art = next((a for a in inp.snapshot.articles if a.article_no == no), None)
            if art:
                rec["warnings"] = sorted(
                    {*rec["warnings"], *art.warnings} - {"footnote_marker_not_found"}
                )
        articles.append(rec)
    for rec in articles:
        rec["confidence"] = confidence.band(rec["warnings"])
    return {
        "number": number,
        "title": latest.title,
        "header": latest.header(),
        "latest_snapshot_date": inputs[-1].date.isoformat(),
        "snapshots": [
            {
                "path": i.path,
                "sha256": i.sha256,
                "date": i.date.isoformat(),
                "date_inferred": i.date_inferred,
                "articles": len(i.snapshot.articles),
                "footnotes": i.snapshot.footnote_count,
                "warnings": i.snapshot.warnings,
                "duplicates": duplicates.get(i.path, []),
            }
            for i in inputs
        ],
        "articles": articles,
    }


def build_records(
    files: list[SnapshotFile], registry: Registry
) -> tuple[list[dict[str, Any]], dict[str, list[SnapshotInput]]]:
    """One statute record (header, snapshots, article timelines) per statute number."""
    duplicates = {f.path: f.duplicates for f in files if f.duplicates}
    groups = _inputs_for(files)
    records = [
        _statute_record(number, inputs, registry, duplicates)
        for number, inputs in sorted(groups.items())
    ]
    return records, groups


def run(
    scan_report: Path, text_cache: Path, raw_dir: Path, registry: Registry, out: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = time.perf_counter()
    records, groups = build_records(discover(scan_report, text_cache, raw_dir), registry)
    stats = {
        number: {"diffs": [_diff_counts(a, b) for a, b in zip(inputs, inputs[1:], strict=False)]}
        for number, inputs in groups.items()
    }
    overlaps = {
        r["number"]: [
            {"article": a["article_no"], "overlap": o}
            for a in r["articles"]
            for o in find_overlaps(a)
        ]
        for r in records
    }
    summary = report.build_summary(
        records, groups, registry, stats, overlaps, time.perf_counter() - start
    )
    out.mkdir(parents=True, exist_ok=True)
    with (out / "statutes.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "statutes-report.json").write_text(report.dump_json(summary), encoding="utf-8")
    (out / "statutes-report.md").write_text(report.render_markdown(summary), encoding="utf-8")
    return records, summary


def _diff_counts(a: SnapshotInput, b: SnapshotInput) -> dict[str, Any]:
    diffs = diff_snapshots(a.snapshot, b.snapshot)
    counts: dict[str, int] = {}
    for d in diffs:
        counts[d.kind] = counts.get(d.kind, 0) + 1
    return {
        "from": a.date.isoformat(),
        "to": b.date.isoformat(),
        **{k: counts.get(k, 0) for k in ("unchanged", "changed", "added", "removed")},
        "uncertain_diff": sum("uncertain_diff" in d.warnings for d in diffs),
    }
