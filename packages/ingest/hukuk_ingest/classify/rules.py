"""Rules that read the type and the reference fields of a document from its text (task 13a).

Pure functions of the extracted text: no I/O, no model. Each rule returns the suggestions it can
support with a quote, and nothing else; a field the text does not show is left out (md. 25).
Order matters in `classify`: the most specific header first."""

import re

from hukuk_ingest.classify.evidence import Suggestion, Suggestions, collapse, span_evidence
from hukuk_ingest.decisions.clean import clean_journal
from hukuk_ingest.decisions.fields import DecisionFields, extract_fields, parse_date, tr_upper
from hukuk_ingest.decisions.layout import LABEL_RE, detect_layout
from hukuk_ingest.statutes.split import parse_header

_HEAD_CHARS = 3000
_DATE = r"(?<![\w.-])(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})(?!\d)"
_NUMBER_RE = re.compile(r"Kanun Numarası\s*:\s*(\d+)")
_KABUL_RE = re.compile(r"Kabul Tarihi\s*:\s*\d{1,2}/\d{1,2}/\d{4}")
_RG_LINE_RE = re.compile(
    r"(?:Resmî Gazete|R\.Gazete)\s*:\s*Tarih\s*:\s*\d{1,2}/\d{1,2}/\d{4}\s+Sayı\s*:\s*\d+"
)
# "Resmi Gazete Tarihi: 18/02/2017" and "Resmi Gazete No: 29983" (or "Sayısı"), either first,
# the value possibly on the next line.
_RG_DATE_RE = re.compile(
    r"Resm[iî]\s+Gazete(?:\s+Tarih[iı]?)?\s*(?:/\s*Say[ıi]s[ıi]\s*)?:?\s*" + _DATE
)
_RG_NO_RE = re.compile(r"Resm[iî]\s+Gazete\s+(?:No|Say[ıi]s[ıi]?)\s*[.:]?\s*(\d{4,6})")
_TITLE_END_RE = re.compile(
    r"^\s*(?:MADDE\b|Madde\b|BİRİNCİ\b|BIRINCI\b|BÖLÜM\b|AMAÇ\b|Amaç\b|Resm[iî]\s+Gazete|"
    r"\((?:Resm|R\.?G)|\d{1,2}[./]\d{1,2}[./]\d{4}\b|Yayımlandığı)",
)
_REG_WORD_RE = re.compile(r"(YÖNETMELİ[ĞK]|TEBLİĞ)")
_RG_LEAD_RE = re.compile(r"^\s*Resm[iî]\s+Gazete\b")
# "GENELGE", "GENELGE 2024/5", "2013/11 GENELGE", "2024/12 SAYILI GENELGE", "... HAKKINDA GENELGE":
# a short line in capitals that has the word, with or without the number beside it. Mixed case
# ("2025/15 sayılı Genelge") is a reference to another circular and does not count.
_GENELGE_RE = re.compile(r"^[^\n]{0,100}\bGENELGE\b[^\n]{0,40}$", re.M)
_YEAR_NO_RE = re.compile(r"(?<!\d)(\d{4})[ \t]*[/-][ \t]*(\d{1,3})(?!\d)")
_SAYI_RE = re.compile(r"^[ \t]*Sayı[ \t]*:[ \t]*(?P<ref>\S[^\n]*?)[ \t]*$", re.M)
_KONU_RE = re.compile(r"^[ \t]*Konu[ \t]*:[ \t]*(?P<first>[^\n]*)\n?", re.M)
_ISSUER_RE = re.compile(
    r"KURUMU|BAKANLI[ĞG]I|BAŞKANLI[ĞG]I|MÜDÜRLÜ[ĞG]Ü|MAHKEMES[İI]|YARGITAY", re.I
)
_SHEET_TYPES = frozenset({"xlsx_xlsm", "xls"})
_COURT_NAMES = {
    "yargitay": "Yargıtay",
    "danistay": "Danıştay",
    "aym": "Anayasa Mahkemesi",
    "bam": "Bölge Adliye Mahkemesi",
    "bim": "Bölge İdare Mahkemesi",
}


def _iso(raw: str) -> str | None:
    return parse_date(raw)[0]


def _lines(text: str, count: int) -> list[tuple[int, str]]:
    """The first `count` non-empty lines with their offsets."""
    out: list[tuple[int, str]] = []
    offset = 0
    for line in text.split("\n"):
        if line.strip():
            out.append((offset, line))
            if len(out) == count:
                break
        offset += len(line) + 1
    return out


def _issuer(text: str) -> Suggestion | None:
    """The first of the opening lines that names an institution."""
    for offset, line in _lines(text, 8):
        if _ISSUER_RE.search(tr_upper(line)) and 6 <= len(line.strip()) <= 120:
            start = offset + len(line) - len(line.lstrip())
            return Suggestion(
                collapse(line), "rule", span_evidence(text, start, offset + len(line.rstrip()))
            )
    return None


def kanun(text: str) -> Suggestions:
    """The mevzuat.gov.tr header: "Kanun Numarası", "Kabul Tarihi", "Resmî Gazete: Tarih Sayı"."""
    number, _, kabul, rg_date, _ = parse_header(text)
    head = text[:_HEAD_CHARS]
    found = _NUMBER_RE.search(head)
    if number is None or found is None or (kabul is None and rg_date is None):
        return {}
    out: Suggestions = {
        "doc_type": Suggestion("kanun", "rule", span_evidence(text, found.start(), found.end())),
        "official_ref": Suggestion(number, "rule", span_evidence(text, found.start(), found.end())),
    }
    date_match = _RG_LINE_RE.search(head) if rg_date else _KABUL_RE.search(head)
    chosen = rg_date or kabul
    if date_match is not None and chosen is not None:
        out["doc_date"] = Suggestion(
            chosen.isoformat(), "rule", span_evidence(text, date_match.start(), date_match.end())
        )
    title = _kanun_title(text, found.start())
    if title is not None:
        out["title"] = title
    return out


def _kanun_title(text: str, number_at: int) -> Suggestion | None:
    """The heading lines above the number, up to the parenthesised list of old laws."""
    lines = [(o, ln) for o, ln in _lines(text[:number_at], 6) if not ln.strip().startswith("(")]
    first = next(iter(lines), None)
    if first is None:
        return None
    offset, line = first
    return Suggestion(
        collapse(line), "rule", span_evidence(text, offset, offset + len(line.rstrip()))
    )


def regulation(text: str) -> Suggestions:
    """A yönetmelik or tebliğ: the type word ends the heading above the first article."""
    heading: list[tuple[int, str]] = []
    for offset, line in _lines(text, 12):
        if not heading and _RG_LEAD_RE.match(line):  # the Resmi Gazete line may come first
            continue
        if _TITLE_END_RE.match(line):
            break
        heading.append((offset, line))
    kind = None
    for _offset, line in reversed(heading):
        words = _REG_WORD_RE.findall(tr_upper(line))
        if words:
            kind = "yonetmelik" if words[-1].startswith("YÖNETMELİ") else "teblig"
            break
    if kind is None or not heading:
        return {}
    first_at, first = heading[0]
    last_at, last = heading[-1]
    title_span = span_evidence(text, first_at, last_at + len(last.rstrip()))
    out: Suggestions = {
        "doc_type": Suggestion(kind, "rule", title_span),
        "title": Suggestion(collapse(" ".join(ln for _, ln in heading)), "rule", title_span),
    }
    head = text[:_HEAD_CHARS]
    if (m := _RG_DATE_RE.search(head)) and (iso := _iso(m.group(1))):
        out["doc_date"] = Suggestion(iso, "rule", span_evidence(text, m.start(), m.end()))
    if m := _RG_NO_RE.search(head):
        out["official_ref"] = Suggestion(
            f"RG {m.group(1)}", "rule", span_evidence(text, m.start(), m.end())
        )
    return out


def _date_after(text: str, start: int) -> Suggestion | None:
    """The first date within the lines after `start`: the date of an SGK letter sits at the end
    of the "Sayı" line or, in older ones, after the "Konu" line."""
    window = text[start : start + 400]
    if m := re.search(_DATE, window):
        if iso := _iso(m.group(1)):
            return Suggestion(iso, "rule", span_evidence(text, start + m.start(), start + m.end()))
    return None


def _konu(text: str) -> Suggestion | None:
    m = _KONU_RE.search(text[:_HEAD_CHARS])
    if m is None:
        return None
    end = m.end()
    parts = [m.group("first").strip()]
    # The subject wraps over the lines that follow, up to the heading or the addressee.
    for line in text[end:_HEAD_CHARS].split("\n")[:3]:
        stripped = line.strip()
        if (
            not stripped
            or stripped.isupper()
            or re.match(r"(?:Sayı|İlgi)\b", stripped)
            or re.fullmatch(_DATE, stripped)
        ):
            break
        parts.append(stripped)
        end += len(line) + 1
    value = collapse(" ".join(parts))
    return (
        Suggestion(value, "rule", span_evidence(text, m.start(), m.start() + (end - m.start())))
        if value
        else None
    )


def _circular_number(text: str, heading: re.Match[str]) -> tuple[str, tuple[int, int]] | None:
    """Year/number on the heading line, else on the lines just above or below it."""
    lines = text[: _HEAD_CHARS + 200]
    around_start = max(lines.rfind("\n", 0, max(heading.start() - 1, 0)), 0)
    below_end = lines.find("\n", min(heading.end() + 1, len(lines)))
    below_end = len(lines) if below_end < 0 else below_end
    for start, end in (
        (heading.start(), heading.end()),
        (around_start, heading.start()),
        (heading.end(), below_end),
    ):
        if m := _YEAR_NO_RE.search(lines, start, end):
            return f"{m.group(1)}/{m.group(2)}", (
                min(m.start(), heading.start()),
                max(m.end(), heading.end()),
            )
    return None


def genelge(text: str) -> Suggestions:
    """ "GENELGE" in capitals in a short line of the opening lines, with the year/number beside
    or next to it; the "Sayı" line gives the date."""
    head = text[:_HEAD_CHARS]
    heading = _GENELGE_RE.search(head)
    if heading is None:
        return {}
    out: Suggestions = {
        "doc_type": Suggestion(
            "genelge", "rule", span_evidence(text, heading.start(), heading.end())
        )
    }
    if found := _circular_number(text, heading):
        number, span = found
        out["official_ref"] = Suggestion(number, "rule", span_evidence(text, *span))
    if sayi := _SAYI_RE.search(head):
        if date_s := _date_after(text, sayi.start()):
            out["doc_date"] = date_s
    if title := _konu(text):
        out["title"] = title
    if issuer := _issuer(text):
        out["issuer"] = issuer
    return out


def genel_yazi(text: str) -> Suggestions:
    """A letter with "Sayı:" and "Konu:" lines and no GENELGE heading."""
    head = text[:_HEAD_CHARS]
    sayi, konu = _SAYI_RE.search(head), _konu(text)
    if sayi is None or konu is None:
        return {}
    out: Suggestions = {
        "doc_type": Suggestion("genel_yazi", "rule", span_evidence(text, sayi.start(), sayi.end())),
        "official_ref": Suggestion(
            collapse(re.split(r"\s+(?=\d{1,2}[./]\d{1,2}[./]\d{4})", sayi.group("ref"))[0]),
            "rule",
            span_evidence(text, sayi.start(), sayi.end()),
        ),
        "title": konu,
    }
    if date_s := _date_after(text, sayi.start()):
        out["doc_date"] = date_s
    if issuer := _issuer(text):
        out["issuer"] = issuer
    return out


def _label_line(text: str, group: str) -> tuple[int, int] | None:
    for m in LABEL_RE.finditer(text[: _HEAD_CHARS * 2]):
        if m[group] and m["value"]:
            return m.start(), m.end()
    return None


def _case_no_span(text: str, case_no: str) -> tuple[int, int] | None:
    """Where `2013/10344` is printed in the head, whatever sits between year and number (the
    Hukuk Genel Kurulu prints `2024/10-389`)."""
    if "/" not in case_no:
        return None
    year, number = case_no.split("/", 1)
    m = re.search(
        rf"{year}\s*/\s*(?:\(?\d{{1,2}}\)?\s*-\s*)?{number}(?!\d)", text[: _HEAD_CHARS * 2]
    )
    return (m.start(), m.end()) if m else None


def _date_span(text: str, iso: str, after: int) -> tuple[int, int] | None:
    for m in re.finditer(_DATE, text[after : after + _HEAD_CHARS]):
        if parse_date(m.group(1))[0] == iso:
            return after + m.start(), after + m.end()
    return None


def karar(text: str) -> Suggestions:
    """A court decision, read by the parser of the decision archive: the court from the header
    block, the Esas / Karar numbers and the date from the lines that print them."""
    journal = clean_journal(text)
    fields: DecisionFields = extract_fields(journal, detect_layout(journal))
    if not fields.court or not (fields.esas_no or fields.karar_no):
        return {}
    esas = _label_line(text, "esas") or _case_no_span(text, fields.esas_no)
    kar = _label_line(text, "karar") or _case_no_span(text, fields.karar_no)
    spans = [s for s in (esas, kar) if s]
    if not spans:
        return {}
    ref_span = (min(s[0] for s in spans), max(s[1] for s in spans))
    out: Suggestions = {"doc_type": Suggestion("karar", "rule", span_evidence(text, *spans[0]))}
    refs = [f"{no} {kind}." for no, kind in ((fields.esas_no, "E"), (fields.karar_no, "K")) if no]
    out["official_ref"] = Suggestion(", ".join(refs), "rule", span_evidence(text, *ref_span))
    court = " ".join(p for p in (_COURT_NAMES.get(fields.court, fields.court), fields.chamber) if p)
    out["title"] = Suggestion(f"{court} {', '.join(refs)}", "rule", span_evidence(text, *ref_span))
    out["issuer"] = Suggestion(court, "rule", span_evidence(text, *spans[0]))
    if fields.decision_date:
        tarih = _label_line(text, "tarih") or _date_span(text, fields.decision_date, ref_span[0])
        if tarih:
            out["doc_date"] = Suggestion(fields.decision_date, "rule", span_evidence(text, *tarih))
    return out


def spreadsheet(detected_type: str) -> Suggestions:
    if detected_type not in _SHEET_TYPES:
        return {}
    return {
        "doc_type": Suggestion("hesap_tablosu", "rule", {"file_type": detected_type}),
    }
