"""What the agent has read (md. 25): the sources the answer may cite.

The list is written by code from what the knowledge base returned, never by a model. A citation
is built from a read source: its künye, label and status are the source's own, so a model can
pick a source but cannot make one up.
"""

import re
from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel

from agent.kb import KbHit
from hukuk_models.chat import (
    CitationCategory,
    CitationRef,
    ReadSources,
    ReviewStatus,
    Verification,
)

# "4857 m.18/1" -> ("4857 m.18", "/1"); a künye without a statute article is its own base.
_STATUTE_REF = re.compile(r"^(?P<base>\d+ m\.\d+(?:\s?[A-Za-z])?)(?P<sub>/.+)?$")
_WORD = re.compile(r"\S+")


class Passage(BaseModel):
    # Offset of `text` in the full text of the source; None when the knowledge base gave none.
    char_start: int | None
    text: str


class ReadSource(BaseModel):
    source_id: str
    category: CitationCategory
    title: str
    ref: str
    review_status: ReviewStatus
    verification: Verification
    valid_from: date | None
    valid_to: date | None
    passages: list[Passage]


def split_ref(ref: str) -> tuple[str, str]:
    """Splits "4857 m.18/1" into ("4857 m.18", "/1"): the article and the paragraph part."""
    found = _STATUTE_REF.match(ref.strip())
    if found is None:
        return ref.strip(), ""
    return found["base"], found["sub"] or ""


def _key(ref: str) -> str:
    return " ".join(ref.replace("İ", "i").replace("I", "ı").lower().split())


def covers(hit_ref: str, wanted: str) -> bool:
    """`hit_ref` is the künye wanted or a part of it ("4857 m.18" covers "4857 m.18/1")."""
    hit, want = _key(hit_ref), _key(split_ref(wanted)[0])
    return hit == want or hit.startswith((want + "/", want + " "))


def as_read_source(hit: KbHit) -> ReadSource | None:
    """The hit as a read source; None when none of its passages came with text."""
    passages = [
        Passage(char_start=m.char_start, text=m.text) for m in hit.matches if m.text is not None
    ]
    if not passages:
        return None
    return ReadSource(
        source_id=hit.source_id,
        category=hit.category,
        title=hit.title,
        ref=hit.ref,
        review_status=hit.review_status,
        verification=hit.verification or "not_applicable",
        valid_from=hit.valid_from,
        valid_to=hit.valid_to,
        passages=passages,
    )


def merge(read: Iterable[ReadSource], new: Iterable[ReadSource]) -> list[ReadSource]:
    """`read` plus `new`; a source read twice keeps each of its passages once."""
    merged = {s.source_id: s.model_copy(deep=True) for s in read}
    for source in new:
        have = merged.get(source.source_id)
        if have is None:
            merged[source.source_id] = source.model_copy(deep=True)
            continue
        seen = {(p.char_start, p.text) for p in have.passages}
        have.passages += [p for p in source.passages if (p.char_start, p.text) not in seen]
    return list(merged.values())


def locate(source: ReadSource, quote: str) -> tuple[int | None, int | None] | None:
    """Where `quote` stands in the text read of `source`, matching it word for word (the white
    space may differ). None: it is not there. The offsets are into the source's full text and
    are None when the passage had no offset."""
    words = _WORD.findall(quote)
    if not words:
        return None
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words))
    for passage in source.passages:
        found = pattern.search(passage.text)
        if found is None:
            continue
        if passage.char_start is None:
            return None, None
        return passage.char_start + found.start(), passage.char_start + found.end()
    return None


def valid_on(source: ReadSource, day: date) -> bool:
    """The text of `source` is in force on `day`; a bound that was not recorded does not bind."""
    return (source.valid_from is None or source.valid_from <= day) and (
        source.valid_to is None or day <= source.valid_to
    )


def citation(
    source: ReadSource,
    *,
    sub: str | None = None,
    quote: str | None = None,
    used_for: str | None = None,
) -> CitationRef:
    """A citation of `source`, with `sub` ("1": the paragraph) and `quote` if given. The caller
    has checked the quote with `locate`."""
    suffix = f"/{sub}" if sub else ""
    start = end = None
    if quote is not None and (where := locate(source, quote)) is not None:
        start, end = where
    return CitationRef(
        source_id=source.source_id,
        category=source.category,
        label=source.title + suffix,
        ref=source.ref + suffix,
        review_status=source.review_status,
        verification=source.verification,
        valid_from=source.valid_from,
        valid_to=source.valid_to,
        quote=quote,
        char_start=start,
        char_end=end,
        used_for=used_for,
    )


def summarize(read: Iterable[ReadSource]) -> ReadSources:
    """ "Okunanlar": every source read, once, with the counts per category."""
    items = [citation(s) for s in read]
    return ReadSources(
        statute_articles=sum(c.category == "statute" for c in items),
        decisions=sum(c.category == "decision" for c in items),
        admin_acts=sum(c.category == "admin_act" for c in items),
        items=items,
    )
