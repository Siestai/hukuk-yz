"""Load summary (task 05 §8): load-summary.json + load-summary.md.

Counts only: no decision text, party names or file titles. Records are referred to by journal
issue and sha256 prefix, as in the task 04 report."""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TOP_REASONS = 15
BANDS = ("high", "medium", "low")
# Warnings the loader adds on top of the parser's (normalize.py and the duplicate rules).
LOADER_WARNINGS = (
    "outcome_unmapped",
    "court_missing",
    "court_unmapped",
    "court_level_unmapped",
    "duplicate_of",
)


@dataclass
class PreparedRecord:
    """One decision file ready to be written: the rows of §2 minus their ids."""

    sha256: str
    source_path: str
    title: str
    official_ref: str | None
    size: int
    detected_type: str | None
    parser_version: str
    fields: dict[str, Any]
    warnings: list[str]
    confidence: dict[str, Any]
    raw_text_ref: str

    @property
    def ref(self) -> str:
        return f"{self.fields['journal_issue']}. sayı · {self.sha256[:12]}"


@dataclass
class LoadCounts:
    """Row counts of one run; `new` and `skipped_existing` come from the database (a dry run
    has neither a database nor already-loaded rows: every prepared record counts as new)."""

    total: int = 0
    new: int = 0
    skipped_duplicate_sha256: int = 0
    skipped_existing: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


def build_summary(
    prepared: list[PreparedRecord], counts: LoadCounts, seconds: float, dry_run: bool
) -> dict[str, Any]:
    by_court: dict[str, Counter[str]] = defaultdict(Counter)
    by_layout: dict[str, Counter[str]] = defaultdict(Counter)
    bands: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    normalization: Counter[str] = Counter()
    for p in prepared:
        band = p.confidence["band"]
        bands[band] += 1
        by_court[p.fields["court"] or "(boş)"][band] += 1
        by_layout[p.fields["layout"]][band] += 1
        reasons.update(p.confidence["reasons"])
        normalization.update(w for w in p.warnings if w in LOADER_WARNINGS)
    groups = {
        (g["dup_kind"], tuple(g["key"])) for p in prepared if (g := p.fields.get("duplicate_group"))
    }
    group_kinds = Counter(kind for kind, _ in groups)
    return {
        "dry_run": dry_run,
        "parser_versions": sorted({p.parser_version for p in prepared}),
        "total": counts.total,
        "new": counts.new,
        "skipped": counts.skipped_duplicate_sha256 + counts.skipped_existing,
        "skipped_duplicate_sha256": counts.skipped_duplicate_sha256,
        "skipped_existing": counts.skipped_existing,
        "errors": len(counts.errors),
        "error_refs": counts.errors,
        "seconds": round(seconds, 1),
        "bands": {band: bands[band] for band in BANDS},
        "bands_by_court": {k: _bands(c) for k, c in sorted(by_court.items())},
        "bands_by_layout": {k: _bands(c) for k, c in sorted(by_layout.items())},
        "top_reasons": reasons.most_common(TOP_REASONS),
        "duplicate_groups": {"total": len(groups), "by_dup_kind": dict(group_kinds)},
        "normalization_warnings": {w: normalization[w] for w in LOADER_WARNINGS},
    }


def _bands(counter: Counter[str]) -> dict[str, int]:
    return {band: counter[band] for band in BANDS}


def render_markdown(s: dict[str, Any]) -> str:
    out = [
        "# Decision load summary",
        "",
        f"Dry run: {'yes' if s['dry_run'] else 'no'}; parser versions: "
        f"{', '.join(s['parser_versions'])}; duration: {s['seconds']} s",
        "",
        f"Total: {s['total']}; new: {s['new']}; skipped: {s['skipped']} "
        f"(same sha256 in the input: {s['skipped_duplicate_sha256']}, already loaded: "
        f"{s['skipped_existing']}); errors: {s['errors']}",
        "",
        "## Bands",
        "",
        "| band | records |",
        "|---|---|",
    ]
    out += [f"| {band} | {n} |" for band, n in s["bands"].items()]
    for title, key in (("court", "bands_by_court"), ("layout", "bands_by_layout")):
        out += [
            "",
            f"## Bands by {title}",
            "",
            f"| {title} | high | medium | low |",
            "|---|---|---|---|",
        ]
        out += [f"| {k} | {b['high']} | {b['medium']} | {b['low']} |" for k, b in s[key].items()]
    out += ["", f"## Top {TOP_REASONS} reasons", ""]
    out += [f"- {code}: {n}" for code, n in s["top_reasons"]]
    dup = s["duplicate_groups"]
    out += ["", f"## Duplicate groups ({dup['total']})", ""]
    out += [f"- {kind}: {n}" for kind, n in sorted(dup["by_dup_kind"].items())]
    out += ["", "## Normalization warnings", ""]
    out += [f"- {code}: {n}" for code, n in s["normalization_warnings"].items()]
    out += ["", f"## Errors ({s['errors']})", ""]
    out += [f"- {e['ref']}: {e['error']}" for e in s["error_refs"]]
    return "\n".join(out) + "\n"


def write_report(summary: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "load-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "load-summary.md").write_text(render_markdown(summary), encoding="utf-8")
