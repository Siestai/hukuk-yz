"""Splits the text of one statute snapshot into header data and articles (task 11a).

Three footnote layouts occur in the snapshots and all are removed from the article text:

* rule style (2016 docx/doc, 2017 PDFs): a `––––` line, then `(1) ...` lines up to a blank line,
  a bare page number or the end of the page;
* numbered style (5510 2025 PDF): lines `47 Bu madde ...` at the bottom of a page, numbered
  continuously over the whole document, markers glued to the text (`kesilmesi47`);
* marker-line style (4857 PDF): a line `1` followed by the footnote text.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from hukuk_ingest.clean import clean_text
from hukuk_ingest.quality import PAGE_BREAK

_RULE_RE = re.compile(r"^\s*[–—―_-]{5,}\s*$")
_PAGE_NUMBER_RE = re.compile(r"^\s*\d{4,5}(?:-\d+)?\s*$")
_BRACKET_START_RE = re.compile(r"^\s*\((\d{1,3})\)\s*(.*)$")
_NUMBERED_START_RE = re.compile(r"^\s*(\d{1,3})(?:\s+(.*))?$")
_FOOTNOTE_OPEN_RE = re.compile(
    r"^\s*(?:\d{1,2}/\d{1,2}/\d{4}|\d{3,4}\s+sayılı|Bu\s|Anayasa\s+Mahkemesi)"
)
_FOOTNOTE_SKIP = 3  # numbers a page may skip before the sequence is considered broken
_HEAD_RE = re.compile(
    r"^\s*(?:(?P<ek>EK|Ek)\s+|(?P<gecici>GEÇİCİ|Geçici)\s+)?(?:MADDE|Madde)\s+"
    r"(?P<no>\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)(?:\s*[-–—]|(?=\s*\(\s*Mülga))\s*(?P<rest>.*)$"
)
_SECTION_RE = re.compile(
    r"^\s*(?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU|"
    r"ONBİRİNCİ|ONİKİNCİ|ONÜÇÜNCÜ)\s+(?:BÖLÜM|KISIM|KİTAP|AYIRIM)\s*(?:\(\d{1,3}\)|\d{0,3})\s*$",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"Kanun Numarası\s*:\s*(\d+)")
_KABUL_RE = re.compile(r"Kabul Tarihi\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})")
_RG_RE = re.compile(
    r"(?:Resmî Gazete|R\.Gazete)\s*:\s*Tarih\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+Sayı\s*:\s*(\d+)"
)
_TRAILER_RE = re.compile(
    r"(?:\d{1,2}/\d{1,2}/\d{4}\s+TARİHLİ\s+VE\s+\d+\s+SAYILI\s+KANUNA\s+)?İŞLENEMEYEN", re.I
)
_TERMINAL = ".;:,"
_HEADING_LINES = 4
_WRAPPED_TITLE = 75  # a section title line this long probably wraps onto the next line
_PARAGRAPH_START_RE = re.compile(r"^(?:[A-ZÇĞİÖŞÜ(•\-–]|\d+\)|[a-zçğıöşü]\))")
_GLUED_RUN_RE = re.compile(r"(?<=[^\W\d_])\d{1,6}(?=\s|$)|(?<=[)”’.,;:…])\d{1,6}(?=\s|$)")
_BRACKET_MARK_RE = r"(?<=\S)\s*\({n}\)"
# Wording of a footnote that stayed in the text: "... sayılı Kanunun 34 üncü maddesiyle ...
# değiştirilmiştir". Body text says "maddesi ile" about other things, never with these verbs.
_FOOTNOTE_LEAK_RE = re.compile(
    r"\d+\s+sayılı\s+(?:Kanunun|KHK)[^.]{0,80}maddesiyle[^.]{0,300}"
    r"(?:değiştirilmiş|eklenmiş|çıkarılmış|kanunlaşmıştır|hüküm altına)"
)
_REPEALED_RE = re.compile(r"^\(\s*(?:Mülga|İptal)\s*:[^()]*\)$", re.IGNORECASE)


@dataclass
class Footnote:
    no: int
    text: str
    page: int
    marker_found: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"no": self.no, "text": self.text, "page": self.page}


@dataclass
class Article:
    article_no: str
    ordinal: int
    heading: str
    text: str
    status: str = "in_force"  # in_force | repealed
    footnotes: list[Footnote] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_no": self.article_no,
            "ordinal": self.ordinal,
            "heading": self.heading,
            "text": self.text,
            "status": self.status,
            "footnotes": [f.to_dict() for f in self.footnotes],
            "warnings": self.warnings,
        }


@dataclass
class Snapshot:
    number: str | None
    title: str
    kabul_tarihi: date | None
    rg_tarihi: date | None
    rg_sayisi: str | None
    articles: list[Article]
    warnings: list[str] = field(default_factory=list)

    @property
    def footnote_count(self) -> int:
        return sum(len(a.footnotes) for a in self.articles)

    def header(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "kabul_tarihi": self.kabul_tarihi.isoformat() if self.kabul_tarihi else None,
            "rg_tarihi": self.rg_tarihi.isoformat() if self.rg_tarihi else None,
            "rg_sayisi": self.rg_sayisi,
        }


@dataclass
class _Line:
    text: str
    page: int


def _tr_date(d: str, m: str, y: str) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_header(text: str) -> tuple[str | None, str, date | None, date | None, str | None]:
    """(number, title, kabul date, RG date, RG number) from the header block."""
    head = text[:3000]
    number = _NUM_RE.search(head)
    kabul = _KABUL_RE.search(head)
    rg = _RG_RE.search(head)
    title_end = number.start() if number else 0
    title = " ".join(
        line.strip()
        for line in head[:title_end].splitlines()
        if line.strip() and not _PAGE_NUMBER_RE.match(line)
    )
    return (
        number.group(1) if number else None,
        title,
        _tr_date(*kabul.groups()) if kabul else None,
        _tr_date(*rg.groups()[:3]) if rg else None,
        rg.group(4) if rg else None,
    )


# --- footnote blocks ---------------------------------------------------------------------------


def _group_footnotes(lines: list[str], page: int, bracket: bool) -> list[Footnote]:
    """Footnote entries from the lines of a block (`(1) text`, or `47 text` / `1` + text)."""
    start_re = _BRACKET_START_RE if bracket else _NUMBERED_START_RE
    notes: list[Footnote] = []
    parts: list[str] = []
    no = 0
    for line in lines:
        m = start_re.match(line)
        if m and (bracket or not notes and not parts or int(m.group(1)) == no + 1):
            if parts:
                notes.append(Footnote(no, " ".join(p for p in parts if p), page))
            no, parts = int(m.group(1)), [(m.group(2) or "").strip()]
        elif parts:
            parts.append(line.strip())
    if parts:
        notes.append(Footnote(no, " ".join(p for p in parts if p), page))
    return notes


def _rule_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """(rule line, end exclusive) of every rule-style footnote block."""
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        nxt = next((x for x in lines[i + 1 :] if x.strip()), "")
        if not (_RULE_RE.match(lines[i]) and _BRACKET_START_RE.match(nxt)):
            i += 1
            continue
        end = next(
            (
                j
                for j in range(i + 1, len(lines))
                if not lines[j].strip() or _PAGE_NUMBER_RE.match(lines[j])
            ),
            len(lines),
        )
        blocks.append((i, end))
        i = end
    return blocks


def _numbered_block(lines: list[str], expected: int) -> tuple[int, int] | None:
    """(first line, number of the first footnote) of a numbered block at the page bottom: the
    last line that begins footnote `n` (n = expected ..) and whose text opens like a footnote."""
    for n in range(expected, expected + _FOOTNOTE_SKIP + 1):
        for i in range(len(lines) - 1, -1, -1):
            m = _NUMBERED_START_RE.match(lines[i])
            if not m or int(m.group(1)) != n:
                continue
            opening = (m.group(2) or "").strip() or next(
                (x.strip() for x in lines[i + 1 :] if x.strip()), ""
            )
            if _FOOTNOTE_OPEN_RE.match(opening):
                return i, n
    return None


def _extract_footnotes(
    text: str,
) -> tuple[list[_Line], list[tuple[Footnote, int, bool]], list[str]]:
    """Body lines with their page, and the footnotes with the body index where their block stood
    and whether they use the bracket style."""
    pages = text.split(PAGE_BREAK)
    paged = len(pages) > 1
    body: list[_Line] = []
    notes: list[tuple[Footnote, int, bool]] = []
    warnings: list[str] = []
    expected = 1
    rule_style = any(_rule_blocks(page.splitlines()) for page in pages)
    for p, page_text in enumerate(pages):
        lines = [line.rstrip() for line in page_text.splitlines()]
        filled = [i for i, x in enumerate(lines) if x.strip()]
        edges = {filled[0], filled[-1]} if filled else set()
        blocks = [(a, b, True) for a, b in _rule_blocks(lines)]
        if not blocks and not rule_style and (num := _numbered_block(lines, expected)) is not None:
            blocks = [(num[0], len(lines), False)]
            if num[1] != expected:
                warnings.append(f"footnote_sequence_gap:page {p + 1}:{expected}->{num[1]}")
        pos = 0
        for start, end, bracket in [*blocks, (len(lines), len(lines), True)]:
            for idx in range(pos, start):
                if _PAGE_NUMBER_RE.match(lines[idx]) and (not paged or idx in edges):
                    continue
                body.append(_Line(lines[idx], p + 1))
            if start < len(lines):
                raw = lines[start + 1 : end] if bracket else lines[start:end]
                fns = _group_footnotes([x for x in raw if x.strip()], p + 1, bracket)
                notes.extend((fn, len(body), bracket) for fn in fns)
                if not bracket and fns:
                    expected = fns[-1].no + 1
            pos = end
    return body, notes, warnings


# --- helpers for assembling articles -----------------------------------------------------------


def _decompose(digits: str, known: set[int]) -> list[int] | None:
    """`910` -> [9, 10] when 9 is a known footnote number: markers glued next to each other."""
    for k in range(1, len(digits) + 1):
        first = int(digits[:k])
        if first not in known:
            continue
        nums, pos, cur = [first], k, first
        while pos < len(digits):
            cur += 1
            if not digits.startswith(str(cur), pos):
                break
            nums.append(cur)
            pos += len(str(cur))
        if pos == len(digits):
            return nums
    return None


def _strip_markers(heading: str, known: set[int]) -> str:
    """Removes footnote markers glued to a heading: `... (1)` or `...zorunluluğu910`."""
    heading = re.sub(r"(?:\s*\(\d{1,3}\))+$", "", heading).strip()
    m = re.search(r"(?<=[^\W\d_])(\d+)$", heading)
    if m and _decompose(m.group(1), known):
        return heading[: m.start()].rstrip()
    return heading


def _has_marker(line: str, n: int, bracket: bool, known: set[int]) -> bool:
    if bracket:
        return bool(re.search(_BRACKET_MARK_RE.format(n=n), line))
    return any(n in (_decompose(m.group(0), known) or ()) for m in _GLUED_RUN_RE.finditer(line))


_NOTE_END_RE = re.compile(r"\((?:Ek|Değişik|Mülga|İptal|Yeniden|Aynen|Başlığı)[^()]*\)$")


def _ends_sentence(line: str) -> bool:
    """A line that closes a sentence or ends with an amendment note (a trailing glued footnote
    marker is ignored)."""
    s = re.sub(r"(?:\s*\(\d{1,3}\))+$", "", line.rstrip()).rstrip("0123456789").rstrip()
    return bool(s) and (s[-1] in ".;:”" or s.endswith(".)") or bool(_NOTE_END_RE.search(s)))


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    return (
        bool(s) and not _PAGE_NUMBER_RE.match(s) and not _HEAD_RE.match(s) and not _ends_sentence(s)
    )


def _heading_start(lines: list[str], first: int, idx: int) -> int:
    """Index where the heading ending before `idx` begins: the heading is the run of lines after
    the last line that closes a sentence (headings may wrap over several lines)."""
    start = idx
    while (
        start > first
        and idx - start < _HEADING_LINES
        and lines[start - 1].strip()
        and _is_heading_line(lines[start - 1])
    ):
        start -= 1
    while (
        start < idx and not lines[start].strip()[:1].isupper() and lines[start].strip()[:1] != "("
    ):
        start += 1
    return start


def _split_tail(lines: list[str], first: int) -> tuple[int, str, list[str]]:
    """Splits `lines[first:]` into (end of the article text, heading of the NEXT article,
    warnings). Section labels (`BİRİNCİ BÖLÜM` + its title line) drop out."""
    idx = len(lines)
    while idx > first and not lines[idx - 1].strip():
        idx -= 1
    sec = next(
        (j for j in range(idx - 1, max(idx - 12, first - 1), -1) if _SECTION_RE.match(lines[j])),
        None,
    )
    if sec is not None:
        while sec - 2 >= first and _SECTION_RE.match(lines[sec - 2]):  # KISIM + BÖLÜM chain
            sec -= 2
        last = max(j for j in range(sec, idx) if _SECTION_RE.match(lines[j]))
        after = [x for x in lines[last + 1 : idx] if x.strip()]
        n_title = 2 if len(after) >= 3 and len(after[0]) >= _WRAPPED_TITLE else 1
        rest = after[n_title:]
        warnings = ["section_title_guess"] if len(after) >= 3 else []
        return sec, " ".join(x.strip() for x in rest), warnings
    start = _heading_start(lines, first, idx)
    if start == idx:
        return idx, "", []
    prior = next((x.strip() for x in reversed(lines[first:start]) if x.strip()), "")
    suspect = bool(prior) and not _ends_sentence(prior) and prior[-1] != ")"
    heading = " ".join(x.strip() for x in lines[start:idx])
    return start, heading, ["heading_suspect"] if suspect else []


def _paragraphs(lines: list[str]) -> str:
    """Joins wrapped PDF lines; a leading tab (docx/doc) or a sentence end followed by a
    paragraph-start character begins a new paragraph."""
    paragraphs: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        new = not paragraphs or raw.startswith("\t")
        if not new:
            prev = paragraphs[-1]
            new = prev[-1] in _TERMINAL + ")" and bool(_PARAGRAPH_START_RE.match(line))
            if prev[-1] == "," and line[0].islower():
                new = False
        if new:
            paragraphs.append(line)
        else:
            paragraphs[-1] += " " + line
    return "\n".join(re.sub(r"[ \t]+", " ", p) for p in paragraphs)


def _article_no(m: re.Match[str]) -> str:
    no = re.sub(r"\s+", "", m.group("no")).upper()
    if m.group("ek"):
        return f"Ek {no}"
    if m.group("gecici"):
        return f"Geçici {no}"
    return no


def _is_repealed(text: str) -> bool:
    """A stub article: a single `(Mülga: ...)` note and no running text."""
    flat = " ".join(text.split())
    return bool(_REPEALED_RE.match(flat))


def _attach_footnotes(
    articles: list[Article],
    spans: list[tuple[int, int]],
    body: list[_Line],
    notes: list[tuple[Footnote, int, bool]],
    known: set[int],
) -> None:
    """Attaches each footnote to the article holding its marker; if no marker is found, to the
    article of the last body line before the block."""

    def owner(index: int) -> int | None:
        if not articles:
            return None
        for k, (start, text_end) in enumerate(spans):
            nxt = spans[k + 1][0] if k + 1 < len(spans) else len(body)
            if index < start:
                return k  # heading printed before the first head
            if start <= index < text_end:
                return k
            if text_end <= index < nxt:  # heading lines of the next article
                return min(k + 1, len(articles) - 1)
        return len(articles) - 1

    cursor = 0
    prev_at = 0
    for fn, at, bracket in notes:
        lo = prev_at if bracket else cursor
        hi = min(at, len(body))
        found = next(
            (
                i
                for i in range(lo, hi)
                if (bracket or body[i].page == fn.page)
                and _has_marker(body[i].text, fn.no, bracket, known)
            ),
            None,
        )
        if found is not None:
            cursor = found
        else:
            fn.marker_found = False
        k = owner(found if found is not None else max(hi - 1, 0))
        if k is not None:
            articles[k].footnotes.append(fn)
        if bracket:
            prev_at = max(prev_at, hi)


def _numbering_warnings(articles: list[Article]) -> list[str]:
    """Skipped, repeated or unordered article numbers; each is also noted on the article that
    follows the break. A repeated number gets the suffix ` (2)` so that numbers stay unique."""
    out: list[str] = []
    seen: dict[str, int] = {}
    last: dict[str, int] = {}
    for a in articles:
        if a.article_no in seen:
            seen[a.article_no] += 1
            original = a.article_no
            a.article_no = f"{original} ({seen[original]})"
            out.append(f"duplicate_article:{original}")
            a.warnings.append(f"duplicate_article:{original}")
            continue
        seen[a.article_no] = 1
        series, _, rest = a.article_no.rpartition(" ")
        series = series or "main"
        m = re.match(r"(\d+)(?:/([A-Z]))?$", rest or a.article_no)
        if not m:
            out.append(f"unparsed_article_no:{a.article_no}")
            a.warnings.append("unparsed_article_no")
            continue
        n = int(m.group(1))
        prev = last.get(series, 0)
        msg = ""
        if n > prev + 1:
            msg = f"number_skipped:{series}:{prev}->{n}"
        elif n < prev:
            msg = f"number_out_of_order:{series}:{prev}->{n}"
        if msg:
            out.append(msg)
            a.warnings.append(msg)
        last[series] = max(prev, n)
    return out


def split_statute(text: str) -> Snapshot:
    """Header data and articles of one snapshot text (PDF pages separated by form feeds)."""
    text = clean_text(text)
    trailer = _TRAILER_RE.search(text)
    extra_warnings: list[str] = []
    if trailer:  # provisions of amending laws that were never merged into the articles
        extra_warnings.append(f"trailer_ignored:{len(text) - trailer.start()} chars")
        text = text[: trailer.start()]
    number, title, kabul, rg_date, rg_no = parse_header(text)
    body, notes, warnings = _extract_footnotes(text)
    warnings += extra_warnings
    known = {fn.no for fn, _, _ in notes}

    heads = [(i, m) for i, line in enumerate(body) if (m := _HEAD_RE.match(line.text))]
    articles: list[Article] = []
    spans: list[tuple[int, int]] = []
    if heads:
        preamble = [x.text for x in body[: heads[0][0]]]
        _, heading, heading_warnings = _split_tail(preamble, 0)
    else:
        heading, heading_warnings = "", []
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(body)
        lines = [body[i].text[m.start("rest") :]] + [x.text for x in body[i + 1 : end]]
        last = k + 1 == len(heads)
        stop, next_heading, next_warnings = (len(lines), "", []) if last else _split_tail(lines, 1)
        articles.append(
            Article(
                article_no=_article_no(m),
                ordinal=k + 1,
                heading=_strip_markers(heading, known),
                text=_paragraphs(lines[:stop]),
                warnings=heading_warnings,
            )
        )
        spans.append((i, i + max(stop, 1)))
        heading, heading_warnings = next_heading, next_warnings
    _attach_footnotes(articles, spans, body, notes, known)
    for a in articles:
        a.status = "repealed" if _is_repealed(a.text) else "in_force"
        if any(not fn.marker_found for fn in a.footnotes):
            a.warnings.append("footnote_marker_not_found")
        if _FOOTNOTE_LEAK_RE.search(a.text):
            a.warnings.append("footnote_leak_suspect")
    return Snapshot(
        number, title, kabul, rg_date, rg_no, articles, warnings + _numbering_warnings(articles)
    )
