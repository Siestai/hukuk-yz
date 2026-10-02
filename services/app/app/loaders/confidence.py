"""Deterministic confidence of an extraction (task 05 §4).

One rule table: reason -> (band, penalty). The band is the worst band among the reasons that
fire (no reason: high). The score is 100 minus the penalties, floored at 0: a low reason costs 60
and a medium one 25, so any low-band record scores at most 40 and a single-medium record 75; the
score only orders records inside a band. The review screen sorts by it and may offer bulk
approval of the `high` band; nothing here approves anything.

Why each rule:
- low: a record whose identity (court, esas, karar, date, and chamber where the court has
  chambers) cannot be established cannot be matched against the official source later; this holds
  for every court, so a record without E/K (foreign courts, AYM individual applications) is low
  and never covered by bulk approval. A court the schema does not know (`court_unmapped`,
  `court_level_unmapped`) or a court without a level cannot be published at all. No body or
  summary-only text means there is nothing to cite; a layout the parser does not know means its
  fields are unreliable; duplicate groups whose texts differ or whose dates disagree need a human
  to pick the right file, and the shorter copy of a same-text group is redundant.
- medium: the parser found the field but the record contradicts itself or the field was guessed
  (dates from the closing, inferred statutes, approximate body start).
"""

from typing import Any, Literal

from hukuk_ingest.decisions import qa

Band = Literal["high", "medium", "low"]

LOW_PENALTY = 60
MEDIUM_PENALTY = 25

RULES: dict[str, tuple[Band, int]] = {
    "missing_court": ("low", LOW_PENALTY),
    "missing_esas_no": ("low", LOW_PENALTY),
    "missing_karar_no": ("low", LOW_PENALTY),
    "missing_decision_date": ("low", LOW_PENALTY),
    "missing_chamber": ("low", LOW_PENALTY),
    "court_unmapped": ("low", LOW_PENALTY),
    "court_level_unmapped": ("low", LOW_PENALTY),
    "court_level_missing": ("low", LOW_PENALTY),
    "layout_unknown": ("low", LOW_PENALTY),
    "body_not_found": ("low", LOW_PENALTY),
    "text_summary_only": ("low", LOW_PENALTY),
    "duplicate_different_text": ("low", LOW_PENALTY),
    "duplicate_date_mismatch": ("low", LOW_PENALTY),
    "duplicate_of": ("low", LOW_PENALTY),
    "header_closing_date_mismatch": ("medium", MEDIUM_PENALTY),
    "karar_year_ne_date_year": ("medium", MEDIUM_PENALTY),
    "date_is_lower_court": ("medium", MEDIUM_PENALTY),
    "date_from_closing": ("medium", MEDIUM_PENALTY),
    "body_start_approximate": ("medium", MEDIUM_PENALTY),
    "statute_inferred_from_date": ("medium", MEDIUM_PENALTY),
    "statute_unmapped": ("medium", MEDIUM_PENALTY),
    "date_outside_issue_year": ("medium", MEDIUM_PENALTY),
    "multiple_esas_candidates": ("medium", MEDIUM_PENALTY),
    "duplicate_excerpt": ("medium", MEDIUM_PENALTY),
    "duplicate_same_text": ("medium", MEDIUM_PENALTY),
}
_BAND_ORDER: tuple[Band, ...] = ("low", "medium", "high")


def reasons_of(fields: dict[str, Any], warnings: list[str]) -> list[str]:
    """Rule-table reasons that fire for a normalized record (`fields` as stored on the
    extraction, `warnings` parser + loader warnings), in table order."""
    fired = {f"missing_{name}" for name in qa.CRITICAL_FIELDS if not fields[name]}
    if qa.applies("chamber", fields) and not fields["chamber"]:
        fired.add("missing_chamber")  # the only exemption: courts without chambers
    if fields["court"] and not fields["court_level"]:
        fired.add("court_level_missing")
    fired |= {qa.warning_code(w) for w in warnings}
    if fields["layout"] == "unknown":
        fired.add("layout_unknown")
    if fields["text_completeness"] == "summary_only":
        fired.add("text_summary_only")
    group = fields.get("duplicate_group")
    if group:
        fired.add(f"duplicate_{group['dup_kind']}")
    return [reason for reason in RULES if reason in fired]


def confidence(fields: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """`{"score": 0..100, "band": ..., "reasons": [...]}` for `extraction.confidence`."""
    reasons = reasons_of(fields, warnings)
    band = min((RULES[r][0] for r in reasons), key=_BAND_ORDER.index, default="high")
    score = max(0, 100 - sum(RULES[r][1] for r in reasons))
    return {"score": score, "band": band, "reasons": reasons}
