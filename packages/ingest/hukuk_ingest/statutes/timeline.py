"""Version timeline of every article from consecutive snapshots (task 11a).

Between two snapshots S1 (date d1) and S2 (date d2) an article that changed is explained by the
amendment notes in the S2 text whose kabul date lies in (d1, d2]; the in-force date of the
amending act (registry) is the boundary of the old and new version. What cannot be explained
stays an explicit gap: no text is invented for it.

Half-open intervals `[valid_from, valid_to)` throughout; ISO strings in the records."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from hukuk_ingest.statutes import confidence
from hukuk_ingest.statutes.acts import BASIS_ACT, BASIS_PARTIAL, Registry
from hukuk_ingest.statutes.annotations import Annotation, footnote_laws
from hukuk_ingest.statutes.diff import UNCHANGED, compare, marker_numbers, same_wording
from hukuk_ingest.statutes.split import Article, Snapshot

DAY = timedelta(days=1)
FOUND, GAP, NOT_IN_FORCE, UNKNOWN_ARTICLE = "found", "gap", "not_in_force", "unknown_article"
_ADDED_KINDS = ("Ek ", "Geçici ")


@dataclass
class SnapshotInput:
    path: str
    sha256: str
    date: date
    date_inferred: bool
    snapshot: Snapshot
    notes: dict[str, list[Annotation]]
    unparsed: dict[str, list[str]]


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _d(value: str | date | None) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) else value


def _known(notes: list[Annotation]) -> list[dict[str, str]]:
    seen: dict[tuple[date, str, str, str], Annotation] = {}
    for n in notes:
        seen.setdefault((n.date, n.law, n.kind, n.scope), n)
    return [
        {"law": n.law, "date": n.date.isoformat(), "kind": n.kind, "scope": n.scope}
        for _, n in sorted(seen.items(), key=lambda kv: kv[0][:2])
    ]


@dataclass
class _Trans:
    old_to: date
    new_from: date
    gap: dict[str, Any] | None
    warnings: list[str]
    basis: str  # act | exception | fallback
    acts: list[dict[str, str]]


def _gap(start: date | None, end: date, reason: str, notes: list[Annotation]) -> dict[str, Any]:
    return {
        "from": _iso(start),
        "to": end.isoformat(),
        "reason": reason,
        "known_amendments": _known(notes),
    }


def _fallback(d_old: date, d_new: date, reason: str, notes: list[Annotation]) -> _Trans:
    """Boundary unknown: the old text is known at d_old, the new one at d_new."""
    old_to = d_old + DAY
    gap = _gap(old_to, d_new, reason, notes) if old_to < d_new else None
    return _Trans(old_to, d_new, gap, [reason], "fallback", _known(notes))


def _explain(
    art: Article,
    notes: list[Annotation],
    d_old: date,
    d_new: date,
    d_new_inferred: bool,
    number: str,
    registry: Registry,
) -> _Trans:
    """Boundary between the old text (seen at d_old) and the new one (seen at d_new)."""
    window = [n for n in notes if n.kind != "kabul" and d_old < n.date <= d_new]
    pairs = sorted({(n.date, n.law) for n in window})
    if not pairs:
        return _fallback(d_old, d_new, "unexplained_change", [])
    # Footnotes only make the window more cautious: they never date a version.
    foot_only = sorted(
        {
            (when, law)
            for f in art.footnotes
            for when, law in footnote_laws(f.text)
            if d_old < when <= d_new
        }
        - set(pairs)
    )
    dates: set[date] = set()
    bases: set[str] = set()
    for when, law in pairs:
        found = registry.effective_dates(law, when, number, art.article_no)
        if found is None:
            return _fallback(d_old, d_new, "yururluk_unknown", window)
        dates |= found[0]
        bases.add(found[1])
    widened = False
    for when, law in foot_only:
        found = registry.effective_dates(law, when, number, art.article_no)
        if found is None:
            return _fallback(d_old, d_new, "multi_amendment_in_window", window)
        # In force before the old snapshot (a confirmation law): the old text already has it.
        later = {y for y in found[0] if y > d_old}
        dates |= later
        widened = widened or bool(later)
    if any(y <= d_old or (y > d_new and not d_new_inferred) for y in dates):
        return _fallback(d_old, d_new, "yururluk_outside_window", window)
    start, end = min(dates), max(dates)
    own = bases != {BASIS_ACT}  # an exception or a partial date, not the act's plain date
    warnings = ["exception_effective"] if own else []
    gap = None
    if start < end:
        multi = len(pairs) > 1 or widened
        if multi:
            reason = "multi_amendment_in_window"
        elif BASIS_PARTIAL in bases:
            reason = "partial_entry_into_force"
        else:
            reason = "split_effective_dates"
        warnings.append(reason)
        gap = _gap(start, end, reason, window)
    return _Trans(start, end, gap, warnings, "exception" if own else "act", _known(window))


def _is_added_kind(article_no: str) -> bool:
    return article_no.startswith(_ADDED_KINDS)


def _version(
    art: Article,
    snap: SnapshotInput,
    valid_from: date | None,
    change_kind: str,
    ref: list[dict[str, str]],
    basis: str,
) -> dict[str, Any]:
    return {
        "text": art.text,
        "heading": art.heading,
        "valid_from": _iso(valid_from),
        "valid_to": None,
        "change_kind": change_kind,
        "amending_ref": ref,
        "evidence": {
            "basis": basis,
            "snapshots": [snap.path],
            "snapshot_dates": [snap.date.isoformat()],
        },
        "footnotes": [f.to_dict() for f in art.footnotes],
        "warnings": [],
        "confidence": confidence.HIGH,
    }


def _add_dates(
    art: Article, real: list[Annotation], number: str, registry: Registry
) -> set[date] | None:
    """In-force dates of the act that added the article, when a note says so.

    Ek and Geçici articles: the earliest whole-article `Ek` note (a later `Ek` without a scope can
    be a paragraph). Other articles: only a lone `Ek` heading note, since any further note means
    the article may have existed long before. None when no note adds it or its date is unknown."""
    if _is_added_kind(art.article_no):
        adds = [n for n in real if n.kind == "ek" and not n.scope]
        add = min(adds, key=lambda n: n.date) if adds else None
    else:
        heads = [n for n in real if n.kind == "ek" and not n.scope and n.offset == 0]
        add = heads[0] if heads and len({(n.date, n.law) for n in real}) == 1 else None
    if add is None:
        return None
    found = registry.effective_dates(add.law, add.date, number, art.article_no)
    return found[0] if found else None


def _first_snapshot(
    art: Article,
    notes: list[Annotation],
    snap: SnapshotInput,
    number: str,
    original: tuple[str, date | None],
    registry: Registry,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    """Version in force at the earliest snapshot and the gap before it."""
    real = [n for n in notes if n.kind != "kabul"]
    law_from: date | None = None
    law_dates: set[date] = set()
    if original[1] is not None:
        found = registry.effective_dates(original[0], original[1], number, art.article_no)
        if found:
            law_dates = found[0]
    if law_dates:
        law_from = min(law_dates)
    warnings: list[str] = []
    kind = "repealed" if art.status == "repealed" else "amended"
    if real:
        dates: set[date] = set()
        basis = "act"
        for n in real:
            found = registry.effective_dates(n.law, n.date, number, art.article_no)
            if found is None:
                dates = set()
                break
            dates |= found[0]
            if found[1] != BASIS_ACT:
                basis = "exception"
        if not dates:
            valid_from, basis = snap.date, "fallback"
            warnings.append("yururluk_unknown")
        else:
            valid_from = max(dates)
            if valid_from > snap.date:
                valid_from, basis = snap.date, "fallback"
                warnings.append("yururluk_outside_window")
            elif basis == "exception":
                warnings.append("exception_effective")
        # The note that brought the article in dates its start; nothing is known before it.
        add = _add_dates(art, real, number, registry)
        gap_from = min(add) if add else law_from
        reason = "before_earliest_snapshot"
        if add and valid_from == max(add) and min(add) < valid_from:
            reason = "partial_entry_into_force"
        gap = None
        if gap_from is None or gap_from < valid_from:
            warnings.append(reason)
            gap = _gap(gap_from, valid_from, reason, real)
            if gap_from is None:
                warnings.append("yururluk_unknown")
        elif add and art.status != "repealed":
            kind = "added"
        return _version(art, snap, valid_from, kind, _known(real), basis), gap, warnings
    if _is_added_kind(art.article_no):
        # No note says when this extra/transitional article came in: only the snapshot is evidence.
        version = _version(art, snap, snap.date, "original", [], "fallback")
        warnings.append("start_unverified")
        gap = (
            _gap(law_from, snap.date, "before_earliest_snapshot", [])
            if law_from != snap.date
            else None
        )
        return version, gap, warnings
    if law_from is None:
        warnings.append("yururluk_unknown")
        return (
            _version(art, snap, snap.date, "original", [], "fallback"),
            (_gap(None, snap.date, "before_earliest_snapshot", [])),
            warnings,
        )
    return _version(art, snap, law_from, "original", [], "act"), None, warnings


def build_article(
    article_no: str,
    inputs: list[SnapshotInput],
    number: str,
    original: tuple[str, date | None],
    registry: Registry,
) -> dict[str, Any]:
    """Versions and gaps of one article over all snapshots (oldest first)."""
    versions: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    warnings: list[str] = []
    current: dict[str, Any] | None = None
    last_art: Article | None = None
    base_art: Article | None = None  # snapshot article the current version's text comes from
    last_idx = -1
    for i, snap in enumerate(inputs):
        art = next((a for a in snap.snapshot.articles if a.article_no == article_no), None)
        notes = snap.notes.get(article_no, [])
        warnings += [f"unparsed_annotation:{r[:60]}" for r in snap.unparsed.get(article_no, [])]
        if art is None:
            if current is not None and last_idx == i - 1:
                current["valid_to"] = _iso(inputs[i - 1].date + DAY)
                gaps.append(_gap(inputs[i - 1].date + DAY, snap.date, "removed_unexplained", []))
                warnings.append("removed_article")
                current = None
            continue
        if current is None and not versions and i == 0:
            first, first_gap, w = _first_snapshot(art, notes, snap, number, original, registry)
            current, base_art = first, art
            versions.append(first)
            if first_gap:
                gaps.append(first_gap)
            warnings += w
            first["warnings"] = list(w)
        elif current is None:
            # Appeared after the first snapshot (or came back): absent at inputs[i - 1].
            tr = _explain(
                art, notes, inputs[i - 1].date, snap.date, snap.date_inferred, number, registry
            )
            kind = "repealed" if art.status == "repealed" else "added"
            current = _version(art, snap, tr.new_from, kind, tr.acts, tr.basis)
            current["warnings"] = list(tr.warnings)
            warnings += tr.warnings
            if tr.gap:
                gaps.append(tr.gap)
            base_art = art
            versions.append(current)
        else:
            assert base_art is not None
            # Compared with the text the version holds, so small drifts cannot add up unseen.
            kind, diff_warnings = compare(
                base_art.text, art.text, marker_numbers(base_art), marker_numbers(art)
            )
            warnings += diff_warnings
            if kind == UNCHANGED:
                # The version keeps the text of the earliest snapshot that evidences it.
                if not same_wording(
                    base_art.text, art.text, marker_numbers(base_art), marker_numbers(art)
                ):
                    current["warnings"] = sorted({*current["warnings"], "uncertain_diff"})
                    warnings.append("uncertain_diff")
                current["evidence"]["snapshots"].append(snap.path)
                current["evidence"]["snapshot_dates"].append(snap.date.isoformat())
            else:
                tr = _explain(
                    art,
                    notes,
                    inputs[last_idx].date,
                    snap.date,
                    snap.date_inferred,
                    number,
                    registry,
                )
                current["valid_to"] = _iso(tr.old_to)
                if tr.gap:
                    gaps.append(tr.gap)
                ck = "repealed" if art.status == "repealed" else "amended"
                current, base_art = _version(art, snap, tr.new_from, ck, tr.acts, tr.basis), art
                current["warnings"] = [*tr.warnings, *diff_warnings]
                warnings += tr.warnings
                versions.append(current)
        last_art, last_idx = art, i
    for v in versions:
        v["confidence"] = confidence.band(v["warnings"])
    latest = last_art
    return {
        "article_no": article_no,
        "ordinal": latest.ordinal if latest else 0,
        "status": latest.status if latest else "removed",
        "heading": latest.heading if latest else "",
        "versions": versions,
        "gaps": gaps,
        "footnotes": [f.to_dict() for f in latest.footnotes] if latest else [],
        "annotations": [n.to_dict() for n in inputs[last_idx].notes.get(article_no, [])]
        if latest
        else [],
        "latest_snapshot_date": inputs[-1].date.isoformat(),
        "warnings": sorted(set(warnings)),
    }


def find_overlaps(timeline: dict[str, Any]) -> list[tuple[str, str]]:
    """Pairs of periods (versions and gaps) of one article timeline that intersect."""
    periods = [(v["valid_from"], v["valid_to"], "version") for v in timeline["versions"]]
    periods += [(g["from"], g["to"], "gap") for g in timeline["gaps"]]
    spans = sorted(
        ((_d(a) or date.min, _d(b) or date.max, kind) for a, b, kind in periods),
        key=lambda p: p[:2],
    )
    return [
        (f"{x[2]} {x[0]}..{x[1]}", f"{y[2]} {y[0]}..{y[1]}")
        for x, y in zip(spans, spans[1:], strict=False)
        if y[0] < x[1]
    ]


def as_of(timeline: dict[str, Any], when: date | str) -> dict[str, Any]:
    """What an article said on `when`: `{status: found, version, confidence}`,
    `{status: gap, gap}` or `{status: not_in_force}` (before the article existed, after it was
    removed, or repealed: then the stub `version` is included).

    Every result carries `latest_snapshot_date` and `stale`: `stale` is true when `when` is after
    the newest snapshot, so the text may have been amended since; the status stays `found` and
    the product says "metin <tarih> itibarıyla". A `found` result carries the `confidence` band
    of its version (`low` versions rest on a fallback boundary): the consumer must not hide it.
    Mirrors the DB query of task 11b, which must return the same three fields."""
    day = _d(when)
    assert day is not None
    latest = timeline["latest_snapshot_date"]
    base = {"latest_snapshot_date": latest, "stale": day > (_d(latest) or date.min)}
    for v in timeline["versions"]:
        start, end = _d(v["valid_from"]), _d(v["valid_to"])
        if (start is None or start <= day) and (end is None or day < end):
            if v["change_kind"] == "repealed":
                return {"status": NOT_IN_FORCE, "reason": "repealed", "version": v, **base}
            return {"status": FOUND, "version": v, "confidence": v["confidence"], **base}
    for g in timeline["gaps"]:
        start, end = _d(g["from"]), _d(g["to"])
        if (start is None or start <= day) and (end is None or day < end):
            return {"status": GAP, "gap": g, **base}
    return {"status": NOT_IN_FORCE, **base}


def statute_as_of(statute: dict[str, Any], article_no: str, when: date | str) -> dict[str, Any]:
    for art in statute["articles"]:
        if art["article_no"] == article_no:
            return as_of(art, when)
    return {"status": UNKNOWN_ARTICLE}
