"""The hüküm haritası, checked by code: a row stays only if it stands on a source that was read,
in force on the date of the law applied, and its `condition_quote` is in that source word for
word, in the paragraph the row cites (docs/architecture.md §5.1, item 6)."""

import re
from collections import Counter
from datetime import date
from typing import NamedTuple

from agent.llm_schemas import HoldingDraft, RowDraft
from agent.sources import (
    ReadSource,
    checked_sub,
    citation,
    kunye_sub,
    locate,
    named_source,
    quote_paragraph,
    valid_on,
)
from hukuk_models.chat import CaseFacts, HoldingRow
from hukuk_models.formal_turkish import progressive_forms

# A shorter quote is found in any text and proves nothing.
MIN_QUOTE_WORDS = 3
# "bilinmiyor" in a fact value is the value of an unknown fact, said in the "-iyor" form: the row
# is a conditional branch, not a register error. Code writes it formally; any other "-iyor" form
# still drops the row.
_UNKNOWN_VALUE = re.compile(r"\b([Bb])ilinmiyor\b")
# The paragraph a sub names: "4" of "4", "4-a" or "4 a"; a sub with no number names none.
_SUB_PARAGRAPH = re.compile(r"^([1-9]\d*)(?!\d)")


# Why a row drops: fixed codes, for the trace and the eval table (never the row's words).
UNREAD_SOURCE = "unread_source"
NOT_IN_FORCE = "not_in_force"
SHORT_QUOTE = "short_quote"
QUOTE_NOT_FOUND = "quote_not_found"
OTHER_PARAGRAPH = "other_paragraph"
PROGRESSIVE = "progressive"
UNKNOWN_KEY = "unknown_key"


class Verified(NamedTuple):
    rows: list[HoldingRow]
    # The rows dropped, by the code of why.
    dropped_by: dict[str, int]
    # The paragraphs of kept rows that the text read did not bear out: cited at article level.
    subs_dropped: int


def invented_keys(draft: HoldingDraft, facts: CaseFacts) -> list[str]:
    """The dependency keys of the rows that are no fact of the template (the facts are those of
    the template), each once, in the order written."""
    keys = {f.key for f in facts.facts}
    found = [k for r in draft.rows for k in r.depends_on_facts if k not in keys]
    return list(dict.fromkeys(found))


def key_feedback(invented: list[str], facts: CaseFacts) -> str:
    """What the holding model is told when its rows depend on keys the template does not have."""
    return (
        f"depends_on_facts içinde olgu listesinde olmayan anahtar: {', '.join(invented)}. "
        f"Yalnız şu anahtarları kullan: {', '.join(f.key for f in facts.facts)}; "
        "bu anahtarlara dayanmayan satır silinir."
    )


def _other_paragraph(source: ReadSource, row: RowDraft, quote: str) -> bool:
    """The row cites a paragraph, and its quote stands in another one of the text read."""
    cited = _SUB_PARAGRAPH.match(row.sub or "")
    if cited is None:
        return False
    found = quote_paragraph(source, quote, cited[1])
    return found is not None and found != cited[1]


def _with_kunye_sub(row: RowDraft) -> RowDraft:
    """The row with the paragraph of the künye in its `source_id` as its sub, when it has none."""
    if row.sub or (sub := kunye_sub(row.source_id)) is None:
        return row
    return row.model_copy(update={"sub": sub})


def _formal_value(row: RowDraft) -> str | None:
    return _UNKNOWN_VALUE.sub(r"\1ilinmemektedir", row.fact_value or "") or None


def _problems(
    row: RowDraft,
    source: ReadSource | None,
    applied_on: date,
    keys: set[str] | None,
) -> list[str]:
    """Why the row drops, as fixed codes in the order checked; empty: it stays. `source`: the
    source read the row names (`named_source`); `keys`: the facts of the template. A row on a
    source not read or not in force has no other code."""
    if source is None:
        return [UNREAD_SOURCE]
    if not valid_on(source, applied_on):
        return [NOT_IN_FORCE]
    quote = row.condition_quote.strip()
    problems = []
    if len(quote.split()) < MIN_QUOTE_WORDS:
        problems.append(SHORT_QUOTE)
    elif locate(source, quote) is None:
        problems.append(QUOTE_NOT_FOUND)
    elif _other_paragraph(source, row, quote):
        problems.append(OTHER_PARAGRAPH)
    if progressive_forms([row.condition, _formal_value(row) or ""]):
        problems.append(PROGRESSIVE)
    if keys is not None and any(k not in keys for k in row.depends_on_facts):
        problems.append(UNKNOWN_KEY)
    return problems


_ROW_FEEDBACK = {
    UNREAD_SOURCE: "source_id okunan kaynak listesinde yoktur; kaynak listesindeki "
    "[source_id: ...] değerlerinden birini aynen yaz",
    SHORT_QUOTE: "condition_quote en az üç kelime olmalıdır",
    QUOTE_NOT_FOUND: "condition_quote kaynak metinde birebir geçmemektedir; "
    "kaynaktan aynen kopyala",
    OTHER_PARAGRAPH: "condition_quote atıf yapılan fıkrada (sub) değil, başka bir fıkradadır; "
    "sub değerini alıntının bulunduğu fıkra yap",
    PROGRESSIVE: "condition veya fact_value -iyor kipindedir ({forms}); -mektedir / -maktadır "
    "kipi veya geniş zamanla yaz",
}


def holding_feedback(
    draft: HoldingDraft, read: list[ReadSource], applied_on: date, facts: CaseFacts
) -> list[str]:
    """What the holding model is told in its one correction, for every row it can mend: an
    invented key, a source_id that names no source read, a quote that is not in the text read
    (or too short, or in another paragraph), an "-iyor" form. Empty: no row needs it. A row on a
    text not in force is no model error that a correction mends; it drops."""
    sources = {s.source_id: s for s in read}
    feedback = []
    if invented := invented_keys(draft, facts):
        feedback.append(key_feedback(invented, facts))
    for number, row in enumerate(draft.rows, start=1):
        forms = ", ".join(progressive_forms([row.condition, _formal_value(row) or ""]))
        if found := [
            _ROW_FEEDBACK[p].format(forms=forms)
            for p in _problems(
                _with_kunye_sub(row), named_source(sources, row.source_id), applied_on, None
            )
            if p in _ROW_FEEDBACK
        ]:
            feedback.append(
                f"{number}. satır ({row.source_id}, «{row.condition_quote.strip()}»): "
                f"{'; '.join(found)}; düzeltilmeyen satır silinir."
            )
    return feedback


def verify_rows(
    draft: HoldingDraft, read: list[ReadSource], applied_on: date, *, facts: CaseFacts | None = None
) -> Verified:
    """Check provenance and declared dependencies, not legal entailment.

    Dependency completeness is a model responsibility. Unrelated unknown facts do not
    invalidate a known condition; a declared unknown cannot support met/not_met. With `facts`,
    a row that depends on a key that is no fact of the template is dropped.
    """
    sources = {s.source_id: s for s in read}
    rows = []
    dropped: Counter[str] = Counter()
    subs_dropped = 0
    values = {f.key: f for f in facts.facts} if facts is not None else {}
    keys = set(values) if facts is not None else None
    for row in draft.rows:
        source = named_source(sources, row.source_id)
        row = _with_kunye_sub(row)
        problems = _problems(row, source, applied_on, keys)
        if source is None or problems:
            dropped[problems[0]] += 1
            continue
        quote = row.condition_quote.strip()
        fact_value = _formal_value(row)
        unresolved = fact_value != (row.fact_value or None) or any(
            key not in values or values[key].status == "unknown" for key in row.depends_on_facts
        )
        result = "unknown" if unresolved and row.result in ("met", "not_met") else row.result
        subs_dropped += bool(row.sub) and checked_sub(source, row.sub, quote) is None
        cited = citation(source, sub=row.sub, quote=quote)
        rows.append(
            HoldingRow(
                condition=row.condition,
                condition_quote=cited.quote or quote,
                citation=cited,
                fact_value=fact_value,
                result=result,
            )
        )
    return Verified(rows, dict(dropped), subs_dropped)
