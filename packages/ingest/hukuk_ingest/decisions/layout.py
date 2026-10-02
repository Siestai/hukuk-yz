"""Layout detection from markers in the text, never from the issue number. Issue ranges in the
spec are only an expectation used by the QA report."""

import re
from enum import StrEnum

from hukuk_ingest.decisions.clean import FOREIGN_TITLES, JournalText


class Layout(StrEnum):
    ERA1_SUMMARY_FIRST = "era1_summary_first"
    ERA2_CLASSIC = "era2_classic"
    ERA3_TWO_COLUMN = "era3_two_column"
    ERA4_NEW_TEMPLATE = "era4_new_template"
    FOREIGN_ARTICLE = "foreign_article"
    UNKNOWN = "unknown"


# Summary marker: "ÖZÜ:" (era 1), "ÖZETİ:" / "ÖZETİ " (later eras), at line start.
SUMMARY_RE = re.compile(r"^[ \t]*(?:ÖZETİ|ÖZÜ|ÖZET|Özeti|Özü)\b", re.MULTILINE)
# Labels of the decision block, at line start. Variants seen: "ESAS NO:", "Esas No.", "Esas
# Sayısı:", "E.2001/12345", "Başvuru No2001/1234", "Baş.V. No.", "YD. İtiraz No:", "Karar
# Tarihi:", "T.09.10.2007".
LABEL_RE = re.compile(
    r"^[ \t]*(?:"
    r"(?P<esas>ESAS|Esas)[ \t]*(?:NO|No|Sayısı)\b\.?"
    r"|(?P<karar>KARAR|Karar)[ \t]*(?:NO|No|Sayısı)\b\.?"
    r"|(?P<basvuru>(?:Başvuru|BAŞVURU|Baş\.(?:V\.)?|YD\.[ \t]*İtiraz)[ \t]*(?:No|NO))\.?"
    r"|(?P<tarih>(?:KARAR[ \t]+|Karar[ \t]+)?(?:TARİHİ|TARİH|Tarihi|Tarih)\b"
    r"|Karar[ \t]+T\.|T\.(?=\d))"
    r"|(?P<e>E\.)(?=[ \t]*\d)|(?P<k>K\.)(?=[ \t]*\d)"
    r")[ \t]*:?[ \t]*(?P<value>.*?)[ \t]*$",
    re.MULTILINE,
)
# OCR variants of the labels above, seen in the archive (eras 1-2 and 4); every one is listed so
# the set stays reviewable. Tried only after LABEL_RE fails, only while the header scan is already
# running (`fields._scan_meta`), never to find the start of a header, so a body line cannot match:
#   KARAR N0:   (zero for O)          KARAR NO0:  (stray zero)       KARAR:  (NO lost)
#   Karr No.    (letter lost)         TARİH... with the dotted İ misread: TARIHI, TARTHi, Tar;h;
#   Karar Tç28/3/2024 ("Tarihi" read as "Tç", no separator)
# The value must be empty or start with a digit, so prose cannot become a value.
OCR_LABEL_RE = re.compile(
    r"^[ \t]*(?:"
    r"(?P<karar>(?:KARAR|Karar)[ \t]*N[O0]{1,2}\b\.?|KARAR[ \t]*(?=:)|Karr[ \t]*No\b\.?)"
    r"|(?P<tarih>(?:TAR|Tar)[İITi;][Hh][İIi;]?(?=[ \t]*:?[ \t]*(?:\d|$))"
    r"|Karar[ \t]+T[çc](?=[ \t]*\d))"
    r")[ \t]*:?[ \t]*(?=\d|$)(?P<value>.*?)[ \t]*$",
    re.MULTILINE,
)
# Era 4: the new Yargıtay template numbers its sections with roman numerals ("I. DAVA",
# "V. GEREKÇE", "VI. KARAR"), at line start.
_TEMPLATE_RE = re.compile(
    r"^[ \t]*(?:I\.[ \t]*DAVA|V\.[ \t]*GEREKÇE|VI\.[ \t]*KARAR)\b", re.MULTILINE
)
# Era 3: two-column extraction leaves the labels without values, one per line in a row:
# "Esas No.\nKarar No.\nTarihi:" (the values follow on separate lines in the same order).
_TWO_COLUMN_RE = re.compile(
    r"^[ \t]*(?:Esas No|Baş\. No|Başvuru No)\.?[ \t]*\n"
    r"[ \t]*(?:Karar No|Karar Tarihi)\.?:?[ \t]*\n",
    # Python's IGNORECASE folds i/I/İ/ı together (not Turkish-correct). Harmless here: the labels
    # are fixed words and a stray dotted/dotless variant should still match. Text that must tell
    # İ from I (court and chamber names) goes through `fields.tr_lower` / `tr_upper` instead.
    re.IGNORECASE | re.MULTILINE,
)


def detect_layout(journal: JournalText) -> Layout:
    text = journal.text
    if journal.header_title in FOREIGN_TITLES:
        return Layout.FOREIGN_ARTICLE
    if _TEMPLATE_RE.search(text):
        return Layout.ERA4_NEW_TEMPLATE
    if _TWO_COLUMN_RE.search(text):
        return Layout.ERA3_TWO_COLUMN
    label = LABEL_RE.search(text)
    if label is None:
        return Layout.UNKNOWN
    summary = SUMMARY_RE.search(text)
    if summary is not None and summary.start() < label.start():
        return Layout.ERA1_SUMMARY_FIRST
    return Layout.ERA2_CLASSIC
