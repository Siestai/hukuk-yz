"""Run summary of the statute pipeline: statutes-report.json (machine) and .md (human)."""

import json
from collections import Counter
from datetime import date
from typing import Any

from hukuk_ingest.statutes.acts import Registry
from hukuk_ingest.statutes.timeline import SnapshotInput

_LEAK_MARKS = ("––", "hüküm altına alınmıştır")
_UNPARSED_LIMIT = 30


def _series(inp: SnapshotInput) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for a in inp.snapshot.articles:
        counts[
            "Ek"
            if a.article_no.startswith("Ek ")
            else "Geçici"
            if a.article_no.startswith("Geçici ")
            else "madde"
        ] += 1
    return dict(counts)


def _gap_days(gaps: list[dict[str, Any]]) -> tuple[int, int]:
    """(days of closed gaps, number of gaps without a start date)."""
    days, open_start = 0, 0
    for g in gaps:
        if g["from"] is None:
            open_start += 1
        else:
            days += (date.fromisoformat(g["to"]) - date.fromisoformat(g["from"])).days
    return days, open_start


def _annotation_stats(inputs: list[SnapshotInput]) -> dict[str, Any]:
    per_snapshot = []
    unparsed: list[dict[str, str]] = []
    for inp in inputs:
        parsed = sum(len(v) for v in inp.notes.values())
        bad = [(no, raw) for no, raws in inp.unparsed.items() for raw in raws]
        per_snapshot.append(
            {
                "path": inp.path,
                "parsed": parsed,
                "unparsed": len(bad),
                "parsed_ratio": round(parsed / (parsed + len(bad)), 4)
                if parsed + len(bad)
                else 1.0,
            }
        )
        unparsed += [{"snapshot": inp.path, "article": no, "raw": raw} for no, raw in bad]
    return {"per_snapshot": per_snapshot, "unparsed": unparsed}


def build_summary(
    records: list[dict[str, Any]],
    groups: dict[str, list[SnapshotInput]],
    registry: Registry,
    stats: dict[str, Any],
    overlaps: dict[str, list[dict[str, Any]]],
    seconds: float,
) -> dict[str, Any]:
    kinds: dict[tuple[date, str], set[str]] = {}
    laws: list[dict[str, Any]] = []
    for rec in records:
        number = rec["number"]
        inputs = groups[number]
        for inp in inputs:
            for ns in inp.notes.values():
                for n in ns:
                    kinds.setdefault((n.date, n.law), set()).add(n.kind)
        arts = rec["articles"]
        gaps = [g for a in arts for g in a["gaps"]]
        days, open_start = _gap_days(gaps)
        leak = [
            f"{inp.path}: {a.article_no}"
            for inp in inputs
            for a in inp.snapshot.articles
            if any(m in a.text for m in _LEAK_MARKS)
        ]
        suspects = sorted(
            {
                f"{a.article_no}"
                for inp in inputs
                for a in inp.snapshot.articles
                if "footnote_leak_suspect" in a.warnings
            }
        )
        warnings = Counter(w.split(":", 1)[0] for a in arts for w in a["warnings"])
        laws.append(
            {
                "number": number,
                "title": rec["title"],
                "latest_snapshot_date": rec["latest_snapshot_date"],
                "articles": len(arts),
                "snapshots": [
                    {
                        **s,
                        "series": _series(inp),
                        "warnings": s["warnings"],
                    }
                    for s, inp in zip(rec["snapshots"], inputs, strict=True)
                ],
                "diffs": stats[number]["diffs"],
                "versions": sum(len(a["versions"]) for a in arts),
                "gaps": len(gaps),
                "gap_days": days,
                "gaps_without_start": open_start,
                "gap_reasons": dict(Counter(g["reason"] for g in gaps)),
                "confidence": dict(Counter(a["confidence"] for a in arts)),
                "warnings": dict(sorted(warnings.items())),
                "overlaps": overlaps[number],
                "footnote_text_in_articles": leak,
                "footnote_leak_suspects": suspects,
                "annotations": _annotation_stats(inputs),
            }
        )
    pairs = set(kinds)
    kabul_only = sorted(p for p, k in kinds.items() if k == {"kabul"})
    missing = sorted((d.isoformat(), law) for d, law in pairs if registry.get(law, d) is None)
    no_yururluk = sorted(
        (d.isoformat(), law)
        for d, law in pairs
        if (a := registry.get(law, d)) and a.yururluk is None
    )
    return {
        "seconds": round(seconds, 2),
        "laws": laws,
        "act_pairs": {
            "distinct": len(pairs),
            "decree_law_or_act": len([p for p in pairs if p[1] != "AYM"]),
            "court_decisions": len([p for p in pairs if p[1] == "AYM"]),
            "confirmation_only": [[d.isoformat(), law] for d, law in kabul_only],
            "missing_in_registry": [list(p) for p in missing],
            "without_yururluk": [list(p) for p in no_yururluk],
            "registry_acts": len(registry.acts),
            "registry_without_yururluk": len(registry.without_yururluk()),
        },
    }


def dump_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def render_markdown(summary: dict[str, Any]) -> str:
    out = ["# Mevzuat sürümleme raporu (görev 11a)", ""]
    ap = summary["act_pairs"]
    out += [
        f"Süre: {summary['seconds']} s. Farklı (kabul tarihi, kanun) çifti: {ap['distinct']} "
        f"(AYM kararı: {ap['court_decisions']}, yalnızca `Aynen kabul` notunda geçen: "
        f"{len(ap['confirmation_only'])}); "
        f"kayıtta ({ap['registry_acts']} satır) olmayan: {len(ap['missing_in_registry'])}; "
        f"kayıtta `yururluk` boş: {ap['registry_without_yururluk']} satır "
        f"({len(ap['without_yururluk'])} çift metinde geçiyor).",
        "",
    ]
    for law in summary["laws"]:
        out += [
            f"## {law['number']} {law['title']}",
            "",
            f"Son snapshot tarihi: **{law['latest_snapshot_date']}** "
            "(sonrasındaki değişiklikler yok sayılır).",
            f"Madde: {law['articles']}, sürüm: {law['versions']}, gap: {law['gaps']} "
            f"({law['gap_days']} gün; başlangıcı bilinmeyen {law['gaps_without_start']}), "
            f"kesişen aralık: {len(law['overlaps'])}.",
            f"Güven bandı: {law['confidence']}.",
            "",
            "| Snapshot | Tarih | Madde | madde/Ek/Geçici | Dipnot | Uyarı |",
            "|---|---|---|---|---|---|",
        ]
        for s in law["snapshots"]:
            date_s = s["date"] + (" (çıkarım)" if s["date_inferred"] else "")
            out.append(
                f"| {s['path'].rsplit('/', 1)[-1]} | {date_s} | {s['articles']} | {s['series']} "
                f"| {s['footnotes']} | {', '.join(s['warnings']) or '-'} |"
            )
        out += [
            "",
            "| Geçiş | değişmeyen | değişen | eklenen | kaldırılan | uncertain_diff |",
            "|---|---|---|---|---|---|",
        ]
        for d in law["diffs"]:
            out.append(
                f"| {d['from']} → {d['to']} | {d['unchanged']} | {d['changed']} | {d['added']} "
                f"| {d['removed']} | {d['uncertain_diff']} |"
            )
        out += [
            "",
            f"Gap nedenleri: {law['gap_reasons']}",
            f"Uyarı dağılımı (madde sayısı): {law['warnings']}",
            "",
        ]
        out += ["| Snapshot | ayrıştırılan not | ayrıştırılamayan | oran |", "|---|---|---|---|"]
        for a in law["annotations"]["per_snapshot"]:
            out.append(
                f"| {a['path'].rsplit('/', 1)[-1]} | {a['parsed']} | {a['unparsed']} "
                f"| {a['parsed_ratio']} |"
            )
        out.append("")
        for u in law["annotations"]["unparsed"][:_UNPARSED_LIMIT]:
            out.append(f"- ayrıştırılamadı: m.{u['article']}: `{u['raw'][:120]}`")
        out += [
            "",
            "Metne karışan dipnot (`––` / `hüküm altına alınmıştır`): "
            f"{len(law['footnote_text_in_articles'])}",
            f"Dipnot sızıntısı şüphesi: {law['footnote_leak_suspects'] or 'yok'}",
            "",
        ]
    if ap["missing_in_registry"]:
        out += ["## Kayıtta olmayan (tarih, kanun) çiftleri", ""]
        out += [f"- {d} {law}" for d, law in ap["missing_in_registry"]]
    return "\n".join(out) + "\n"
