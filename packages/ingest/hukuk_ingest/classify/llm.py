"""The language-model fallback of the detection (task 13a): provider-neutral parts only.

The provider sits behind `Detector`; this module builds what is sent, and checks what comes back.
Nothing the model says is trusted: every field must come with a quote that occurs in the
extracted text, and a date must be the date its quote shows (md. 25)."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from hukuk_ingest.classify.evidence import (
    DOC_TYPES,
    FIELDS,
    Suggestion,
    Suggestions,
    collapse,
    locate,
)
from hukuk_ingest.decisions.fields import parse_date, tr_lower
from hukuk_ingest.quality import PAGE_BREAK

MAX_PAGES = 2
MAX_CHARS = 6000
MAX_VALUE_CHARS = 300


class DetectorError(Exception):
    """The provider failed (time-out, quota, unreadable answer). The scan goes on without it."""


@dataclass(frozen=True)
class DetectRequest:
    file_name: str
    text: str  # the excerpt, not the whole document
    fields: tuple[str, ...]  # what the rules left empty


@dataclass(frozen=True)
class DetectResult:
    """`answer` is `{field: {"value": ..., "quote": ...}}`; unknown fields are absent or null."""

    answer: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int


class Detector(Protocol):
    def detect(self, request: DetectRequest) -> DetectResult: ...


SYSTEM_PROMPT = (
    "You read the opening of a Turkish legal document (labour and social security law) and "
    "report its type and reference fields. Answer only with JSON. For every field you can read "
    'in the text give {"value": ..., "quote": ...} where quote is the exact words from the '
    "text that show it. Leave out a field the text does not show; never guess. doc_type is one "
    f"of: {', '.join(DOC_TYPES)}. doc_date is the date of the document as YYYY-MM-DD. "
    "official_ref is its number (law number, circular number such as 2024/5, Esas/Karar "
    "numbers, letter number). title is its title or subject. issuer is the institution or "
    "court that issued it."
)


def answer_schema(fields: tuple[str, ...]) -> dict[str, Any]:
    """JSON schema of the answer for the requested fields."""
    value: dict[str, Any] = {"type": "string"}
    entry = {
        "type": "object",
        "properties": {"value": value, "quote": {"type": "string"}},
        "required": ["value"],
    }
    props = {name: entry for name in fields}
    if "doc_type" in props:
        props["doc_type"] = {
            **entry,
            "properties": {
                "value": {"type": "string", "enum": list(DOC_TYPES)},
                "quote": {"type": "string"},
            },
        }
    return {"type": "object", "properties": props}


def excerpt(text: str) -> str:
    """The first two pages or the first 6,000 characters, whichever is shorter."""
    first_pages = PAGE_BREAK.join(text.split(PAGE_BREAK)[:MAX_PAGES])
    return first_pages[:MAX_CHARS]


def user_prompt(request: DetectRequest) -> str:
    return (
        f"File name: {request.file_name}\nFields wanted: {', '.join(request.fields)}\n\n"
        f"Text:\n{request.text}"
    )


def _entry(raw: Any) -> tuple[str, str] | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("value"), str):
        return None
    value = collapse(raw["value"])
    quote = raw.get("quote")
    if not value or len(value) > MAX_VALUE_CHARS:
        return None
    return value, quote if isinstance(quote, str) else ""


def _contains(quote: str, value: str) -> bool:
    return collapse(tr_lower(value)) in collapse(tr_lower(quote))


def validate(answer: dict[str, Any], text: str, wanted: tuple[str, ...]) -> Suggestions:
    """The fields of `answer` that hold up against `text`. A `doc_type` without a quote that
    occurs in the text is kept without evidence (the UI warns); any other field is dropped."""
    out: Suggestions = {}
    for name in wanted:
        if name not in FIELDS or (entry := _entry(answer.get(name))) is None:
            continue
        value, quote = entry
        evidence = locate(text, quote)
        if name == "doc_type":
            if value in DOC_TYPES:
                out[name] = Suggestion(value, "llm", evidence)
            continue
        if evidence is None:
            continue
        if name == "doc_date":
            try:
                date.fromisoformat(value)
            except ValueError:
                continue
            if parse_date(quote)[0] != value:
                continue
        elif name in ("official_ref", "issuer") and not _contains(quote, value):
            continue
        out[name] = Suggestion(value, "llm", evidence)
    return out
