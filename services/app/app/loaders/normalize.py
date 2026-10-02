"""Loader-side normalization of parser fields (task 05 §3). The parser stays untouched."""

from datetime import date
from typing import Any

from app.models.common import Court, CourtLevel

# Parser label -> ASCII label of data-model.md §5.2. Every other accepted label is its own.
OUTCOME_ALIASES = {"düzelterek onama": "duzelterek_onama"}
OUTCOMES = frozenset({"bozma", "onama", "duzelterek_onama", "kabul", "red", "ihlal", "ihlal_yok"})
# Parser bookkeeping kept out of `fields`: it lives in ingest_file, raw_text_ref and extraction.
BOOKKEEPING = frozenset({"status", "error", "warnings", "source_path", "sha256"})
COURTS = frozenset(c.value for c in Court)
COURT_LEVELS = frozenset(c.value for c in CourtLevel)


def normalize(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The row without the parser bookkeeping, with `outcome`, `court`, `court_level` and
    `decision_date` normalized, and the warnings the loader adds. A value outside the schema
    enums becomes '' plus a warning; it is never forced into an enum. Empty values stay empty."""
    out = {k: v for k, v in row.items() if k not in BOOKKEEPING}
    warnings: list[str] = []

    outcome = OUTCOME_ALIASES.get(row["outcome"], row["outcome"])
    if outcome and outcome not in OUTCOMES:
        outcome = ""
        warnings.append("outcome_unmapped")
    out["outcome"] = outcome

    if not row["court"]:
        warnings.append("court_missing")
    elif row["court"] not in COURTS:
        out["court"] = ""
        warnings.append("court_unmapped")
    if row["court_level"] and row["court_level"] not in COURT_LEVELS:
        out["court_level"] = ""
        warnings.append("court_level_unmapped")

    try:
        date.fromisoformat(row["decision_date"])
    except ValueError:
        out["decision_date"] = ""  # the parser's own warning (invalid_date) is kept as is
    return out, warnings
