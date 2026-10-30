"""The hüküm haritası, checked by code: a row stays only if it stands on a source that was read,
in force on the date of the law applied, and its `condition_quote` is in that source word for
word (docs/architecture.md §5.1, item 6)."""

from datetime import date

from agent.llm_schemas import HoldingDraft
from agent.sources import ReadSource, citation, locate, valid_on
from hukuk_models.chat import CaseFacts, HoldingRow
from hukuk_models.formal_turkish import progressive_forms

# A shorter quote is found in any text and proves nothing.
MIN_QUOTE_WORDS = 3


def verify_rows(
    draft: HoldingDraft, read: list[ReadSource], applied_on: date, *, facts: CaseFacts | None = None
) -> tuple[list[HoldingRow], int]:
    """Check provenance and declared dependencies, not legal entailment.

    Dependency completeness is a model responsibility. Unrelated unknown facts do not
    invalidate a known condition; a declared unknown cannot support met/not_met.
    """
    sources = {s.source_id: s for s in read}
    rows = []
    values = {f.key: f for f in facts.facts} if facts is not None else {}
    for row in draft.rows:
        source = sources.get(row.source_id)
        quote = row.condition_quote.strip()
        if (
            source is None
            or not valid_on(source, applied_on)
            or len(quote.split()) < MIN_QUOTE_WORDS
            or locate(source, quote) is None
            or progressive_forms([row.condition, row.fact_value or ""])
        ):
            continue
        unresolved = any(
            key not in values or values[key].status == "unknown" for key in row.depends_on_facts
        )
        result = "unknown" if unresolved and row.result in ("met", "not_met") else row.result
        rows.append(
            HoldingRow(
                condition=row.condition,
                condition_quote=quote,
                citation=citation(source, sub=row.sub, quote=quote),
                fact_value=row.fact_value,
                result=result,
            )
        )
    return rows, len(draft.rows) - len(rows)
