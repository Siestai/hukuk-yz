"""Journal-specific cleanup of the cached `.clean.txt`; source-independent cleanup lives in
`hukuk_ingest.clean`. Words glued together by the PDF extraction are deliberately not repaired:
the full text stays faithful to the source."""

import re
from dataclasses import dataclass

# Page header on the first line of every journal page: the section title, optionally followed
# by "– Çalışma ve Toplum, YYYY/N" (issues 76-90 and 43; the dash part may wrap to the next
# line), then the journal page number alone on its line. The foreign-court sections (German
# federal courts, ECJ, ECtHR) carry their section title instead of "Yargıtay Kararları".
_PAGE_HEADER_RE = re.compile(
    r"[ \t]*(?P<title>Yargıtay Kararları|Alman ?Federal ?Mahkeme ?Karar(?:ları|ı)"
    r"|Federal Mahkeme Kararları|Avrupa İnsan Hakları Mahkemesi|Avrupa Adalet Divanı Kararı)[ \t]*"
    r"(?:\n?[ \t]*[–-][ \t]*Çalışma ve Toplum,[ \t]*(?P<year>\d{4})/(?P<no>\d+)[ \t]*)?\n"
    r"(?:[ \t]*(?P<page>\d{1,4})[ \t]*\n)?"
)
# Footer line of the foreign-court articles (issues 3-23): "Çalışma ve Toplum, 2007/3" alone on a
# line, usually below the page number. A citation inside a sentence has more text on its line.
_FOOTER_RE = re.compile(
    r"^(?:[ \t]*\d{1,4}[ \t]*\n)?[ \t]*Çalışma ve Toplum, \d{4}/\d[ \t]*\n", re.MULTILINE
)
# Court-system banner printed at the top of pages of e-signed UYAP documents (issues 36-37).
_ESIGN_RE = re.compile(
    r"[ \t]*Bu belge \d+ sayılı Yasa hükümlerine göre elektronik olarak imzalanmıştır\.[ \t]*\n"
)
# The last page of an article can end with the next page's number alone on its line.
_TRAILING_PAGE_NO_RE = re.compile(r"\n[ \t]*\d{1,4}[ \t]*\n?\Z")
# Labels of the decision block wrapped inside a word by the two-column extraction ("Esas \nNo.",
# "Kara\nr No.", "Tari\nhi:"); rejoined so that the label patterns of `layout` match.
_WRAPPED_LABELS = (
    (re.compile(r"^(Esas|Karar)[ \t]*\n[ \t]*(No\.)", re.MULTILINE), r"\1 \2"),
    (re.compile(r"^Kara[ \t]*\nr[ \t]+No\.", re.MULTILINE), "Karar No."),
    (re.compile(r"^Tari[ \t]*\nhi:", re.MULTILINE), "Tarihi:"),
)
# Wingdings / Symbol bullet glyphs (U+F06C, U+F0B7, U+F0A7, U+F02A) survive the text layer as
# private-use characters; U+F020 is the matching private-use space.
_PUA_BULLET_RE = re.compile("[]")
_PUA_SPACE_RE = re.compile("")
# U+FFFE is a noncharacter pdfium emits for a line-break hyphen inside a word
# ("ÖRNEK￾KELİME"); dropping it restores the word.
_NONCHAR_RE = re.compile("￾")
# OCR turned "İ" into "Î" in the all-caps abbreviation TİS; the corpus has no genuine Î.
_OCR_I_RE = re.compile(r"(?<=[A-ZÇĞİÖŞÜ])Î(?=[A-ZÇĞİÖŞÜ])")
# A lone lowercase word on its own line between two running lines is a justification residue
# ("...hukuka uygun\nbile\n- devam"): glue it to the previous line.
_LONE_WORD_RE = re.compile(r"(?<=[^\n]{30}[^\n.:;!?\s])[ \t]*\n(?=[a-zçğıöşü]+[ \t]*\n[^\n])")
# Section titles of the foreign-court articles (translated German, ECJ and ECtHR decisions).
FOREIGN_TITLES = frozenset(
    {
        "Alman Federal Mahkeme Kararları",
        "Federal Mahkeme Kararları",
        "Avrupa İnsan Hakları Mahkemesi",
        "Avrupa Adalet Divanı Kararı",
    }
)


@dataclass(frozen=True)
class JournalText:
    text: str
    header_title: str | None
    journal_year: int | None
    journal_no: int | None
    journal_page: int | None


def _canonical_title(title: str) -> str:
    """ "AlmanFederalMahkemeKararları" and "Alman Federal Mahkeme Kararı" are one section."""
    if title.startswith("Alman"):
        return "Alman Federal Mahkeme Kararları"
    return title


def clean_journal(text: str) -> JournalText:
    """Strip page headers, journal page numbers and glyph noise; pages are joined by newlines."""
    pages: list[str] = []
    title: str | None = None
    year = no = page = None
    for i, raw in enumerate(text.split("\f")):
        if m := _PAGE_HEADER_RE.match(raw):
            if i == 0:
                title = _canonical_title(m["title"])
                page = int(m["page"]) if m["page"] else None
            if year is None and m["year"]:
                year, no = int(m["year"]), int(m["no"])
            raw = raw[m.end() :]
        pages.append(_ESIGN_RE.sub("", raw))
    body = _FOOTER_RE.sub("", "\n".join(pages))
    body = _TRAILING_PAGE_NO_RE.sub("", body)
    body = _PUA_BULLET_RE.sub("•", body)
    body = _PUA_SPACE_RE.sub(" ", body)
    body = _NONCHAR_RE.sub("", body)
    body = _OCR_I_RE.sub("İ", body)
    for pattern, replacement in _WRAPPED_LABELS:
        body = pattern.sub(replacement, body)
    body = _LONE_WORD_RE.sub(" ", body)
    return JournalText(body, title, year, no, page)
