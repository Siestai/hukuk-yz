"""Missing-field and warning rules per record, and the corpus-level date plausibility check."""

from collections import defaultdict
from statistics import median
from typing import Any

from hukuk_ingest.decisions.layout import Layout

FIELDS = (
    "court",
    "court_level",
    "chamber",
    "esas_no",
    "karar_no",
    "decision_date",
    "related_articles",
    "keywords",
    "outcome",
    "editorial_summary",
    "full_text",
)
CRITICAL_FIELDS = ("court", "esas_no", "karar_no", "decision_date")
# A decision date this many years away from its journal year is suspicious (typo or wrong parse).
MAX_YEAR_GAP = 3
_FOREIGN_COURTS = {"foreign", "abad", "aihm"}


def applies(name: str, record: dict[str, Any]) -> bool:
    """Whether the field is expected for this kind of decision. Foreign-court articles carry no
    Esas/Karar numbers, statutes, keywords or ruling; an AYM individual application prints a
    Başvuru No (kept as esas_no) and no Karar No; chamberless courts have no chamber."""
    if name == "chamber":
        return bool(record["court_level"] in ("daire", "bam_bim"))
    if name in ("esas_no", "karar_no", "related_articles", "keywords", "outcome"):
        if record["court"] in _FOREIGN_COURTS:
            return False
        return not (name == "karar_no" and record["decision_kind"] == "bireysel_basvuru")
    return True


def missing_fields(record: dict[str, Any]) -> list[str]:
    """Applicable fields that were not extracted."""
    return [name for name in FIELDS if applies(name, record) and not record[name]]


def record_warnings(warnings: list[str], layout: Layout, has_body: bool) -> list[str]:
    out = list(warnings)
    if layout is Layout.UNKNOWN:
        out.append("layout_unknown")
    if not has_body:
        out.append("body_not_found")
    return out


def issue_years(rows: list[tuple[int, str]]) -> dict[int, int]:
    """Median decision year per journal issue: the stand-in for the journal year of issues
    whose pages carry no "Çalışma ve Toplum, YYYY/N" header."""
    years: dict[int, list[int]] = defaultdict(list)
    for issue, decision_date in rows:
        if decision_date:
            years[issue].append(int(decision_date[:4]))
    return {issue: round(median(ys)) for issue, ys in years.items()}


def date_outside_issue_year(decision_date: str, reference_year: int | None) -> bool:
    if not decision_date or reference_year is None:
        return False
    return abs(int(decision_date[:4]) - reference_year) > MAX_YEAR_GAP


def warning_code(warning: str) -> str:
    """ "multiple_esas_candidates:2010/1" counts under "multiple_esas_candidates"."""
    return warning.split(":", 1)[0]


def fill_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per field: how many records need it, and how many have it."""
    out: dict[str, dict[str, int]] = {}
    for name in FIELDS:
        applicable = [r for r in records if applies(name, r)]
        out[name] = {"applicable": len(applicable), "filled": sum(1 for r in applicable if r[name])}
    return out
