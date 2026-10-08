"""Parses the inline amendment notes of an article text (task 11a).

A note is a parenthesis such as `(Değişik birinci fıkra: 12/10/2017-7036/11 md.)`; one
parenthesis may hold several items separated by `;`. Every item becomes one `Annotation`.
A parenthesis that starts like a note but cannot be parsed stays as `raw` with the
`unparsed_annotation` warning: nothing is dropped."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

# The first word of a note item decides its kind.
KINDS = {
    "değişik": "degisik",
    "ek": "ek",
    "mülga": "mulga",
    "iptal": "iptal",
    "yeniden": "degisik",  # "Yeniden düzenleme": the provision was rewritten
    "aynen": "kabul",  # a decree-law re-enacted as it was: no text change
    "değiştirilerek": "degisik",  # re-enacted with changes
}
_OPEN_RE = re.compile(
    r"\(\s*(?:Başlığı\s+ile\s+[Bb]irlikte\s+)?(?:Değişik|Ek|Mülga|İptal|Yeniden|Aynen|Değiştirilerek)"
    r"(?:\s+[a-zçğıöşü]+)*\s*:"
)
_ITEM_RE = re.compile(
    r"^(?P<kind>[A-ZÇĞİÖŞÜa-zçğıöşü]+)(?P<scope>(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*?)\s*:\s*"
    r"(?P<d>\d{1,2})\s*/\s*(?P<m>\d{1,2})\s*/\s*(?P<y>\d{4})\s*[-–—]\s*"
    r"(?:(?P<khk>KHK)[^\d]{0,3})?(?P<law>\d+)\s*/\s*(?P<art>\d+)\s*(?:md\.?)?\s*[.,]?\s*$",
    re.IGNORECASE,
)
_COURT_RE = re.compile(
    r"^(?P<kind>İptal)(?P<scope>(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*?)\s*:\s*"
    r"Anayasa Mahkemesi[’']?\s*nin\s+"
    r"(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})\s+tarihli\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_MD_RE = re.compile(r"\d{4}\s*[-–—]\s*(?:KHK\W*)?\d+\s*/\s*\d+\s*md\.")
_SPLIT_RE = re.compile(
    r"[;,](?=\s*(?:Başlığı|Değişik|Ek|Mülga|İptal|Yeniden|Aynen|Değiştirilerek)\b[^;]*:)"
)
_PAREN_RE = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
_SCOPE_DROP = {"başlığı", "ile", "birlikte"}


@dataclass(frozen=True)
class Annotation:
    kind: str  # degisik | ek | mulga | iptal | kabul
    scope: str  # "birinci fıkra", "cümle", "" (the whole article)
    date: date  # kabul date of the amending act
    law: str  # "6552", "KHK-665" or "AYM" (Anayasa Mahkemesi decision)
    law_article: str
    raw: str
    offset: int  # start of the parenthesis in the article text

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "scope": self.scope,
            "date": self.date.isoformat(),
            "law": self.law,
            "law_article": self.law_article,
            "raw": self.raw,
        }


def _date(d: str, m: str, y: str) -> date | None:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _scope(words: str, title: bool) -> str:
    scope = " ".join(w for w in words.lower().split() if w not in _SCOPE_DROP)
    return f"başlık {scope}".strip() if title else scope


def parse_item(item: str, raw: str, offset: int) -> Annotation | None:
    text = " ".join(item.split())
    title = text.startswith("Başlığı")
    text = re.sub(r"^Başlığı\s+ile\s+birlikte\s+", "", text, flags=re.IGNORECASE)
    m = _ITEM_RE.match(text)
    court = _COURT_RE.match(text) if m is None else None
    g = m or court
    if g is None:
        return None
    kind = KINDS.get(g["kind"].replace("İ", "i").replace("I", "ı").lower())
    when = _date(g["d"], g["m"], g["y"])
    if kind is None or when is None:
        return None
    if m is not None:
        law = f"KHK-{m['law']}" if m["khk"] else m["law"]
        article = m["art"]
    else:
        law, article = "AYM", ""
    scope = _scope(g["scope"], title)
    if g["kind"].startswith("Değiştirilerek"):
        scope = f"değiştirilerek {scope}".strip()
    return Annotation(kind, scope, when, law, article, raw, offset)


def parse_annotations(text: str) -> tuple[list[Annotation], list[str]]:
    """All notes of an article text (in order) and the raw parentheses that could not be parsed."""
    notes: list[Annotation] = []
    unparsed: list[str] = []
    flat = " ".join(text.split())
    for m in _PAREN_RE.finditer(flat):
        if not _OPEN_RE.match(m.group(0)):
            if _MD_RE.search(m.group(0)):  # looks like a note, starts like none we know
                unparsed.append(m.group(0))
            continue
        inner = m.group(0)[1:-1]
        items = [x for x in _SPLIT_RE.split(inner) if x.strip()]
        parsed = [parse_item(x, m.group(0), m.start()) for x in items]
        if parsed and all(parsed):
            notes.extend(p for p in parsed if p)
        else:
            unparsed.append(m.group(0))
    return notes, unparsed
