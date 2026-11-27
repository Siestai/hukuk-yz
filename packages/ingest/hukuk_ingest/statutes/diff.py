"""Article-level diff between two snapshots of the same statute (task 11a).

Texts are compared after normalisation: whitespace, line breaks, quote and dash variants and
footnote markers (also those printed on a line of their own or detached from their sentence) do
not count as changes. Apart from a `(n)` that closes a line after punctuation, only numbers the
splitter knows as footnote numbers of the article are removed as markers; every other digit
stays, so a changed cross reference (`(4)` -> `(5)`) is a change. When the remaining difference is
only punctuation, case or diacritics the article is `unchanged` with the `uncertain_diff` warning;
a change of a couple of words is `changed` with the same warning. A line-end `(n)` that no
snapshot knows as a footnote is dropped only as a last resort, and then with `uncertain_diff`."""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from hukuk_ingest.statutes.split import Article, Snapshot, decompose

UNCHANGED, CHANGED, ADDED, REMOVED = "unchanged", "changed", "added", "removed"
_SMALL_CHANGE_WORDS = 2  # a difference this small may be noise rather than an amendment

_QUOTES = str.maketrans(
    {"“": '"', "”": '"', "„": '"', "‟": '"', "‘": "'", "’": "'", "`": "'", "´": "'"}
)
_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-", "￾": "-", "￿": "-"})
# A footnote marker glued to the end of a word or after punctuation: `kesilmesi47`, `(…)48`.
_GLUED_MARKER_RE = re.compile(
    r"(?<=[^\W\d_)”’.,;:…\-/])\d{1,6}(?=\s|$)|(?<=[)”’.,;:…])\d{1,6}(?=\s|$)"
)
_BRACKET_MARKER_RE = re.compile(r"(?<=[^\s(])[ \t]*\((\d{1,3})\)(?=\s|$|\()")
# A marker printed on a line of its own (`öncesinden,` / `(1)` / `8) ...`).
_OWN_LINE_MARKER_RE = re.compile(r"(?m)^[ \t]*\((\d{1,3})\)[ \t]*$")
# A marker detached from its sentence, before a sub-item label: `... kullanması. 8 e) ...`.
_DETACHED_MARKER_RE = re.compile(r"(?<=[.;:])[ \t]+(\d{1,3})(?=[ \t]+[a-zçğıöşü]\))")
# A `(n)` that closes a line right after sentence punctuation is probably a marker (a paragraph
# number opens a line), but it may also be a cross reference: it is removed silently only when a
# snapshot knows `n` as a footnote number (`_strip_markers`); otherwise `compare` decides.
_LINE_END_MARKER_RE = re.compile(r"(?m)(?<=[.;:,])[ \t]*\(\d{1,3}\)[ \t]*$")
_FOLD = str.maketrans("ıîâûöüşçğ", "iiauousc" + "g")


def _line_end_numbers(text: str) -> frozenset[int]:
    return frozenset(int(re.sub(r"\D", "", m[0])) for m in _LINE_END_MARKER_RE.finditer(text))


def _strip_markers(text: str, markers: frozenset[int], any_line_end: bool = False) -> str:
    text = _LINE_END_MARKER_RE.sub(
        lambda m: "" if any_line_end or int(re.sub(r"\D", "", m[0])) in markers else m[0], text
    )
    if not markers:
        return text
    text = _OWN_LINE_MARKER_RE.sub(lambda m: "" if int(m[1]) in markers else m[0], text)
    text = _DETACHED_MARKER_RE.sub(lambda m: "" if int(m[1]) in markers else m[0], text)
    text = _BRACKET_MARKER_RE.sub(lambda m: "" if int(m[1]) in markers else m[0], text)
    return _GLUED_MARKER_RE.sub(lambda m: "" if decompose(m[0], set(markers)) else m[0], text)


def normalize(text: str, markers: frozenset[int] = frozenset(), any_line_end: bool = False) -> str:
    """`markers`: the footnote numbers of the article; only they are removed from the text.
    `any_line_end`: also remove a line-end `(n)` whose number is no known marker."""
    text = unicodedata.normalize("NFC", text).translate(_QUOTES).translate(_DASHES)
    text = _strip_markers(text, markers, any_line_end)
    text = re.sub(r"(?<=[a-zçğıöşü])-\s+(?=[a-zçğıöşü])", "-", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"%\s+(?=\d)", "%", text)
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


def marker_numbers(art: Article) -> frozenset[int]:
    return frozenset(f.no for f in art.footnotes)


def same_wording(
    old: str,
    new: str,
    old_markers: frozenset[int] = frozenset(),
    new_markers: frozenset[int] = frozenset(),
) -> bool:
    """Equal up to layout: whitespace, line breaks, quote and dash variants, footnote markers."""

    def light(text: str, markers: frozenset[int]) -> str:
        text = unicodedata.normalize("NFC", text).translate(_QUOTES).translate(_DASHES)
        return " ".join(_strip_markers(text, markers).split())

    return light(old, old_markers) == light(new, new_markers)


def compare(
    old: str,
    new: str,
    old_markers: frozenset[int] = frozenset(),
    new_markers: frozenset[int] = frozenset(),
) -> tuple[str, list[str]]:
    """(`unchanged` | `changed`, warnings) for two article texts."""
    a, b = normalize(old, old_markers), normalize(new, new_markers)
    if a == b:
        return UNCHANGED, []
    if old_markers != new_markers:
        # A snapshot whose footnotes were not read leaves its markers in the text: the numbers
        # of the other snapshot identify them.
        both = old_markers | new_markers
        if normalize(old, both) == normalize(new, both):
            return UNCHANGED, ["uncertain_diff"]
    if skeleton(a) == skeleton(b):
        return UNCHANGED, ["uncertain_diff"]
    # Last resort: unknown line-end `(n)` may be markers of footnotes that were not read. If both
    # sides end lines with different unknown numbers, that is more likely an amended cross
    # reference than a layout difference, so the numbers are kept and the diff below decides.
    known = old_markers | new_markers
    ends_old, ends_new = _line_end_numbers(old) - known, _line_end_numbers(new) - known
    if (not ends_old or not ends_new or ends_old == ends_new) and normalize(
        old, old_markers, True
    ) == normalize(new, new_markers, True):
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
        kind, warnings = compare(prev.text, art.text, marker_numbers(prev), marker_numbers(art))
        out.append(ArticleDiff(art.article_no, kind, warnings))
    out.extend(ArticleDiff(no, REMOVED) for no in old_by_no)
    return out
