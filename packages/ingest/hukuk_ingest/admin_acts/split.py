"""Split the text of a genelge into its numbered sections (handoff 2026-11-22, A3).

A genelge is numbered with dotted headings ("2.6.2.5- ...", "1.1. ..."); a long one restarts the
numbering in every KISIM / BÖLÜM. A section is the text from its heading up to the next heading
of any depth, so a parent holds only its own opening text and names its `children`. The section
number of a genelge with parts carries them: "K2-B3-2.1.1" is 2.1.1 of the third bölüm of the
second kısım, "K4-B1" the opening text of a bölüm, "Giriş" the text before the first heading.

Nothing is rewritten: the text of a section is its lines as extracted, without the page
furniture (letterhead, page numbers) and the blank lines. A line is a heading only when its
number continues the numbering (child, next sibling, next sibling of an ancestor); a top-level
number must also stand in the table of contents with the same title, so a numbered list inside
a section ("3- ...") is not a heading.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from hukuk_ingest.quality import MIN_CHARS_PER_PAGE, PAGE_BREAK

INTRO = "Giriş"
# Lines looked at on each side of a page for letterhead and footer lines.
_HEAD_LINES, _TAIL_LINES = 12, 3
_MAX_SKIP = 2  # headings that may be missing before one that is still taken as a heading
_TOC_GAP = 60  # lines without a dot leader after which the table of contents is over
_MASTHEAD_LINES = 40  # lines after the table of contents searched for number and subject
_MIN_TITLE = 3  # letters a heading and its table-of-contents entry must share

_HEADING_RE = re.compile(
    r"^(\d{1,2}(?:\.\d{1,2})*)(?:\s*[-–]\s*|\.\s+|\.(?=[^\d\s])|\s+(?=[A-ZÇĞİÖŞÜ]))(\S.*)$"
)
_LEADER_RE = re.compile(r"\.{4,}\s*\d+$")
_TOC_PAGE_RE = re.compile(r"[.\s]+\d+$")
_PAGE_NO_RE = re.compile(r"^(?:\d{1,4}|[ivxlc]{1,7})$")
_ORDINALS = (
    "BİRİNCİ İKİNCİ ÜÇÜNCÜ DÖRDÜNCÜ BEŞİNCİ ALTINCI YEDİNCİ SEKİZİNCİ DOKUZUNCU ONUNCU "
    "ONBİRİNCİ ONİKİNCİ ONÜÇÜNCÜ ONDÖRDÜNCÜ ONBEŞİNCİ ONALTINCI ONYEDİNCİ ONSEKİZİNCİ "
    "ONDOKUZUNCU"
).split()
_PART_RE = re.compile(rf"^(ON ?)?({'|'.join(_ORDINALS[:10])})\s+(KISIM|BÖLÜM)$")
_CLOSING_RE = re.compile(r"^(?:Bilgi|Bilgilerinizi|Gereğini)\b.*\brica ederim\.?$")
_REF_RE = re.compile(r"^(\d{4})\s*/\s*(\d+)$")
_NUMBER_RE = re.compile(r"^(?:Sayı|Sayi)\s*:.*?(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")
_SUBJECT_RE = re.compile(r"^Konu\s*:\s*(\S.*)$")
_NOTE_RE = re.compile(
    r"\((Değişik|Mülga|Ek)\s*[,:]\s*(\d{1,2})/(\d{1,2})/(\d{4})\s+tarihli\s+ve\s+(\d{4}/\d+)\s+sayılı"
)
_ANY_NOTE_RE = re.compile(r"\((?:Değişik|Mülga|Ek)\s*[,:]")
_INCORPORATED_RE = re.compile(
    r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+tarihli\s+ve\s+(\d{4}/\d+)\s+sayılı$"
)
_REPEALED_RE = re.compile(r"^\(Mülga\s*[,:][^)]*\)$")
_NOTE_KINDS = {"Değişik": "amended", "Mülga": "repealed", "Ek": "added"}

Number = tuple[int, ...]


@dataclass
class Section:
    section_no: str
    ordinal: int
    heading: str
    lines: list[str]
    pages: list[int]  # first and last page (1-based) of the file
    children: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class Split:
    ref: str | None  # "2020/8", as the document names itself
    issue_date: date | None
    subject: str | None
    incorporated: list[dict[str, str]]  # amending genelges listed on the cover
    sections: list[Section]
    toc_entries: int
    toc_unmatched: list[str]  # listed in the table of contents, not found in the body
    pages: int
    pages_without_text: list[int]  # inside the body
    annex_pages: list[int] | None  # first and last page after the closing; not split
    warnings: list[str]


@dataclass
class _Line:
    text: str
    page: int


def _squash(line: str) -> str:
    return "".join(line.split())


def _page_lines(text: str) -> list[list[str]]:
    """The non-blank lines of every page, without the lines that repeat on most pages at its top
    or bottom (compared without whitespace) and without the page numbers there."""
    pages = [[ln.strip() for ln in p.splitlines() if ln.strip()] for p in text.split(PAGE_BREAK)]
    seen: Counter[str] = Counter()
    for lines in pages:
        edge = lines[:_HEAD_LINES] + lines[max(_HEAD_LINES, len(lines) - _TAIL_LINES) :]
        seen.update({_squash(ln) for ln in edge})
    repeated = {key for key, count in seen.items() if count >= max(3, len(pages) // 2)}
    numbered = sum(1 for lines in pages if lines and _PAGE_NO_RE.match(lines[0]))
    strip_numbers = numbered >= max(3, len(pages) // 2)
    out = []
    for lines in pages:
        head = [ln for ln in lines[:_HEAD_LINES] if _squash(ln) not in repeated]
        body = lines[_HEAD_LINES : max(_HEAD_LINES, len(lines) - _TAIL_LINES)]
        tail = [
            ln
            for ln in lines[max(_HEAD_LINES, len(lines) - _TAIL_LINES) :]
            if _squash(ln) not in repeated
        ]
        kept = head + body + tail
        if strip_numbers and kept and _PAGE_NO_RE.match(kept[0]):
            kept = kept[1:]
        out.append(kept)
    return out


def _number(raw: str) -> Number:
    return tuple(int(part) for part in raw.split("."))


def _part(line: str) -> tuple[str, int] | None:
    """("KISIM" | "BÖLÜM", its number) for a part heading line."""
    if not (m := _PART_RE.match(line)):
        return None
    word = ("ON" if m.group(1) else "") + m.group(2)
    return m.group(3), _ORDINALS.index(word) + 1


def _prefix(kisim: int | None, bolum: int | None) -> str:
    return "-".join(p for p in (f"K{kisim}" if kisim else "", f"B{bolum}" if bolum else "") if p)


def _toc_span(lines: list[_Line]) -> tuple[int, int]:
    """The table of contents as [start, end) in `lines` ((0, 0): there is none): from the first
    entry with a dot leader (and the part heading above it) to the last line with one."""
    start = end = 0
    last = None
    for i, line in enumerate(lines):
        if _LEADER_RE.search(line.text):
            if last is None:
                start = next(
                    (j for j in range(max(0, i - 2), i + 1) if _HEADING_RE.match(lines[j].text)), i
                )
                # the part heading (and its title lines) above the first entry
                start = next(
                    (j for j in range(max(0, start - _HEAD_LINES), start) if _part(lines[j].text)),
                    start,
                )
            elif i - last > _TOC_GAP:
                break
            end, last = i + 1, i
    return start, end


def _fold(text: str) -> str:
    """Letters and digits only, lowercased the Turkish way: for comparing two titles."""
    lowered = text.replace("İ", "i").replace("I", "ı").lower()
    return "".join(c for c in lowered if c.isalnum())


def _toc_titles(lines: list[_Line]) -> dict[tuple[str, Number], str]:
    """The entries of the table of contents: the (first line of the) title, without the leader
    and the page number, by part and number."""
    titles: dict[tuple[str, Number], str] = {}
    kisim = bolum = None
    for line in lines:
        if part := _part(line.text):
            if part[0] == "KISIM":
                kisim, bolum = part[1], None
            else:
                bolum = part[1]
        elif m := _HEADING_RE.match(line.text):
            key = (_prefix(kisim, bolum), _number(m.group(1)))
            titles[key] = _fold(_TOC_PAGE_RE.sub("", m.group(2)))
    return titles


def _same_title(listed: str, heading: str) -> bool:
    """A heading and its entry in the table of contents start alike (either may be cut short by
    a line break)."""
    a, b = listed, _fold(heading)
    n = min(len(a), len(b))
    return n >= _MIN_TITLE and a[:n] == b[:n]


def _successors(current: Number) -> list[Number]:
    """The numbers that may follow `current`: its first child, its next sibling and the next
    sibling of every ancestor."""
    return [(*current, 1)] + [(*current[:k], current[k] + 1) for k in range(len(current))]


def _skipped(current: Number, number: Number) -> Number | None:
    """The expected number when `number` is a successor that leaves out up to `_MAX_SKIP`."""
    for expected in _successors(current):
        if (
            expected[:-1] == number[:-1]
            and len(expected) == len(number)
            and expected[-1] < number[-1] <= expected[-1] + _MAX_SKIP
        ):
            return expected
    return None


def _label(prefix: str, number: Number) -> str:
    dotted = ".".join(str(n) for n in number)
    return f"{prefix}-{dotted}" if prefix else dotted


def _is_masthead(line: str) -> bool:
    """The lines that open a genelge: "Sayı : ...", "Konu : ...", "GENELGE" and its number."""
    return bool(
        line == "GENELGE"
        or _REF_RE.match(line)
        or _NUMBER_RE.match(line)
        or _SUBJECT_RE.match(line)
    )


def _is_upper(line: str) -> bool:
    return any(c.isalpha() for c in line) and line == line.upper()


def _masthead(
    lines: list[_Line],
) -> tuple[str | None, date | None, str | None, list[dict[str, str]]]:
    """Ref, date and subject as the genelge states them, and the amending genelges its cover
    lists ("15/08/2019 tarihli ve 2019/16 sayılı"); None for what is not there."""
    ref = issue_date = subject = None
    incorporated: list[dict[str, str]] = []
    for line, following in zip(lines, lines[1:], strict=False):
        if (m := _NUMBER_RE.match(line.text)) and issue_date is None:
            issue_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        elif (m := _SUBJECT_RE.match(line.text)) and subject is None:
            subject = m.group(1)
        elif line.text == "GENELGE" and ref is None:
            if m := _REF_RE.match(following.text):
                ref = f"{m.group(1)}/{m.group(2)}"
        elif m := _INCORPORATED_RE.match(line.text):
            day = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            incorporated.append({"date": day.isoformat(), "ref": m.group(4)})
    return ref, issue_date, subject, incorporated


def _sections(
    body: list[_Line], toc: dict[tuple[str, Number], str]
) -> tuple[list[Section], set[tuple[str, Number]]]:
    """The sections of the body in order, and the (part, number) keys of the headings found."""
    sections: dict[str, Section] = {}
    found: set[tuple[str, Number]] = set()
    kisim = bolum = None
    current: Number = ()
    section: Section | None = None
    title_open = False  # the capital lines after a part heading are its title

    def start(section_no: str, heading: str, line: _Line) -> Section:
        new = Section(section_no, 0, heading, [], [line.page, line.page])
        sections[section_no] = new
        return new

    for line in body:
        if part := _part(line.text):
            if part[0] == "KISIM":
                kisim, bolum = part[1], None
            else:
                bolum = part[1]
            current = ()
            section = start(_prefix(kisim, bolum), "", line)
            title_open = True
        elif title_open and section is not None and _is_upper(line.text):
            section.heading = f"{section.heading} {line.text}".strip()
        else:
            title_open = False
            prefix = _prefix(kisim, bolum)
            if m := _HEADING_RE.match(line.text):
                number = _number(m.group(1))
                expected = None if number in _successors(current) else _skipped(current, number)
                continues = number in _successors(current) or expected is not None
                listed = (
                    len(number) > 1
                    or not toc
                    or _same_title(toc.get((prefix, number), ""), m.group(2))
                )
                if continues and listed:
                    current = number
                    found.add((prefix, number))
                    section = start(_label(prefix, number), m.group(2), line)
                    if expected is not None:
                        section.warnings.append(
                            f"number_skipped:{_label(prefix, expected)}->{section.section_no}"
                        )
                    parent = _label(prefix, number[:-1]) if len(number) > 1 else prefix
                    if parent in sections:
                        sections[parent].children.append(section.section_no)
                elif len(number) > 1 and section is not None:
                    # numbered like a heading but out of sequence: the text stays where it is
                    section.warnings.append(f"unplaced_heading:{_label(prefix, number)}")
            if section is None:
                if _is_masthead(line.text):
                    sections.pop(INTRO, None)  # the text starts after number, subject and ref
                    continue
                section_or_intro = sections.get(INTRO) or start(INTRO, INTRO, line)
            else:
                section_or_intro = section
            section_or_intro.lines.append(line.text)
            section_or_intro.pages[1] = line.page
            continue
        section.lines.append(line.text)
        section.pages[1] = line.page
    ordered = list(sections.values())
    for ordinal, s in enumerate(ordered):
        s.ordinal = ordinal
    return ordered, found


def split_act(text: str) -> Split:
    """`text`: the extracted text of the file, pages separated by a form feed."""
    pages = _page_lines(text)
    lines = [_Line(ln, no) for no, page in enumerate(pages, 1) for ln in page]
    toc_start, toc_end = _toc_span(lines)
    toc = _toc_titles(lines[toc_start:toc_end])
    ref, issue_date, subject, incorporated = _masthead(lines[: toc_end + _MASTHEAD_LINES])
    rest = lines[toc_end:]
    closing = next((i for i, ln in enumerate(rest) if _CLOSING_RE.match(ln.text)), None)
    body = rest if closing is None else rest[:closing]
    sections, found = _sections(body, toc)

    warnings: list[str] = []
    if closing is None and sections:
        sections[-1].warnings.append("closing_not_found")
        warnings.append("closing_not_found")
    first_page = body[0].page if body else 0
    last_page = body[-1].page if body else 0
    empty = [
        no
        for no, page in enumerate(pages, 1)
        if first_page <= no <= last_page and sum(len(ln) for ln in page) < MIN_CHARS_PER_PAGE
    ]
    for s in sections:
        s.warnings += [f"page_without_text:{no}" for no in empty if s.pages[0] <= no <= s.pages[1]]
    annex = closing is not None and rest[-1].page > rest[closing].page
    return Split(
        ref=ref,
        issue_date=issue_date,
        subject=subject,
        incorporated=incorporated,
        sections=sections,
        toc_entries=len(toc),
        toc_unmatched=sorted(_label(p, n) for p, n in toc.keys() - found),
        pages=len(pages),
        pages_without_text=empty,
        annex_pages=[rest[closing or 0].page + 1, len(pages)] if annex else None,
        warnings=warnings,
    )


def amendments(text: str) -> tuple[list[dict[str, str]], int]:
    """The amendment notes of a section ("(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı
    Genelge)") as kind, date and ref, and how many notes could not be read."""
    notes = [
        {
            "kind": _NOTE_KINDS[m.group(1)],
            "date": date(int(m.group(4)), int(m.group(3)), int(m.group(2))).isoformat(),
            "ref": m.group(5),
        }
        for m in _NOTE_RE.finditer(text)
    ]
    return notes, len(_ANY_NOTE_RE.findall(text)) - len(notes)


def is_repealed(section: Section) -> bool:
    """The whole section is a repeal note: its heading line is the note and nothing follows."""
    return len(section.lines) == 1 and bool(_REPEALED_RE.match(section.heading))
