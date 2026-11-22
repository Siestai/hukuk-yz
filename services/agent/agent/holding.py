"""The hüküm haritası, checked by code: a row stays only if it stands on a source that was read,
in force on the date of the law applied, and its `condition_quote` is in that source word for
word, in the paragraph the row cites (docs/architecture.md §5.1, item 6)."""

import re
from datetime import date

from agent.llm_schemas import HoldingDraft, RowDraft
from agent.sources import ReadSource, citation, locate, quote_paragraph, valid_on
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


def verify_rows(
    draft: HoldingDraft, read: list[ReadSource], applied_on: date, *, facts: CaseFacts | None = None
) -> tuple[list[HoldingRow], int]:
    """Check provenance and declared dependencies, not legal entailment.

    Dependency completeness is a model responsibility. Unrelated unknown facts do not
    invalidate a known condition; a declared unknown cannot support met/not_met. With `facts`,
    a row that depends on a key that is no fact of the template is dropped.
    """
    sources = {s.source_id: s for s in read}
    rows = []
    values = {f.key: f for f in facts.facts} if facts is not None else {}
    for row in draft.rows:
        source = sources.get(row.source_id)
        quote = row.condition_quote.strip()
        fact_value = _UNKNOWN_VALUE.sub(r"\1ilinmemektedir", row.fact_value or "") or None
        if (
            source is None
            or not valid_on(source, applied_on)
            or len(quote.split()) < MIN_QUOTE_WORDS
            or locate(source, quote) is None
            or _other_paragraph(source, row, quote)
            or progressive_forms([row.condition, fact_value or ""])
            or (facts is not None and any(k not in values for k in row.depends_on_facts))
        ):
            continue
        unresolved = fact_value != (row.fact_value or None) or any(
            key not in values or values[key].status == "unknown" for key in row.depends_on_facts
        )
        result = "unknown" if unresolved and row.result in ("met", "not_met") else row.result
        rows.append(
            HoldingRow(
                condition=row.condition,
                condition_quote=quote,
                citation=citation(source, sub=row.sub, quote=quote),
                fact_value=fact_value,
                result=result,
            )
        )
    return rows, len(draft.rows) - len(rows)
