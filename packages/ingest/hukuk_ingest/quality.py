"""Deterministic text-quality signals used to route files to OCR."""

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

PAGE_BREAK = "\f"
# Below this many visible (non-whitespace) characters a PDF page has effectively no text layer
# (scans: 0; real pages: hundreds+).
MIN_CHARS_PER_PAGE = 50
# Share of Turkish function words among tokens. Full-corpus calibration (task 03): broken OCR
# layers score 0.000-0.021; sound 1-2 page decisions score 0.036-0.059 (short legal text has few
# function words); sound documents overall >= 0.060. The spec's 0.06 cut-off (spike, different
# word list) flagged 24 sound decisions, so the cut-off sits in the empty gap at 0.03 and the
# band up to BORDERLINE_RATIO (the spec's 0.06) is accepted but flagged. The gap is narrow and
# rests on 4 broken samples; partially corrupt layers above the band (seen at 0.094) still pass.
BAD_OCR_RATIO = 0.03
BORDERLINE_RATIO = 0.06
# A page is empty only when it has no visible text at all. Journal decisions end on a page
# holding just the running header and a page number (~20 characters), and 53 of them are
# followed by a fully blank page: trailing blanks are layout, not scans, so only empty pages
# before the last page with text ("interior") are evidence of a partial text layer.
# A ratio over fewer tokens is noise (a page of numbers has no function words).
MIN_TOKENS = 50
# A partially scanned PDF is routed to OCR once this share of its pages are interior empty
# pages: a third of the document missing is not a "warning" for a legal-research pipeline.
# Below the share, the document stays ok with an `empty_pages` warning.
PARTIAL_TEXT_LAYER_SHARE = 0.3

STOPWORDS = frozenset(
    "ve bir bu ile için olarak sayılı madde de da ise veya ancak göre gibi daha olan "
    "kanun kanunu hakkında tarafından kadar sonra her ya ki mi ne şu o ayrıca ilgili "
    "olduğu edilen".split()
)

_TOKEN_RE = re.compile(r"[^\W\d_]+")
_TR_LETTERS = frozenset("abcçdefgğhıijklmnoöprsştuüvyzqwxABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZQWX")
# Share of visible characters in those scripts that marks a broken layer. Sound decisions quote
# foreign text (an AİHM judgment with Russian passages: 0.3%); garbage layers are far denser.
FOREIGN_SCRIPT_SHARE = 0.01
# CJK ideographs, kana, hangul (garbage glyphs of broken OCR layers), plus Cyrillic and
# Arabic, which are never part of Turkish legal text.
_FOREIGN_SCRIPT_RE = re.compile(
    "[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\u0400-\u052f\u0600-\u06ff\u0750-\u077f"
    "\ufb50-\ufdff\ufe70-\ufeff]"
)


def _fold(token: str) -> str:
    return token.replace("İ", "i").replace("I", "ı").lower()


def fingerprint() -> str:
    """Everything that decides a quality verdict, for cache invalidation."""
    parts = (
        MIN_CHARS_PER_PAGE,
        FOREIGN_SCRIPT_SHARE,
        BAD_OCR_RATIO,
        BORDERLINE_RATIO,
        MIN_TOKENS,
        PARTIAL_TEXT_LAYER_SHARE,
        sorted(STOPWORDS),
        _FOREIGN_SCRIPT_RE.pattern,
    )
    return hashlib.sha256(repr(parts).encode()).hexdigest()[:16]


def _stopword_ratio(text: str) -> tuple[int, float | None]:
    tokens = [_fold(t) for t in _TOKEN_RE.findall(text)]
    if not tokens:
        return 0, None
    return len(tokens), sum(1 for t in tokens if t in STOPWORDS) / len(tokens)


@dataclass(frozen=True)
class Quality:
    chars: int
    pages: int | None
    chars_per_page: float | None
    tr_letter_ratio: float
    qmark_ratio: float
    stopword_ratio: float
    tokens: int
    foreign_script_chars: int
    foreign_script_ratio: float
    empty_pages: int
    interior_empty_pages: int
    worst_page_stopword_ratio: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def measure(text: str, pages: int | None) -> Quality:
    visible = [c for c in text if not c.isspace()]
    n = len(visible)
    n_tokens, ratio = _stopword_ratio(text)
    empty_pages = 0
    interior_empty_pages = 0
    worst: float | None = None
    page_texts = text.split(PAGE_BREAK)
    if pages and len(page_texts) == pages:
        last_text_page = max((i for i, page in enumerate(page_texts) if page.strip()), default=-1)
        for i, page in enumerate(page_texts):
            if not page.strip():
                empty_pages += 1
                interior_empty_pages += i < last_text_page
                continue
            page_tokens, page_ratio = _stopword_ratio(page)
            if page_ratio is not None and page_tokens >= MIN_TOKENS:
                worst = page_ratio if worst is None else min(worst, page_ratio)
    foreign = len(_FOREIGN_SCRIPT_RE.findall(text))
    return Quality(
        chars=len(text),
        pages=pages,
        chars_per_page=n / pages if pages else None,
        tr_letter_ratio=round(sum(c in _TR_LETTERS for c in visible) / n, 4) if n else 0.0,
        qmark_ratio=round(sum(c in "?�" for c in visible) / n, 4) if n else 0.0,
        stopword_ratio=round(ratio or 0.0, 4),
        tokens=n_tokens,
        foreign_script_chars=foreign,
        foreign_script_ratio=round(foreign / n, 4) if n else 0.0,
        empty_pages=empty_pages,
        interior_empty_pages=interior_empty_pages,
        worst_page_stopword_ratio=None if worst is None else round(worst, 4),
    )


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str | None = None
    warnings: tuple[str, ...] = ()


def judge(q: Quality) -> Verdict:
    """OCR routing for page-based text layers (PDF)."""
    if not q.pages or q.chars_per_page is None or q.chars_per_page < MIN_CHARS_PER_PAGE:
        return Verdict(False, "no_text_layer")
    if q.interior_empty_pages / q.pages >= PARTIAL_TEXT_LAYER_SHARE:
        return Verdict(False, "partial_text_layer")
    if q.foreign_script_ratio >= FOREIGN_SCRIPT_SHARE:
        return Verdict(False, "bad_ocr_layer")
    warnings: list[str] = []
    if q.tokens < MIN_TOKENS:
        warnings.append("too_little_text")
    elif q.stopword_ratio < BAD_OCR_RATIO:
        return Verdict(False, "bad_ocr_layer")
    elif q.stopword_ratio < BORDERLINE_RATIO:
        warnings.append("borderline_quality")
    if q.empty_pages:
        warnings.append("empty_pages")
    if q.worst_page_stopword_ratio is not None and q.worst_page_stopword_ratio < BAD_OCR_RATIO:
        warnings.append("weak_page_text")
    return Verdict(True, warnings=tuple(warnings))
