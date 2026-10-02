"""Verification summary (task 06 §9): verify-summary.json + verify-summary.md.

Counts, and decisions named by court / chamber / E-K only: no decision text, party names or
official text ever reach a report."""

import json
from pathlib import Path
from typing import Any

from app.verification.runner import YEAR_BANDS, SourceStats

OUTCOMES = ("verified_official", "verified_uyap", "mismatch", "not_in_source", "error")


def build_summary(stats: list[SourceStats], dry_run: bool) -> dict[str, Any]:
    sources = {}
    for s in stats:
        outcomes = {name: s.outcomes[name] for name in OUTCOMES}
        outcomes["error"] = sum(s.errors.values())
        sources[s.court] = {
            "source": s.source,
            "candidates": s.candidates,
            "unsupported": s.unsupported,
            "outcomes": outcomes,
            "by_year_band": {
                band: {name: s.by_band[band][name] for name in OUTCOMES if s.by_band[band][name]}
                for band in YEAR_BANDS
                if s.by_band[band]
            },
            "fuzzy_fields": dict(s.fuzzy),
            "errors": dict(s.errors),
            "requests": s.requests,
            "rate_limited": s.rate_limited,
            "backoff_seconds": s.backoff_seconds,
            "stopped": s.stopped,
            "skipped_pre_2009": s.skipped_pre_2009,
            "pre_2009_sample": s.sample,
            "downgrades": s.downgrades,
            "mismatches": s.mismatches,
        }
    return {"dry_run": dry_run, "sources": sources}


def render_markdown(summary: dict[str, Any]) -> str:
    out = [
        "# Decision verification summary",
        "",
        f"Dry run: {'yes' if summary['dry_run'] else 'no'}",
    ]
    for court, s in summary["sources"].items():
        out += [
            "",
            f"## {court} ({s['source']})",
            "",
            f"Candidates: {s['candidates']}; not queryable: {s['unsupported']}; "
            f"requests: {s['requests']}; 429: {s['rate_limited']} "
            f"(backed off {s['backoff_seconds']:g} s); stopped: {s['stopped'] or 'no'}",
            "",
            "| outcome | decisions |",
            "|---|---|",
        ]
        out += [f"| {name} | {n} |" for name, n in s["outcomes"].items()]
        if s["by_year_band"]:
            out += ["", "| year band | " + " | ".join(OUTCOMES) + " |", "|---|" + "---|" * 5]
            out += [
                f"| {band} | " + " | ".join(str(counts.get(name, 0)) for name in OUTCOMES) + " |"
                for band, counts in s["by_year_band"].items()
            ]
        out += ["", "Fuzzy fields: " + (_pairs(s["fuzzy_fields"]) or "none")]
        out += ["Errors: " + (_pairs(s["errors"]) or "none")]
        sample = s["pre_2009_sample"]
        out += [
            f"Skipped as pre-2009: {s['skipped_pre_2009']}; coverage sample: "
            + (
                f"{sample['checked']} queried, {sample['found']} found"
                + (", heuristic switched off" if sample["heuristic_disabled"] else "")
                if sample
                else "none due"
            )
        ]
        out += ["", f"Downgrades ({len(s['downgrades'])}):"] + [f"- {d}" for d in s["downgrades"]]
        out += ["", f"Mismatches ({len(s['mismatches'])}):"] + [f"- {m}" for m in s["mismatches"]]
    return "\n".join(out) + "\n"


def _pairs(counts: dict[str, int]) -> str:
    return ", ".join(f"{k}: {n}" for k, n in sorted(counts.items()))


def write_report(summary: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verify-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "verify-summary.md").write_text(render_markdown(summary), encoding="utf-8")
