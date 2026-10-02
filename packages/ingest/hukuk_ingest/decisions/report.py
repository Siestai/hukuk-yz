"""Run summary of the decision parser: summary.json (machine) and summary.md (human).

Lists identify decisions as `<issue>. sayı · <sha256 prefix>` instead of file names: the file
name is the journal's decision title, which must not travel into PR descriptions."""

import json
from collections import Counter, defaultdict
from typing import Any

from hukuk_ingest.decisions import qa
from hukuk_ingest.decisions.parse import DecisionRecord

_BUCKET = 15  # issues per row of the layout table
# Court distribution recorded in AGENTS.md (task 03 exploration), for the side-by-side table.
AGENTS_COURTS = {
    "Yargıtay daire": 5649,
    "BAM": 297,
    "HGK": 154,
    "Yabancı (ABAD, Alman Federal)": 64,
    "AYM": 51,
    "AİHM": 12,
    "İBK": 5,
    "Danıştay": 4,
}
_TOP_WARNINGS = 20
_SHINGLE = 5  # words per shingle when comparing the texts of a duplicate group
_SAME_CONTAINMENT = 0.95  # share of the shorter text found in the longer one
_SAME_LENGTH = 0.9  # shorter / longer text length
_EXCERPT_CONTAINMENT = 0.5  # "one text contains most of the other"


def court_group(r: DecisionRecord) -> str:
    if r.court == "yargitay":
        return {"daire": "Yargıtay daire", "hgk_iddk": "HGK", "ibk": "İBK"}.get(
            r.court_level, "Diğer"
        )
    return {
        "bam": "BAM",
        "aym": "AYM",
        "aihm": "AİHM",
        "danistay": "Danıştay",
        "abad": "Yabancı (ABAD, Alman Federal)",
        "foreign": "Yabancı (ABAD, Alman Federal)",
    }.get(r.court, "Diğer" if r.court else "Belirsiz")


def flag_date_outliers(records: list[DecisionRecord]) -> None:
    """Adds `date_outside_issue_year`: against the journal year when the pages print it, else
    against the median decision year of the issue."""
    medians = qa.issue_years(
        [(r.journal_issue, r.decision_date) for r in records if r.journal_issue is not None]
    )
    for r in records:
        reference = r.journal_year or medians.get(r.journal_issue or -1)
        if qa.date_outside_issue_year(r.decision_date, reference):
            r.warnings.append("date_outside_issue_year")


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = text.split()
    return {tuple(words[i : i + _SHINGLE]) for i in range(max(len(words) - _SHINGLE + 1, 1))}


def dup_kind(group: list[DecisionRecord]) -> str:
    """Why a same-key group is not a parser collapse: `date_mismatch` (same court, chamber, E/K,
    different decision_date), else `same_text` (near-identical full_text), `excerpt` (one text
    contains most of the other, or the lengths differ), `different_text` (texts barely overlap:
    two decisions printed under one header key, or no body found; beyond the three asked for)."""
    if len({r.decision_date for r in group}) > 1:
        return "date_mismatch"
    longest = max(group, key=lambda r: len(r.full_text))
    reference = _shingles(longest.full_text)
    kinds = set()
    for r in group:
        if r is longest:
            continue
        shared = len(_shingles(r.full_text) & reference) / len(_shingles(r.full_text))
        length = len(r.full_text) / max(len(longest.full_text), 1)
        if shared >= _SAME_CONTAINMENT and length >= _SAME_LENGTH:
            kinds.add("same_text")
        elif shared >= _EXCERPT_CONTAINMENT:
            kinds.add("excerpt")
        else:
            kinds.add("different_text")
    for kind in ("different_text", "excerpt", "same_text"):  # the weakest match describes the group
        if kind in kinds:
            return kind
    return "same_text"


def _ref(r: DecisionRecord) -> str:
    return f"{r.journal_issue}. sayı · {r.sha256[:12]}"


def build_summary(records: list[DecisionRecord], total_seconds: float) -> dict[str, Any]:
    ok = [r for r in records if r.status == "ok"]
    dicts = [r.to_dict() for r in ok]
    layouts: dict[str, Counter[int]] = defaultdict(Counter)
    for r in ok:
        layouts[r.layout][((r.journal_issue or 0) - 1) // _BUCKET] += 1
    fill_all = qa.fill_counts(dicts)
    fill_by_layout = {
        layout: qa.fill_counts([d for d in dicts if d["layout"] == layout])
        for layout in sorted({r.layout for r in ok})
    }
    courts = Counter(court_group(r) for r in ok)
    warnings = Counter(qa.warning_code(w) for r in ok for w in r.warnings)
    keys: dict[tuple[str, str, str, str], list[DecisionRecord]] = defaultdict(list)
    for r in ok:
        if r.esas_no and r.karar_no:
            keys[(r.court, r.chamber, r.esas_no, r.karar_no)].append(r)
    return {
        "decisions": len(records),
        "errors": [{"ref": _ref(r), "error": r.error} for r in records if r.status == "error"],
        "total_seconds": round(total_seconds, 1),
        "layout_by_issue_range": {
            layout: {f"{b * _BUCKET + 1}-{(b + 1) * _BUCKET}": n for b, n in sorted(c.items())}
            for layout, c in sorted(layouts.items())
        },
        "fill": {"overall": fill_all, "by_layout": fill_by_layout},
        "courts": dict(courts.most_common()),
        "agents_courts": AGENTS_COURTS,
        "completeness": dict(Counter(r.text_completeness for r in ok)),
        "top_warnings": warnings.most_common(_TOP_WARNINGS),
        "layout_unknown": [_ref(r) for r in ok if r.layout == "unknown"],
        "critical_missing": [
            {"ref": _ref(r), "missing": [m for m in r.missing if m in qa.CRITICAL_FIELDS]}
            for r in ok
            if any(m in qa.CRITICAL_FIELDS for m in r.missing)
        ],
        "duplicate_candidates": [
            {"key": list(k), "dup_kind": dup_kind(group), "refs": [_ref(r) for r in group]}
            for k, group in sorted(keys.items())
            if len(group) > 1
        ],
    }


def _pct(counts: dict[str, int]) -> str:
    if not counts["applicable"]:
        return "-"
    filled, applicable = counts["filled"], counts["applicable"]
    return f"{100 * filled / applicable:.1f}% ({filled}/{applicable})"


def render_markdown(s: dict[str, Any]) -> str:
    out = [
        "# Decision parser summary",
        "",
        f"Decisions: {s['decisions']}; errors: {len(s['errors'])}; "
        f"duration: {s['total_seconds']} s",
        f"Text completeness: {s['completeness']}",
        "",
        "## Layout x issue range",
        "",
    ]
    ranges = sorted(
        {r for v in s["layout_by_issue_range"].values() for r in v},
        key=lambda x: int(x.split("-")[0]),
    )
    out += ["| layout | " + " | ".join(ranges) + " |", "|---|" + "---|" * len(ranges)]
    for layout, row in s["layout_by_issue_range"].items():
        out.append(f"| {layout} | " + " | ".join(str(row.get(r, 0)) for r in ranges) + " |")
    out += ["", "## Field fill (of applicable decisions)", ""]
    layouts = list(s["fill"]["by_layout"])
    out += [
        "| field | overall | " + " | ".join(layouts) + " |",
        "|---|---|" + "---|" * len(layouts),
    ]
    for name in s["fill"]["overall"]:
        cells = [_pct(s["fill"]["by_layout"][layout][name]) for layout in layouts]
        out.append(f"| {name} | {_pct(s['fill']['overall'][name])} | " + " | ".join(cells) + " |")
    out += ["", "## Courts vs AGENTS.md", "", "| court | parsed | AGENTS.md |", "|---|---|---|"]
    for name in sorted(set(s["courts"]) | set(s["agents_courts"])):
        out.append(f"| {name} | {s['courts'].get(name, 0)} | {s['agents_courts'].get(name, '-')} |")
    out += ["", f"## Top {_TOP_WARNINGS} warnings", ""]
    out += [f"- {code}: {n}" for code, n in s["top_warnings"]]
    out += ["", f"## layout=unknown ({len(s['layout_unknown'])})", ""]
    out += [f"- {ref}" for ref in s["layout_unknown"]]
    out += ["", f"## Critical field missing ({len(s['critical_missing'])})", ""]
    out += [f"- {m['ref']}: {', '.join(m['missing'])}" for m in s["critical_missing"]]
    kinds = Counter(d["dup_kind"] for d in s["duplicate_candidates"])
    out += [
        "",
        f"## Duplicate candidates across issues ({len(s['duplicate_candidates'])})",
        "",
        "The same court, chamber, esas and karar number in more than one file. These are "
        "cross-issue repeats of the journal (the same decision printed again, in full or as an "
        "excerpt), not parser collapses of different decisions.",
        "",
        "Kinds: " + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())),
        "",
        "| dup_kind | key | files |",
        "|---|---|---|",
    ]
    out += [
        f"| {d['dup_kind']} | {' / '.join(d['key'])} | {', '.join(d['refs'])} |"
        for d in s["duplicate_candidates"]
    ]
    out += ["", f"## Errors ({len(s['errors'])})", ""]
    out += [f"- {e['ref']}: {e['error']}" for e in s["errors"]]
    return "\n".join(out) + "\n"


def dump_json(s: dict[str, Any]) -> str:
    return json.dumps(s, ensure_ascii=False, indent=2)
