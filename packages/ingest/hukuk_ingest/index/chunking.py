"""Chunking of decisions and statute articles for the search index (task 14, data-model.md §8).

Pure functions: text in, `ChunkDraft`s out. Every body chunk is a verbatim slice of the source
text (`text == source[char_start:char_end]`), so a quotation can be checked against the record.

Sizes are counted in words; a Turkish word is about 2.2 model tokens (`TOKENS_PER_WORD`).
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

TOKENS_PER_WORD = 2.2
# A decision of at most this many words is one chunk (data-model.md §8).
SINGLE_CHUNK_WORDS = 500
# Window of a long decision or section: about 440 tokens, with a light overlap.
WINDOW_WORDS = 200
OVERLAP_WORDS = 30
# A section of the new Yargıtay template stays whole up to this size; longer ones are windowed.
SECTION_MAX_WORDS = 300
# A shorter section is joined to the next one: a heading and two lines make a poor chunk.
SECTION_MIN_WORDS = 40
# An article (version) of at most this many words is one chunk; longer ones split by paragraph.
ARTICLE_SINGLE_WORDS = 350
ARTICLE_WINDOW_WORDS = 250

# "I. DAVA", "V. GEREKÇE", "VI. KARAR": a roman numeral and an upper-case heading on its own line.
_SECTION_RE = re.compile(r"^[ \t]*([IVX]{1,5}\.[ \t]+[^\n]{2,80}?)[ \t]*$", re.MULTILINE)
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")
_LINE_RE = re.compile(r"\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+")
_WORD_RE = re.compile(r"\S+")

BODY = "body"
EDITORIAL_SUMMARY = "editorial_summary"


@dataclass(frozen=True)
class ChunkDraft:
    kind: str
    ordinal: int
    char_start: int
    char_end: int
    text: str
    header: str
    section: str | None = None


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def estimate_tokens(text: str) -> int:
    return round(word_count(text) * TOKENS_PER_WORD)


def embedding_input(header: str, text: str) -> str:
    """What the model reads: the citation header and the text. The header is never displayed."""
    return f"{header}\n\n{text}" if header else text


def content_hash(header: str, text: str) -> str:
    """Changes when the embedding input does; a chunk with the same hash and model is not
    embedded again."""
    return hashlib.sha256(embedding_input(header, text).encode()).hexdigest()


def decision_header(
    ref: str | None, articles: Sequence[dict[str, Any]], keywords: Sequence[str]
) -> str:
    """ "Yargıtay 9. HD, E. 2017/1 K. 2018/2, 12.03.2018 · 4857/17,32 · Kıdem tazminatı": the
    reference, the statute articles cited (`related_articles`, data-model.md §5.2) and the
    keywords; a missing part is left out."""
    cited = [
        f"{a['statute']}/{','.join(str(n) for n in a.get('articles') or [])}".rstrip("/")
        for a in articles
        if a.get("statute")
    ]
    parts = [ref or "", " ".join(cited), ", ".join(keywords)]
    return " · ".join(p for p in parts if p)


def article_label(article_no: str) -> str:
    """ "m.18" for a numbered article; "Geçici 4" and "Ek 2" stand as they are."""
    return f"m.{article_no}" if article_no[:1].isdigit() else article_no


def statute_header(number: str, article_no: str, heading: str | None, valid_from: str) -> str:
    """ "4857 sayılı Kanun · m.18 · Feshin geçerli sebebe dayandırılması · yürürlük 2018-01-01"."""
    parts = [
        f"{number} sayılı Kanun",
        article_label(article_no),
        heading or "",
        f"yürürlük {valid_from}",
    ]
    return " · ".join(p for p in parts if p)


Span = tuple[int, int]


def _trim(text: str, start: int, end: int) -> Span | None:
    chunk = text[start:end]
    stripped = chunk.strip()
    if not stripped:
        return None
    offset = len(chunk) - len(chunk.lstrip())
    return start + offset, start + offset + len(stripped)


def _split(text: str, start: int, end: int, separator: re.Pattern[str]) -> list[Span]:
    spans: list[Span] = []
    position = start
    for match in separator.finditer(text, start, end):
        if span := _trim(text, position, match.start()):
            spans.append(span)
        position = match.end()
    if span := _trim(text, position, end):
        spans.append(span)
    return spans


def _atoms(text: str, start: int, end: int, paragraph: re.Pattern[str], window: int) -> list[Span]:
    """Paragraphs; a paragraph longer than a window is cut into sentences, and a sentence longer
    than a window into runs of words."""
    atoms: list[Span] = []
    for p_start, p_end in _split(text, start, end, paragraph):
        if word_count(text[p_start:p_end]) <= window:
            atoms.append((p_start, p_end))
            continue
        for s_start, s_end in _split(text, p_start, p_end, _SENTENCE_RE):
            if word_count(text[s_start:s_end]) <= window:
                atoms.append((s_start, s_end))
                continue
            words = [
                (s_start + m.start(), s_start + m.end())
                for m in _WORD_RE.finditer(text[s_start:s_end])
            ]
            for i in range(0, len(words), window):
                atoms.append((words[i][0], words[min(i + window, len(words)) - 1][1]))
    return atoms


def _windows(
    text: str, start: int, end: int, paragraph: re.Pattern[str], window: int, overlap: int
) -> list[Span]:
    """Greedy packing of whole atoms into windows of at most about `window` words; the next
    window starts with the trailing atoms of the last one that fit in `overlap` words."""
    windows: list[Span] = []
    current: list[tuple[Span, int]] = []
    size = 0
    for atom in _atoms(text, start, end, paragraph, window):
        words = word_count(text[atom[0] : atom[1]])
        if current and size + words > window:
            windows.append((current[0][0][0], current[-1][0][1]))
            tail: list[tuple[Span, int]] = []
            tail_size = 0
            for kept in reversed(current):
                if tail_size + kept[1] > overlap:
                    break
                tail.insert(0, kept)
                tail_size += kept[1]
            current, size = tail, tail_size
        current.append((atom, words))
        size += words
    if current:
        windows.append((current[0][0][0], current[-1][0][1]))
    return windows


def _sections(text: str) -> list[tuple[str | None, Span]]:
    """The sections of a decision in the new template (heading to the next heading; text before
    the first heading is a section without a name); empty unless there are two headings. Short
    sections are joined to the next one, a short last one to the previous."""
    headings = [(m.start(), m.group(1)) for m in _SECTION_RE.finditer(text)]
    headings = [h for h in headings if not any(c.islower() for c in h[1])]
    if len(headings) < 2:
        return []
    bounds = [h[0] for h in headings] + [len(text)]
    raw: list[tuple[str | None, int, int]] = [
        (name, bounds[i], bounds[i + 1]) for i, (_, name) in enumerate(headings)
    ]
    if headings[0][0] > 0 and text[: headings[0][0]].strip():
        raw.insert(0, (None, 0, headings[0][0]))
    merged: list[tuple[str | None, int, int]] = []
    carry: tuple[str | None, int, int] | None = None
    for name, start, end in raw:
        if carry is not None:
            name, start = carry[0], carry[1]
            carry = None
        if word_count(text[start:end]) < SECTION_MIN_WORDS:
            carry = (name, start, end)
            continue
        merged.append((name, start, end))
    if carry is not None:
        if merged:
            name, start, _ = merged[-1]
            merged[-1] = (name, start, carry[2])
        else:
            merged.append(carry)
    out: list[tuple[str | None, Span]] = []
    for name, start, end in merged:
        span = _trim(text, start, end)
        if span:
            out.append((name, span))
    return out


def chunk_decision(
    full_text: str, editorial_summary: str, header: str, *, body: bool = True
) -> list[ChunkDraft]:
    """The body chunks of a decision, then its editorial summary as one chunk of its own
    (data-model.md §8). `body=False` leaves the body out (a record whose `full_text` is not the
    court's own text). Ordinals count within a kind."""
    drafts: list[ChunkDraft] = []
    if body and full_text.strip():
        pieces: list[tuple[str | None, Span]] = []
        if word_count(full_text) <= SINGLE_CHUNK_WORDS:
            if span := _trim(full_text, 0, len(full_text)):
                pieces.append((None, span))
        else:
            sections = _sections(full_text)
            if sections:
                for name, (start, end) in sections:
                    if word_count(full_text[start:end]) <= SECTION_MAX_WORDS:
                        pieces.append((name, (start, end)))
                        continue
                    pieces.extend(
                        (name, w)
                        for w in _windows(
                            full_text, start, end, _BLANK_LINE_RE, WINDOW_WORDS, OVERLAP_WORDS
                        )
                    )
            else:
                pieces.extend(
                    (None, w)
                    for w in _windows(
                        full_text, 0, len(full_text), _BLANK_LINE_RE, WINDOW_WORDS, OVERLAP_WORDS
                    )
                )
        for ordinal, (name, (start, end)) in enumerate(pieces):
            chunk_header = f"{header} · {name}" if name else header
            drafts.append(
                ChunkDraft(BODY, ordinal, start, end, full_text[start:end], chunk_header, name)
            )
    if span := _trim(editorial_summary, 0, len(editorial_summary)):
        drafts.append(
            ChunkDraft(
                EDITORIAL_SUMMARY, 0, span[0], span[1], editorial_summary[span[0] : span[1]], header
            )
        )
    return drafts


def chunk_article(text: str, header: str) -> list[ChunkDraft]:
    """One chunk per article version; an article longer than `ARTICLE_SINGLE_WORDS` splits at
    paragraph (fıkra) breaks."""
    if word_count(text) <= ARTICLE_SINGLE_WORDS:
        span = _trim(text, 0, len(text))
        return (
            [ChunkDraft(BODY, 0, span[0], span[1], text[span[0] : span[1]], header)] if span else []
        )
    return [
        ChunkDraft(BODY, ordinal, start, end, text[start:end], header)
        for ordinal, (start, end) in enumerate(
            _windows(text, 0, len(text), _LINE_RE, ARTICLE_WINDOW_WORDS, 0)
        )
    ]
