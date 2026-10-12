"""What a suggestion is made of: the value, where it came from and the quote that shows it."""

import re
from dataclasses import dataclass
from typing import Any

from hukuk_ingest.decisions.fields import tr_lower
from hukuk_ingest.quality import PAGE_BREAK

FIELDS = ("doc_type", "doc_date", "official_ref", "title", "issuer")
# The labels of the `document_type` enum of the app (a test keeps the two in step).
DOC_TYPES = (
    "kanun",
    "cbk",
    "yonetmelik",
    "teblig",
    "genelge",
    "genel_yazi",
    "ic_emri",
    "karar",
    "kitap",
    "hesap_tablosu",
    "gorus",
    "diger",
)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Suggestion:
    """One suggested field. `evidence` is `{"page": 1, "quote": "GENELGE 2024/5"}` for a quote
    found in the text, `{"file_type": "xlsx_xlsm"}` for a suggestion from the file type, and None
    for a suggestion nothing in the text supports (an LLM answer without a quote)."""

    value: str
    source: str  # "rule" | "llm"
    evidence: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "source": self.source, "evidence": self.evidence}


Suggestions = dict[str, Suggestion]


def collapse(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def page_of(text: str, offset: int) -> int:
    return text.count(PAGE_BREAK, 0, offset) + 1


def span_evidence(text: str, start: int, end: int) -> dict[str, Any]:
    return {"page": page_of(text, start), "quote": collapse(text[start:end])}


def _fold(text: str) -> tuple[str, list[int]]:
    """The text lower-cased (Turkish rules) with every run of white space as one space, and for
    every character of the result its offset in the original."""
    folded: list[str] = []
    offsets: list[int] = []
    previous_space = True
    for offset, char in enumerate(text):
        if char.isspace():
            if not previous_space:
                folded.append(" ")
                offsets.append(offset)
            previous_space = True
            continue
        previous_space = False
        for lowered in tr_lower(char):
            folded.append(lowered)
            offsets.append(offset)
    return "".join(folded), offsets


def locate(text: str, quote: str) -> dict[str, Any] | None:
    """Evidence for `quote` if it occurs in `text`, ignoring case and white space; else None."""
    needle = collapse(tr_lower(quote))
    if not needle:
        return None
    folded, offsets = _fold(text)
    at = folded.find(needle)
    if at < 0:
        return None
    start, end = offsets[at], offsets[at + len(needle) - 1] + 1
    return span_evidence(text, start, end)
