"""Article-level diff between two snapshots of the same statute (task 11a).

Texts are compared after normalisation: whitespace, line breaks, quote and dash variants and
footnote markers do not count as changes. When the remaining difference is only punctuation,
case or diacritics the article is `unchanged` with the `uncertain_diff` warning; a change of a
couple of words is `changed` with the same warning."""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from hukuk_ingest.statutes.split import Snapshot

UNCHANGED, CHANGED, ADDED, REMOVED = "unchanged", "changed", "added", "removed"
_SMALL_CHANGE_WORDS = 2  # a difference this small may be noise rather than an amendment

_QUOTES = str.maketrans(
    {"“": '"', "”": '"', "„": '"', "‟": '"', "‘": "'", "’": "'", "`": "'", "´": "'"}
)
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-", "￾": "-", "￿": "-"})
# A footnote marker glued to the end of a word or after punctuation: `kesilmesi47`, `(…)48`.
_GLUED_MARKER_RE = re.compile(
    r"(?<=[^\W\d_)”’.,;:…\-/])\d{1,3}(?=\s|$)|(?<=[)”’.,;:…])\d{1,3}(?=\s|$)"
)
_BRACKET_MARKER_RE = re.compile(r"(?<=[^\s(])[ \t]*\(\d{1,3}\)(?=\s|$|\()")
_FOLD = str.maketrans("ıîâûöüşçğ", "iiauousc" + "g")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_QUOTES).translate(_DASHES)
    text = _BRACKET_MARKER_RE.sub("", text)
    text = _GLUED_MARKER_RE.sub("", text)
    text = re.sub(r"(?<=[a-zçğıöşü])-\s+(?=[a-zçğıöşü])", "-", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r":(?=\S)", ": ", text)
    text = re.sub(r"(?<=\d)\s*-\s*(?=\d|KHK)", "-", text)
    return text.strip()


def skeleton(text: str) -> str:
    """Letters and digits only, lower case, diacritics folded."""
    lowered = text.replace("İ", "i").replace("I", "ı").lower().translate(_FOLD)
    return re.sub(r"[\W_]+", "", lowered)


@dataclass
class ArticleDiff:
    article_no: str
    kind: str
    warnings: list[str] = field(default_factory=list)


def compare(old: str, new: str) -> tuple[str, list[str]]:
    """(`unchanged` | `changed`, warnings) for two article texts."""
    a, b = normalize(old), normalize(new)
    if a == b:
        return UNCHANGED, []
    if skeleton(a) == skeleton(b):
        return UNCHANGED, ["uncertain_diff"]
    wa, wb = a.split(), b.split()
    matcher = SequenceMatcher(None, wa, wb, autojunk=False)
    changed_words = sum(
        max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"
    )
    return CHANGED, ["uncertain_diff"] if changed_words <= _SMALL_CHANGE_WORDS else []


def diff_snapshots(old: Snapshot, new: Snapshot) -> list[ArticleDiff]:
    """One entry per article number present in either snapshot (order: new, then removed)."""
    old_by_no = {a.article_no: a for a in old.articles}
    out: list[ArticleDiff] = []
    for art in new.articles:
        prev = old_by_no.pop(art.article_no, None)
        if prev is None:
            out.append(ArticleDiff(art.article_no, ADDED))
            continue
        kind, warnings = compare(prev.text, art.text)
        out.append(ArticleDiff(art.article_no, kind, warnings))
    out.extend(ArticleDiff(no, REMOVED) for no in old_by_no)
    return out
