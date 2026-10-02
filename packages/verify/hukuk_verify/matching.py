"""Field-by-field comparison of a decision with the rows an official source returned (task 06 §4).

Pure functions: no network, no database. Every comparison folds Turkish case and diacritics first
(`İ`/`ı` included), and ignores punctuation and extra whitespace."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from hukuk_verify.models import DecisionKey, FieldMatch, OfficialRow

FUZZY_DAYS = 3

_ASCII = str.maketrans("ıçğöşü", "icgosu")
_NOT_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBERED = re.compile(r"\b(\d+) (hukuk dairesi|ceza dairesi|daire|hd|cd|d)\b")
_REGION = re.compile(r"^(.*?)\s*\b(?:bolge adliye mahkemesi|bam)\b")
_KINDS = {
    "hukuk dairesi": "HD",
    "hd": "HD",
    "ceza dairesi": "CD",
    "cd": "CD",
    "daire": "D",
    "d": "D",
}
# Named bodies without a number, by folded name. Only the one an expectation exists for.
_BODIES = {
    "hukuk genel kurulu": "HGK",
    "hgk": "HGK",
}
_ESAS_KARAR = re.compile(r"^(\d{4}) ?/ ?(?:\d+ ?- ?)?0*(\d+)$")


def fold(text: str) -> str:
    """Lower case the Turkish way (`İ` -> i, `I` -> ı), drop diacritics and punctuation."""
    lowered = text.replace("İ", "i").replace("I", "ı").lower().translate(_ASCII)
    return _NOT_ALNUM.sub(" ", lowered).strip()


def canonical_chamber(raw: str) -> str | None:
    """`"Yargıtay 9. Hukuk Dairesi"`, `"9. HD"` -> `"9 HD"`; `"n. D"` ≡ `"n. Daire"` -> `"n D"`;
    a named body such as `"Hukuk Genel Kurulu"` -> `"HGK"`. None for an empty string."""
    folded = fold(raw)
    if not folded:
        return None
    if numbered := _NUMBERED.search(folded):
        return f"{numbered.group(1)} {_KINDS[numbered.group(2)]}"
    return _BODIES.get(folded, folded)


def bam_region(raw: str) -> str:
    """The folded region in front of "Bölge Adliye Mahkemesi" / "BAM"; '' when there is none.
    `Istanbul` and `İstanbul` fold to the same word."""
    found = _REGION.match(fold(raw))
    return found.group(1) if found else ""


def normalize_number(raw: str) -> str:
    """`"2017/016188"` -> `"2017/16188"`; an HGK `"2024/10-389"` -> `"2024/389"` (the
    originating chamber is compared separately). Anything else is folded."""
    found = _ESAS_KARAR.match(raw.strip())
    return f"{found.group(1)}/{found.group(2)}" if found else fold(raw)


def compare_dates(wanted: date | None, found: date | None) -> FieldMatch:
    if wanted is None or found is None:
        return FieldMatch.absent
    days = abs((wanted - found).days)
    if days == 0:
        return FieldMatch.match
    return FieldMatch.fuzzy if days <= FUZZY_DAYS else FieldMatch.mismatch


def expected_chamber(key: DecisionKey) -> str | None:
    """The canonical chamber the site must show; None when the decision has none to check
    (AYM, İBK)."""
    if key.chamber:
        return canonical_chamber(key.chamber)
    if key.court == "yargitay" and key.court_level == "hgk_iddk":
        return "HGK"
    return None


def _compare_chamber(key: DecisionKey, row: OfficialRow) -> FieldMatch:
    expected = expected_chamber(key)
    if expected is None:
        return FieldMatch.absent
    return FieldMatch.match if canonical_chamber(row.chamber) == expected else FieldMatch.mismatch


def _compare_region(key: DecisionKey, row: OfficialRow) -> FieldMatch:
    found = bam_region(row.chamber)
    if not key.bam_region or not found:
        return FieldMatch.absent
    return FieldMatch.match if fold(key.bam_region) == found else FieldMatch.mismatch


@dataclass(frozen=True)
class RowMatch:
    row: OfficialRow
    chamber: FieldMatch
    bam_region: FieldMatch
    decision_date: FieldMatch

    @property
    def _same_place(self) -> bool:
        ok = (FieldMatch.match, FieldMatch.absent)
        return self.chamber in ok and self.bam_region in ok

    @property
    def exact(self) -> bool:
        return self._same_place and self.decision_date in (FieldMatch.match, FieldMatch.absent)

    @property
    def acceptable(self) -> bool:
        """A date that is only fuzzy still verifies."""
        return self._same_place and self.decision_date is not FieldMatch.mismatch

    def fields(self) -> dict[str, str]:
        return {
            "esas_no": FieldMatch.match,
            "karar_no": FieldMatch.match,
            "chamber": self.chamber,
            "bam_region": self.bam_region,
            "decision_date": self.decision_date,
        }


@dataclass(frozen=True)
class Decision:
    """`kind` is `not_in_source`, `verified` or `mismatch`; `row` is the chosen (or, for a
    mismatch, the first candidate) row and None only for `not_in_source`."""

    kind: str
    row: OfficialRow | None
    matched: dict[str, Any]


def match_rows(key: DecisionKey, rows: list[OfficialRow]) -> Decision:
    """Combine the rows of a search by esas and karar number into one verdict (§4 "Birleştirme").

    A row whose E/K differs is not a candidate. No candidate: `not_in_source`. One exact (chamber
    and date match) candidate, else one acceptable one: `verified`. Several equally good
    candidates: `mismatch` with `ambiguous`. A candidate whose chamber or date disagrees:
    `mismatch`. A decision without a date is judged on E/K and chamber alone."""
    wanted = (normalize_number(key.esas_no or ""), normalize_number(key.karar_no or ""))
    candidates = [
        RowMatch(
            row,
            _compare_chamber(key, row),
            _compare_region(key, row),
            compare_dates(key.decision_date, row.decision_date),
        )
        for row in rows
        if (normalize_number(row.esas_no), normalize_number(row.karar_no)) == wanted
    ]
    summary: dict[str, Any] = {"rows": len(rows), "candidates": len(candidates)}
    if not candidates:
        return Decision("not_in_source", None, summary)

    exact = [c for c in candidates if c.exact]
    acceptable = [c for c in candidates if c.acceptable]
    pool = exact or acceptable
    chosen = pool[0] if len(pool) == 1 else None
    best = chosen or candidates[0]
    matched = {
        **summary,
        **best.fields(),
        "site": {
            "chamber": best.row.chamber,
            "esas_no": best.row.esas_no,
            "karar_no": best.row.karar_no,
            "decision_date": best.row.decision_date.isoformat() if best.row.decision_date else None,
        },
        "fuzzy": [name for name, found in best.fields().items() if found is FieldMatch.fuzzy],
    }
    if len(pool) > 1:
        matched["ambiguous"] = True
    return Decision("verified" if chosen else "mismatch", best.row, matched)


def source_chamber_match(key: DecisionKey, heading: str) -> FieldMatch:
    """HGK decisions: karararama keeps no originating chamber (`YYYY/D-N` becomes `YYYY/N`), so
    `D` is looked for in the heading line of the official text. Not found is only `fuzzy`."""
    if not key.source_chamber or not key.esas_no:
        return FieldMatch.absent
    year, _, number = normalize_number(key.esas_no).partition("/")
    pattern = rf"\b{year} ?/ ?{re.escape(key.source_chamber)} ?- ?0*{number}\b"
    return FieldMatch.match if re.search(pattern, heading) else FieldMatch.fuzzy
