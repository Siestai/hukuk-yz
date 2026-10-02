"""Field extraction for one cleaned decision text, named after `docs/data-model.md` §5.2.

The court comes from the header block (the court lines directly above the Esas/Karar labels),
never from free body text: bodies cite "Yargıtay 10. Hukuk Dairesince" and the "MAHKEMESİ :"
line of a Yargıtay decision names the lower court. Whatever cannot be extracted stays empty and
is reported by `qa`; nothing is guessed (md. 25)."""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from hukuk_ingest.decisions.clean import FOREIGN_TITLES, JournalText
from hukuk_ingest.decisions.layout import LABEL_RE, OCR_LABEL_RE, SUMMARY_RE, Layout

_TR_LOWER = str.maketrans({"İ": "i", "I": "ı"})
_TR_UPPER = str.maketrans({"i": "İ", "ı": "I"})


def tr_lower(s: str) -> str:
    return s.translate(_TR_LOWER).lower()


def tr_upper(s: str) -> str:
    return s.translate(_TR_UPPER).upper()


def _squash(s: str) -> str:
    """Upper-case without whitespace: robust to "Y A R G I T A Y" and wrapped court names."""
    return re.sub(r"\s+", "", tr_upper(s))


# --- Esas / Karar numbers -------------------------------------------------------------------

# "2010 / 37635", "2017/16188", HGK "2024/10-389" (10 = source chamber, 389 = sequence).
# Typos in the source are tolerated: "2001/(7)22-1234", "12001/18194", "2001/27016 E".
_CASE_NO_RE = re.compile(r"(\d{4})\s*/\s*(?:\(\d+\)\s*)?(?:(\d{1,2})\s*-\s*)?(\d{1,6})\b")


def normalize_case_no(raw: str) -> tuple[str, str] | None:
    """`YYYY/N` plus the HGK source chamber ('' when absent), or None."""
    m = _CASE_NO_RE.search(raw)
    if m is None:
        return None
    return f"{m[1]}/{m[3]}", m[2] or ""


# --- Dates ----------------------------------------------------------------------------------

_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}
# "07.06.2004", "7.6.2004", "07/06/2004", "18. 09. 2008", "21.05 .2013"
_NUMERIC_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})(?!\d)")
# "7 Haziran 2004"
_NAMED_DATE_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})\b")
# A date-shaped token that the strict pattern rejected: malformed year ("08/04/20219", "12.05.20").
_MALFORMED_DATE_RE = re.compile(r"(?<!\d)\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d+")


def parse_date(raw: str) -> tuple[str | None, bool]:
    """(ISO date, found_but_invalid). A date that does not exist (31.02.2004) or has a malformed
    year (08/04/20219) is invalid; the intended date is never guessed."""
    if m := _NUMERIC_DATE_RE.search(raw):
        day, month, year = int(m[1]), int(m[2]), int(m[3])
    elif (m := _NAMED_DATE_RE.search(raw)) and tr_lower(m[2]) in _MONTHS:
        day, month, year = int(m[1]), _MONTHS[tr_lower(m[2])], int(m[3])
    else:
        return None, _MALFORMED_DATE_RE.search(raw) is not None
    try:
        return date(year, month, day).isoformat(), False
    except ValueError:
        return None, True


# --- Court ----------------------------------------------------------------------------------

# Matched against the squashed upper-case line. Besides court names: the "T.C. / TÜRK MİLLETİ
# ADINA / YARGITAY İLAMI" banner and the "2001/1234 E., 2002/5678 K." line some decisions print
# between the chamber and the labels.
_COURT_LINE_RE = re.compile(
    r"^T\.?C\.?|YARG[İI]*TAY|ANAYASA|DA[İI]RE|[İI]RES[İI]|MAHKEME|KURUL|[İI]LAM|B[ÖO]LÜM|BÖLGE|ADL[İI]YE|B[İI]RLE[ŞS][İI]RME"
    r"|DANI[ŞS]TAY|HUKUK|CEZA|CUMHUR[İI]YET|M[İI]LLET|^\d+\.$|^\d{4}/\d+E\."
)
_CITY_RE = re.compile(r"^[A-ZÇĞİÖŞÜ]{3,25}$")
_MAX_COURT_LINES = 7
_MAX_UNLABELLED_SKIP = 2
# "9. HUKUK \nAİRESİ": the wrapped header loses the "D" of "DAİRESİ" in some extractions. `squashed`
# already joins the wrapped words, so only the optional "D" is needed.
_CHAMBER_RE = re.compile(r"(\d{1,2})\.?(HUKUK|CEZA)?D?A[İI]RE")
_ORDINAL_CHAMBERS = {
    "BİRİNCİ": 1,
    "İKİNCİ": 2,
    "ÜÇÜNCÜ": 3,
    "DÖRDÜNCÜ": 4,
    "BEŞİNCİ": 5,
    "ALTINCI": 6,
    "YEDİNCİ": 7,
    "SEKİZİNCİ": 8,
    "DOKUZUNCU": 9,
    "ONUNCU": 10,
}


@dataclass
class CourtInfo:
    court: str = ""
    court_level: str = ""
    chamber: str = ""
    decision_kind: str = "karar"
    jurisdiction: str = ""
    bam_region: str = ""


def _chamber(squashed: str, danistay: bool) -> str:
    if m := _CHAMBER_RE.search(squashed):
        if m[2] == "CEZA":
            return f"{m[1]}. CD"
        if m[2] == "HUKUK":
            return f"{m[1]}. HD"
        return f"{m[1]}. D" if danistay else ""
    for word, n in _ORDINAL_CHAMBERS.items():
        if word in squashed and "DA" in squashed:
            return f"{n}. D"
    return ""


def _region(lines: list[str]) -> str:
    """The city printed before "BÖLGE ... MAHKEMESİ" (its own line or the same line)."""
    for i, line in enumerate(lines):
        squashed = _squash(line)
        if "BÖLGE" not in squashed:
            continue
        before = re.split(r"B[ÖO]LGE", tr_upper(line))[0]
        before = re.sub(r"T\.?\s?C\.?", "", before).strip()
        if not before and i > 0 and _CITY_RE.match(tr_upper(lines[i - 1].strip())):
            before = lines[i - 1].strip()
        if before:
            return tr_upper(before)[0] + tr_lower(before)[1:]
    return ""


def classify_court(
    block: list[str], journal: JournalText, is_individual_application: bool
) -> CourtInfo:
    """Court of a decision from its header block; foreign sections from the journal section."""
    squashed = _squash(" ".join(block))
    head = _squash(" ".join(journal.text.split("\n")[:8]))
    info = CourtInfo()
    if journal.header_title in FOREIGN_TITLES or not block:
        title = journal.header_title or ""
        if "AVRUPAADALETD" in head or title.startswith("Avrupa Adalet"):
            info.court, info.court_level = "abad", "international"
        elif "AVRUPAİNSANHAKLARIMAHKEMES" in head or title.startswith("Avrupa İnsan"):
            info.court, info.court_level = "aihm", "international"
        elif journal.header_title in FOREIGN_TITLES:
            info.court, info.court_level = "foreign", "international"
        return info
    if "ANAYASAMAHKEMES" in squashed:
        info.court, info.court_level = "aym", "aym"
        info.decision_kind = "bireysel_basvuru" if is_individual_application else "norm_denetimi"
    elif "BİRLEŞTİRME" in squashed or "BIRLEŞTİRME" in squashed:
        info.court, info.court_level, info.decision_kind = "yargitay", "ibk", "ibk"
        info.jurisdiction = "adli"
    elif "DANIŞTAY" in squashed:
        info.court, info.jurisdiction = "danistay", "idari"
        info.court_level = "hgk_iddk" if "KURUL" in squashed else "daire"
        info.chamber = "" if "KURUL" in squashed else _chamber(squashed, danistay=True)
    elif "BÖLGEİDARE" in squashed:
        info.court, info.court_level, info.jurisdiction = "bim", "bam_bim", "idari"
        info.chamber = _chamber(squashed, danistay=True)
        info.bam_region = _region(block)
    elif "BÖLGEADLİYE" in squashed:
        info.court, info.court_level, info.jurisdiction = "bam", "bam_bim", "adli"
        info.chamber = _chamber(squashed, danistay=False)
        info.bam_region = _region(block)
    elif re.search(r"SULH|ASL[İI]YE|AĞIRCEZA|İŞMAHKEMES", squashed):
        info.court, info.court_level, info.jurisdiction = "ilk_derece", "ilk_derece", "adli"
    elif re.search(r"YARG[İI]*TAY", squashed):
        info.court, info.jurisdiction = "yargitay", "adli"
        if "GENELKURU" in squashed:
            info.court_level = "hgk_iddk"
        else:
            info.court_level = "daire"
            info.chamber = _chamber(squashed, danistay=False)
    return info


# --- Header block ---------------------------------------------------------------------------

# Standalone values of the two-column layout; the number form tolerates a leading slash or a
# trailing "E"/"K" ("/2001/8232", "2001/27016 E").
_NUMBER_VALUE_RE = re.compile(r"^[ \t:/]*\d{4,5}[ \t]*/[ \t]*[\d()\- \t]+(?:[EK]\.?)?[ \t]*$")
_DATE_VALUE_RE = re.compile(r"^[ \t:]*\d{1,2}[ \t]*[./-][ \t]*\d{1,2}[ \t]*[./-][ \t]*\d{4}[ \t]*$")
# Lines inside the label block that carry no field: Resmi Gazete refs, blank lines, and the
# "MAHKEMESİ :", "NO :", "DAVACI", "YARGITAY İLAMI" labels and ":value" lines of the 2004 issues,
# which sit between ESAS NO and TARİHİ.
# A bare "MAHKEMESİ" label ("MAHKEMESİ \n:\nAdana 2. İş Mahkemesi") is followed by its value on a
# line of its own, which `_scan_meta` skips too.
_ORIGIN_LABEL_RE = re.compile(r"^[ \t]*MAHKEMES[İI][ \t]*:?[ \t]*$")
_ORIGIN_START_RE = re.compile(r"^[ \t]*MAHKEMES[İI]\b")
_META_SKIP_RE = re.compile(
    r"^[ \t]*(?:RG\.|R:G\.|R\.G\.|MAHKEMES[İI]\b|NO[ \t]*:|DAVAC?LI|DAVACI|:|YARGITAY[ \t]+İLAMI|$)"
)
_RELATED_RE = re.compile(
    r"^[ \t.\d]*İlgili[ \t]+Kanun[ \t]*/?[ \t]*(?:Madde(?:si)?|md)?[ \t]*:?[ \t]*(?P<rest>.*)$"
)
_SUMMARY_LABEL_RE = re.compile(r"^[ \t]*(?:ÖZETİ|ÖZÜ|ÖZET|Özü)[ \t]*:?[ \t]*")

# Where the decision body starts. Strong markers first: the "DAVA" heading (typos "DAVA;",
# "Dava," included), a roman-numbered section ("I. DAVA", "I. BAŞVURU"), the "MAHKEMESİ :" line,
# "Dava Türü", the opening formula. Then the opening sentences of the temyiz text, for the
# decisions whose DAVA line was lost in the extraction.
_BODY_RE = re.compile(
    r"^[ \t]*(?:"
    r"DAVA\b|Dava[ \t]*[,;:.]|D A V A|I\.[ \t]*[A-ZÇĞİÖŞÜ]{3,}|MAHKEMESİ[ \t]*:|DAVACI[ \t]*:"
    r"|Dava[ \t]+Türü|Taraflar[ \t]+arasında|DAVANIN[ \t]+KONUSU|Yukarıda[ \t]+bilgileri"
    r"|(?:Y A R G I T A Y|YARGITAY)[ \t]+(?:K A R A R I|KARARI)|Davacı[ \t]+(?:vekili|İsteminin)"
    r"|[A-E]\)[ \t]*Davacı|BAŞVURUNUN[ \t]+KONUSU|OLAY[ \t]+VE[ \t]+OLGULAR|GİRİŞ[ \t]*$"
    r"|Davacılar?[ \t]*,"
    r"|Davacı\b[^\n]{0,220}(?:\n[^\n]{0,220}){0,2}"
    r"(?:istemiştir|talep etmiştir|talebinde bulunmuştur)"
    r"|Yerel[ \t]+mahkeme,|Mahkeme[ \t]+ilamında|Hüküm[ \t]+süresi[ \t]+içinde"
    r"|Hükmün[ \t,]+(?:davacı|davalı|taraf)"
    r")",
    re.MULTILINE,
)
# Last resort when no marker above exists: the temyiz formula inside the opening paragraph. The
# body then starts at the formula's line, which can lose the first line of the paragraph.
_FORMULA_RE = re.compile(
    r"^[^\n]*(?:temyizen[ \t]+incelenmesi|temyiz[ \t]+edilmiş[ \t]+olmakla"
    r"|hükmün[^\n]{0,40}temyiz)",
    re.MULTILINE,
)
# Foreign-court articles have no DAVA heading; their summary ends at the facts section.
_FOREIGN_BODY_RE = re.compile(
    r"^[ \t]*(?:Olay|OLAY|Olaylar|OLAYLAR|Giriş|GİRİŞ|DAVANIN KONUSU)\b", re.MULTILINE
)


@dataclass
class _Meta:
    end: int
    esas: str = ""
    karar: str = ""
    tarih: str = ""
    esas_candidates: list[str] = field(default_factory=list)
    individual: bool = False
    lower_court_date: bool = False  # a TARİHİ line followed the origin court: not Yargıtay's


def _scan_meta(lines: list[str], first: int, labelled: bool = True) -> _Meta:
    """Read the label lines from `first` on; values are inline or standalone lines in label
    order (two-column layout). Unlabelled rows (`labelled=False`, the 2004 issue whose labels
    were lost) are read as Esas, Karar, Tarih, skipping the court-of-origin line between."""
    meta = _Meta(first)
    pending = [] if labelled else ["esas", "karar", "tarih"]  # kinds still waiting for a value
    skipped = 0
    origin_value = False  # the line after a bare "MAHKEMESİ" label is its value
    after_origin = False  # past a "MAHKEMESİ" line: TARİHİ / NO then describe the lower court
    numbers: list[str] = []
    dates: list[str] = []
    values: dict[str, str] = {}
    i = first
    while i < len(lines):
        line = lines[i]
        if m := LABEL_RE.match(line) or OCR_LABEL_RE.match(line):
            origin_value = False
            groups = m.groupdict()
            kind = next(k for k in ("esas", "karar", "basvuru", "tarih", "e", "k") if groups.get(k))
            kind = {"basvuru": "esas", "e": "esas", "k": "karar"}.get(kind, kind)
            if kind == "esas" and groups.get("basvuru"):
                meta.individual = True
            if after_origin and kind in ("tarih", "karar"):
                meta.lower_court_date |= kind == "tarih"
                i += 1
                continue
            value = m["value"]
            if value:
                if kind in values:
                    if kind == "esas":
                        meta.esas_candidates.append(value)
                else:
                    values[kind] = value
            elif kind not in values:
                pending.append(kind)
        elif after_origin and "tarih" not in pending and _DATE_VALUE_RE.match(line):
            meta.lower_court_date = True
        elif _DATE_VALUE_RE.match(line):
            dates.append(line)
        elif _NUMBER_VALUE_RE.match(line):
            numbers.append(line)
        elif _ORIGIN_LABEL_RE.match(line):
            origin_value = after_origin = True
        elif _ORIGIN_START_RE.match(line):
            after_origin = True
        elif origin_value and line.strip() != ":":
            origin_value = False
        elif not _META_SKIP_RE.match(line):
            if labelled or dates or skipped == _MAX_UNLABELLED_SKIP:
                break
            skipped += 1
        i += 1
    for kind in pending:
        pool = dates if kind == "tarih" else numbers
        if pool and kind not in values:
            values[kind] = pool.pop(0)
    meta.end = i
    meta.esas, meta.karar, meta.tarih = (values.get(k, "") for k in ("esas", "karar", "tarih"))
    return meta


def _court_block(lines: list[str], first: int) -> tuple[int, list[str]]:
    """The court lines directly above the first label: (index of first block line, lines)."""
    start = first
    while start > 0 and first - start < _MAX_COURT_LINES:
        prev = lines[start - 1].strip()
        if prev and (len(prev) > 70 or not _COURT_LINE_RE.search(_squash(prev))):
            break
        start -= 1
    if (
        start > 0
        and _CITY_RE.match(tr_upper(lines[start - 1].strip()))
        and "BÖLGE" in _squash(" ".join(lines[start:first]))
    ):
        start -= 1
    return start, lines[start:first]


# --- Related articles -----------------------------------------------------------------------

# "4857 S.İşK/18-21", "1475 s.İşK: 14", "6356S. STK/25", "BK:90", "4857/18-21" (no label), and
# the typos of the source: "4857/S.İşK/7", "S.K .26", "İşK24", "BK 161", "SSK/. 79", "K: /13".
_REF_RE = re.compile(
    r"^[ \t]*(?:(?P<num>\d{1,4})[ \t]*[./]?[ \t]*(?:[sS][ \t]*\.[ \t]*|[sS][ \t]+)?)?"
    r"(?P<label>[^\d:/•]{0,30}?)(?P<sep>[ \t]*[:/.][ \t:/.]*|[ \t]+|(?<=[^\W\d])(?=\d))"
    r"(?P<arts>(?:[,\d]|[Gg]e[cç]|GEÇ|G\.|[Ee]k\b|EK\b|[Mm]ük|MÜK).*?)[ \t]*$"
)
# Issue 65 prints the block interleaved with the labels: "Esas No. 2001/23336 İlgili
# Kanun/Madde:" followed by "Karar No. 2002/16275 4857 S. İşK/32" and "Tarihi: 16.09.2002 [ref]".
_INTERLEAVED_RE = re.compile(r"İlgili Kanun/Madde:[ \t]*$(?P<rest>)", re.MULTILINE)
_TRAILING_REF_RE = re.compile(
    r"^[ \t]*(?:Karar No\.|Tarihi:)[ \t]*(?:\d{4}/\d+|[\d./]+)[ \t]+(?P<ref>\d{1,4}[ \t]*S.*)$"
)
_MAX_BARE_LABEL = 12  # a label without ":" or "/" must look like an abbreviation, not a keyword


def _match_ref(line: str) -> re.Match[str] | None:
    m = _REF_RE.match(line)
    if m is None or len(line) > 70:
        return None
    if ":" not in m["sep"] and "/" not in m["sep"]:
        label = m["label"].strip(" .")
        if " " in label or len(label) > _MAX_BARE_LABEL:
            return None
    return m


_RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
_MAX_RANGE = 200

# Abbreviation → statute number for labels printed without a number. Keys are `_abbr_key`.
_STATIC_STATUTES = {
    "sgk": 5510, "ssgsk": 5510, "ssgssk": 5510, "ssgskk": 5510, "ssk": 506,
    "bağkur": 1479, "bağkurk": 1479, "bağk": 1479, "isgk": 6331, "tbk": 6098,
    "işmk": 7036, "iik": 2004, "tck": 5237, "möhuk": 5718, "vuk": 213,
}  # fmt: skip
# Abbreviations whose statute changed on a known date: (old, new, first day of the new one).
# 6356 (in force 2012-11-07) replaced both union statutes: Sendikalar Kanunu 2821 and Toplu İş
# Sözleşmesi, Grev ve Lokavt Kanunu 2822.
_DATED_STATUTES = {
    "stk": (2821, 6356, "2012-11-07"),
    "stsk": (2821, 6356, "2012-11-07"),
    "stisk": (2821, 6356, "2012-11-07"),
    "tsk": (2822, 6356, "2012-11-07"),
    "tsglk": (2822, 6356, "2012-11-07"),
    "bk": (818, 6098, "2012-07-01"),
    "humk": (1086, 6100, "2011-10-01"),
    "hmk": (1086, 6100, "2011-10-01"),
    "işk": (1475, 4857, "2003-06-10"),
}


def _abbr_key(label: str) -> str:
    return re.sub(r"[\s.\-]", "", tr_lower(label))


def resolve_statute(
    number: int | None, label: str, decision_date: str | None
) -> tuple[int | None, bool]:
    """(statute number or None, inferred_from_date). A printed number always wins."""
    if number is not None:
        return number, False
    key = _abbr_key(label)
    if key in _STATIC_STATUTES:
        return _STATIC_STATUTES[key], False
    if key in _DATED_STATUTES and decision_date:
        old, new, since = _DATED_STATUTES[key]
        return (new if decision_date >= since else old), True
    return None, False


def _expand_articles(arts: str) -> list[str]:
    out: list[str] = []
    for token in re.split(r"[,;]", arts):
        token = token.strip().rstrip(".").strip()
        if not token:
            continue
        m = _RANGE_RE.fullmatch(token)
        if m and 0 < int(m[2]) - int(m[1]) <= _MAX_RANGE:
            out += [str(n) for n in range(int(m[1]), int(m[2]) + 1)]
        else:
            out.append(token)
    return out


def _parse_related(
    lines: list[str], decision_date: str | None
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Articles of the "İlgili Kanun / Madde" block: (entries, index after the block, warnings).
    Returns an empty block with index 0 when there is none."""
    for i, line in enumerate(lines):
        header = _RELATED_RE.match(line)
        if header is None and _INTERLEAVED_RE.search(line):
            header = _INTERLEAVED_RE.search(line)
        if header is None:
            continue
        entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        pending = [header["rest"]] if header["rest"].strip() else []
        j = i + 1
        if _INTERLEAVED_RE.search(line):
            pending = [m["ref"] for m in map(_TRAILING_REF_RE.match, lines[j : j + 2]) if m]
            j += 2
        if not pending and j < len(lines) and lines[j].strip() in ("Madde", "md:"):
            j += 1  # the header wrapped: "İlgili Kanun /\nMadde"
        while True:
            while j < len(lines) and not pending:
                if _match_ref(lines[j]) is None:
                    break
                pending.append(lines[j])
                j += 1
            if not pending:
                break
            for raw in pending:
                m = _match_ref(raw)
                if m is None:
                    continue
                label = m["label"].strip(" .")
                number = int(m["num"]) if m["num"] else None
                statute, inferred = resolve_statute(number, label, decision_date)
                if statute is None:
                    warnings.append("statute_unmapped")
                elif inferred:
                    warnings.append("statute_inferred_from_date")
                entries.append(
                    {
                        "statute": statute,
                        "label": label,
                        "articles": _expand_articles(m["arts"]),
                        "raw": raw.strip(),
                    }
                )
            pending = []
        return entries, j, warnings
    return [], 0, []


# --- Keywords -------------------------------------------------------------------------------


def _keywords(lines: list[str]) -> list[str]:
    """Bulleted (or one-per-line) uppercase keyword lines, wrapped lines joined."""
    bulleted = any(line.lstrip().startswith("•") for line in lines)
    items: list[str] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if text.startswith("•"):
            text = text.lstrip("• \t")
            if text:
                items.append(text)
        elif bulleted and items:
            items[-1] += " " + text
        else:
            items.append(text)
    return [i for i in items if re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{2}", i)]


# --- Outcome --------------------------------------------------------------------------------

_RESULT_RE = re.compile(
    r"^[ \t]*(?:[A-H]\)[ \t]*)?"
    r"(?:SONUÇ|Sonuç|S O N U Ç|HÜKÜM|VI\.[ \t]*KARAR|V\.[ \t]*(?:SONUÇ|HÜKÜM))[ \t]*:?",
    re.MULTILINE,
)
# Checked in order: a mixed ruling ("bozulmasına ... onanmasına") counts as its first match.
_OUTCOMES = (
    ("düzelterek onama", re.compile(r"DÜZELTİLEREK\s+ONAN")),
    ("bozma", re.compile(r"BOZ(?:UL|MA)")),
    ("onama", re.compile(r"ONAN")),
    ("ihlal_yok", re.compile(r"İHLAL\s+EDİLMEDİĞİNE|İHLAL\s+EDİLMEDİ")),
    ("ihlal", re.compile(r"İHLAL\s+EDİLDİĞİNE|İHLAL\s+EDİLDİ")),
    ("kabul", re.compile(r"KABUL")),
    ("red", re.compile(r"RED(?:D|\b)")),
)


_RULING_CHARS = 1500  # the ruling sits right after its heading; later text may be a dissent


_CLOSING_RE = re.compile(r"karar[ \t\n]+verildi", re.IGNORECASE)


def _classify(section: str) -> str:
    upper = tr_upper(section)
    return next((name for name, rx in _OUTCOMES if rx.search(upper)), "")


def _outcome(body: str) -> str:
    """The ruling after the last result heading that holds one; without a heading, the closing
    "... karar verildi" sentence."""
    for heading in reversed(list(_RESULT_RE.finditer(body))):
        if name := _classify(body[heading.end() : heading.end() + _RULING_CHARS]):
            return name
    closing = list(_CLOSING_RE.finditer(body))
    return (
        _classify(body[max(0, closing[-1].start() - _RULING_CHARS // 2) : closing[-1].end()])
        if closing
        else ""
    )


# --- Whole decision -------------------------------------------------------------------------


@dataclass
class DecisionFields:
    court: str = ""
    court_level: str = ""
    chamber: str = ""
    source_chamber: str = ""
    bam_region: str = ""
    decision_kind: str = "karar"
    jurisdiction: str = ""
    esas_no: str = ""
    karar_no: str = ""
    decision_date: str = ""
    related_articles: list[dict[str, Any]] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    outcome: str = ""
    editorial_summary: str = ""
    full_text: str = ""
    text_completeness: str = "summary_only"
    warnings: list[str] = field(default_factory=list)


_HEAD_LINES = 120  # the decision block, keywords and summary start all sit inside the first lines
# A body shorter than this is an excerpt. In the archive the shortest complete decisions
# (DAVA line, temyiz formula, one-paragraph reasoning, SONUÇ) are 749 chars; the only shorter
# body (320 chars) is cut off after its first sentences.
_MIN_FULL_CHARS = 700


def _first_label(lines: list[str]) -> int | None:
    for i, line in enumerate(lines[:_HEAD_LINES]):
        if LABEL_RE.match(line):
            return i
    return None


def _first_value_run(lines: list[str]) -> int | None:
    """Two case numbers in a row with a date right after: a block whose labels were lost."""
    for i, line in enumerate(lines[: _HEAD_LINES - 4]):
        if (
            _NUMBER_VALUE_RE.match(line)
            and _NUMBER_VALUE_RE.match(lines[i + 1])
            and any(_DATE_VALUE_RE.match(ln) for ln in lines[i + 2 : i + 5])
        ):
            return i
    return None


def _case_numbers(meta: _Meta, warnings: list[str]) -> tuple[str, str, str]:
    esas = normalize_case_no(meta.esas)
    karar = normalize_case_no(meta.karar)
    if esas is None and meta.esas:
        warnings.append("esas_unparsed")
    if karar is None and meta.karar:
        warnings.append("karar_unparsed")
    return (
        esas[0] if esas else "",
        karar[0] if karar else "",
        (esas[1] if esas else "") or (karar[1] if karar and not esas else ""),
    )


def _body_start(text: str, lines: list[str], search_from: int, foreign: bool) -> tuple[int, bool]:
    """(line index of the decision body or -1, whether the start is only approximate)."""
    offset = sum(len(line) + 1 for line in lines[:search_from])
    if match := (_FOREIGN_BODY_RE if foreign else _BODY_RE).search(text, offset):
        return text.count("\n", 0, match.start()), False
    if not foreign and (match := _FORMULA_RE.search(text, offset)):
        return text.count("\n", 0, match.start()), True
    return -1, False


def _other_esas(meta: _Meta, lines: list[str], head_end: int, chosen: str) -> list[str]:
    """Esas numbers that differ from the chosen one: repeated labels inside the block and
    further Esas lines before the body."""
    later = [
        m["value"]
        for line in lines[meta.end : head_end]
        if (m := LABEL_RE.match(line)) and m["esas"]
    ]
    found = {c[0] for v in meta.esas_candidates + later if (c := normalize_case_no(v))}
    return sorted(found - {chosen})


def extract_fields(journal: JournalText, layout: Layout) -> DecisionFields:
    f = DecisionFields()
    text, lines = journal.text, journal.text.split("\n")
    foreign = layout is Layout.FOREIGN_ARTICLE
    first, run = _first_label(lines), _first_value_run(lines)
    labelled = run is None or (first is not None and first < run)
    if not labelled:
        first = run
    meta = _scan_meta(lines, first, labelled) if first is not None else None
    block_start, block = 0, list[str]()
    if first is not None and not foreign:
        block_start, block = _court_block(lines, first)
    if meta is not None:
        f.esas_no, f.karar_no, f.source_chamber = _case_numbers(meta, f.warnings)
        iso, invalid = parse_date(meta.tarih)
        f.decision_date = iso or ""
        if invalid:
            f.warnings.append("invalid_date")
        if meta.lower_court_date and not f.decision_date:
            f.warnings.append("date_is_lower_court")
    if foreign and not f.decision_date:  # ECtHR articles print the date alone: "13 Ocak 2015"
        named = (parse_date(ln)[0] for ln in lines[:15] if _NAMED_DATE_RE.fullmatch(ln.strip()))
        f.decision_date = next((d for d in named if d), "")
    info = classify_court(block, journal, bool(meta and meta.individual))
    for name in ("court", "court_level", "chamber", "decision_kind", "jurisdiction", "bam_region"):
        setattr(f, name, getattr(info, name))

    meta_end = meta.end if meta else 0
    summary = next((i for i, ln in enumerate(lines[:_HEAD_LINES]) if SUMMARY_RE.match(ln)), None)
    # Era 1 prints the court block after the summary; the decision itself follows the block.
    summary_first = summary is not None and first is not None and summary < first
    if summary_first:
        body_line, approximate = meta_end, False
    else:
        search_from = meta_end if summary is None else summary + 1
        body_line, approximate = _body_start(text, lines, search_from, foreign)
    if approximate:
        f.warnings.append("body_start_approximate")
    has_body = body_line >= 0
    if meta is not None:
        others = _other_esas(meta, lines, body_line if has_body else _HEAD_LINES, f.esas_no)
        if others:
            f.warnings.append(f"multiple_esas_candidates:{','.join(others)}")

    if summary is not None:
        summary_end = block_start if summary_first else (body_line if has_body else len(lines))
        raw = "\n".join(lines[summary:summary_end])
        f.editorial_summary = _SUMMARY_LABEL_RE.sub("", raw).strip()
    if has_body:
        f.full_text = "\n".join(lines[body_line:]).strip()
        f.text_completeness = "full" if len(f.full_text) >= _MIN_FULL_CHARS else "excerpt"
        f.outcome = _outcome(f.full_text)

    entries, related_end, related_warnings = _parse_related(
        lines[: body_line if has_body else _HEAD_LINES], f.decision_date or None
    )
    f.related_articles = entries
    f.warnings += related_warnings
    keywords_end = summary if summary is not None else (body_line if has_body else meta_end)
    keywords_start = max(related_end, meta_end if meta_end <= keywords_end else 0)
    if not foreign and keywords_start < keywords_end:
        f.keywords = _keywords(lines[keywords_start:keywords_end])
    return f
