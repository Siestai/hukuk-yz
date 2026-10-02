"""Verify one decision against its official source: look it up, match, fetch the official text
for its hash (task 06 §3-§4, §7). No database: the caller persists the `VerifyResult`."""

import re

from hukuk_verify.adapters.base import SourceAdapter
from hukuk_verify.matching import match_rows, source_chamber_match
from hukuk_verify.models import DecisionKey, FieldMatch, OfficialText, Outcome, VerifyResult

PRE_2009_LAST_YEAR = 2009
HEADING_CHARS = 1500
_TAG = re.compile(r"<[^>]+>")


def is_pre_2009(adapter: SourceAdapter, key: DecisionKey) -> bool:
    """True for a decision the Yargıtay adapter skips without a query (task 06 §7)."""
    return (
        adapter.PRE_2009_SKIP
        and key.decision_date is not None
        and key.decision_date.year <= PRE_2009_LAST_YEAR
    )


def _heading(text: OfficialText | None) -> str:
    return (
        " ".join(_TAG.sub(" ", text.body[: HEADING_CHARS * 4]).split())[:HEADING_CHARS]
        if text
        else ""
    )


async def verify(
    adapter: SourceAdapter, key: DecisionKey, *, skip_pre_2009: bool = True
) -> VerifyResult:
    """A lookup failure raises (see `hukuk_verify.errors`); it is never `not_in_source`."""
    if skip_pre_2009 and is_pre_2009(adapter, key):
        return VerifyResult(
            Outcome.not_in_source, adapter.SOURCE, matched={"skipped": "pre_2009_heuristic"}
        )
    decision = match_rows(key, (await adapter.lookup(key)).rows)
    if decision.row is None:
        return VerifyResult(Outcome.not_in_source, adapter.SOURCE, matched=decision.matched)
    row, matched = decision.row, dict(decision.matched)
    if decision.kind == "mismatch":
        return VerifyResult(Outcome.mismatch, adapter.SOURCE, row.ref, row.url, matched)

    text = await adapter.fetch_text(row.ref)
    chamber = source_chamber_match(key, _heading(text))
    matched["source_chamber"] = chamber
    if chamber is FieldMatch.fuzzy:
        matched["fuzzy"] = [*matched["fuzzy"], "source_chamber"]
    return VerifyResult(adapter.VERIFIED, adapter.SOURCE, row.ref, row.url, matched, text)
