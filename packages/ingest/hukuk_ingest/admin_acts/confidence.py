"""Confidence band of a genelge section (handoff 2026-11-22, A3), as for statute articles: `low`
wins over `medium`, `medium` over `high`; a warning may carry a detail after a colon."""

from collections.abc import Iterable

from hukuk_ingest.statutes.confidence import HIGH, LOW, MEDIUM, code

# warning code -> band; codes missing here do not lower the band (informational).
RULES: dict[str, str] = {
    # the text of the section may be incomplete or not its own
    "number_skipped": LOW,
    "page_without_text": LOW,
    "unparsed_amendment_note": LOW,
    "issue_date_unknown": LOW,
    # clean, but with a caveat
    "amended_in_place": MEDIUM,
    "unplaced_heading": MEDIUM,
    "closing_not_found": MEDIUM,
    "ocr_text": MEDIUM,
}
_ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2}


def band(warnings: Iterable[str]) -> str:
    return min((RULES.get(code(w), HIGH) for w in warnings), key=_ORDER.__getitem__, default=HIGH)
