"""Load summary of the statute loader (task 11b): load-summary.json + load-summary.md.

Counts only, like the decision report: no article text."""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.loaders.report import BANDS, TOP_REASONS


@dataclass
class PreparedArticle:
    """One article timeline ready to be written as an `extraction`."""

    article_no: str
    fields: dict[str, Any]
    warnings: list[str]
    confidence: dict[str, Any]  # {band, reasons}

    @property
    def band(self) -> str:
        return str(self.confidence["band"])


@dataclass
class PreparedStatute:
    number: str
    parser_version: str
    title: str
    official_ref: str
    snapshots: list[dict[str, Any]]  # path, sha256, date; oldest first
    articles: list[PreparedArticle]

    @property
    def sha256s(self) -> list[str]:
        return sorted(s["sha256"] for s in self.snapshots)


@dataclass
class StatuteCounts:
    """Row counts of one run. A dry run has no database: every article counts as new."""

    new: int = 0
    skipped_existing: int = 0
    sources_new: int = 0
    files_new: int = 0
    files_existing: int = 0
    published: int = 0
    publish_failed: list[tuple[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


def _gap_days(gaps: list[dict[str, Any]]) -> int:
    """Days of the gaps that have a start; a gap from the statute's entry into force is counted
    apart (`open_start`)."""
    return sum(
        (date.fromisoformat(g["to"]) - date.fromisoformat(g["from"])).days
        for g in gaps
        if g["from"]
    )


def build_summary(
    statutes: list[PreparedStatute], counts: StatuteCounts, seconds: float, dry_run: bool
) -> dict[str, Any]:
    bands: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    per_statute = []
    for st in statutes:
        st_bands: Counter[str] = Counter(a.band for a in st.articles)
        gaps = [g for a in st.articles for g in a.fields["gaps"]]
        bands.update(st_bands)
        for a in st.articles:
            reasons.update(a.confidence["reasons"])
        per_statute.append(
            {
                "number": st.number,
                "title": st.title,
                "snapshots": len(st.snapshots),
                "latest_snapshot_date": st.snapshots[-1]["date"],
                "articles": len(st.articles),
                "versions": sum(len(a.fields["versions"]) for a in st.articles),
                "gaps": len(gaps),
                "gap_days": _gap_days(gaps),
                "gaps_open_start": sum(g["from"] is None for g in gaps),
                "bands": {b: st_bands[b] for b in BANDS},
            }
        )
    return {
        "dry_run": dry_run,
        "parser_versions": sorted({st.parser_version for st in statutes}),
        "statutes": per_statute,
        "articles": sum(len(st.articles) for st in statutes),
        "versions": sum(s["versions"] for s in per_statute),
        "gaps": sum(s["gaps"] for s in per_statute),
        "gap_days": sum(s["gap_days"] for s in per_statute),
        "new": counts.new,
        "skipped": counts.skipped_existing,
        "sources_new": counts.sources_new,
        "files_new": counts.files_new,
        "files_existing": counts.files_existing,
        "errors": len(counts.errors),
        "error_refs": counts.errors,
        "published": counts.published,
        "publish_failed": [{"ref": ref, "error": err} for ref, err in counts.publish_failed],
        "seconds": round(seconds, 1),
        "bands": {b: bands[b] for b in BANDS},
        "top_reasons": reasons.most_common(TOP_REASONS),
    }


def render_markdown(s: dict[str, Any]) -> str:
    out = [
        "# Statute load summary",
        "",
        f"Dry run: {'yes' if s['dry_run'] else 'no'}; parser versions: "
        f"{', '.join(s['parser_versions'])}; duration: {s['seconds']} s",
        "",
        f"Articles: {s['articles']}; new: {s['new']}; skipped (already loaded): {s['skipped']}; "
        f"errors: {s['errors']}",
        f"Source rows new: {s['sources_new']}; snapshot files new: {s['files_new']}, "
        f"already known: {s['files_existing']}",
        f"Versions: {s['versions']}; gaps: {s['gaps']} "
        f"({s['gap_days']} article-days, gaps with a start date)",
        f"Published: {s['published']}; publish failures: {len(s['publish_failed'])}",
        "",
        "## Statutes",
        "",
        "| statute | snapshots | latest snapshot | articles | versions | gaps | gap days "
        "| gaps from entry into force | high | medium | low |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    out += [
        f"| {st['number']} | {st['snapshots']} | {st['latest_snapshot_date']} | {st['articles']} "
        f"| {st['versions']} | {st['gaps']} | {st['gap_days']} | {st['gaps_open_start']} "
        f"| {st['bands']['high']} | {st['bands']['medium']} | {st['bands']['low']} |"
        for st in s["statutes"]
    ]
    out += ["", "## Bands", "", "| band | articles |", "|---|---|"]
    out += [f"| {band} | {n} |" for band, n in s["bands"].items()]
    out += ["", f"## Top {TOP_REASONS} reasons", ""]
    out += [f"- {code}: {n}" for code, n in s["top_reasons"]]
    out += ["", f"## Errors ({s['errors']})", ""]
    out += [f"- {e['ref']}: {e['error']}" for e in s["error_refs"]]
    out += ["", f"## Publish failures ({len(s['publish_failed'])})", ""]
    out += [f"- {f['ref']}: {f['error']}" for f in s["publish_failed"]]
    return "\n".join(out) + "\n"


def write_report(summary: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "load-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "load-summary.md").write_text(render_markdown(summary), encoding="utf-8")
