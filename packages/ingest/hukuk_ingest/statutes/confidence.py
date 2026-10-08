"""Confidence band of an article timeline (task 11a, rules of the spec in one table).

`low` wins over `medium`, `medium` over `high`. A warning may carry a detail after a colon
(`number_skipped:main:86->88`); only the part before the colon is looked up."""

from collections.abc import Iterable

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

# warning code -> band; codes missing here do not lower the band (informational).
RULES: dict[str, str] = {
    # splitting doubts
    "number_skipped": LOW,
    "number_out_of_order": LOW,
    "duplicate_article": LOW,
    "unparsed_article_no": LOW,
    # transitions that no registered act explains
    "unexplained_change": LOW,
    "multi_amendment_in_window": LOW,
    "unparsed_annotation": LOW,
    "yururluk_unknown": LOW,
    "yururluk_outside_window": LOW,
    "removed_article": LOW,
    "footnote_leak_suspect": LOW,
    # clean, but with a caveat
    "exception_effective": MEDIUM,
    "split_effective_dates": MEDIUM,
    "partial_entry_into_force": MEDIUM,
    "uncertain_diff": MEDIUM,
    "before_earliest_snapshot": MEDIUM,
    "start_unverified": MEDIUM,
    "heading_suspect": MEDIUM,
    "section_title_guess": MEDIUM,
}
_ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2}


def code(warning: str) -> str:
    return warning.split(":", 1)[0]


def band(warnings: Iterable[str]) -> str:
    worst = HIGH
    for w in warnings:
        b = RULES.get(code(w), HIGH)
        if _ORDER[b] < _ORDER[worst]:
            worst = b
    return worst
