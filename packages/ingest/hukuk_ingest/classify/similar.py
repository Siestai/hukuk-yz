"""Text similarity of two extracted documents (task 13a), for the "looks like file X" hint.

The same decision from two sources differs in layout, page headers, line breaks and a few
characters, so the texts are compared as sets of word 5-grams after case and punctuation are
removed. The score is the share of the shorter document's 5-grams that the other one has too
(containment, not Jaccard): an excerpt of a document, or a document with a journal summary
added, still scores high. Pure Python and only ever run over a handful of candidates."""

import re

from hukuk_ingest.decisions.fields import tr_lower

SHINGLE_WORDS = 5
# Below this many 5-grams a document is too short to say anything about (a title page).
MIN_SHINGLES = 20
# Calibrated on 198 decisions of the archive (seed 13, 19,503 pairs): 99.9% of the pairs of
# different decisions score under 0.35 (the maximum, 0.85, is a decision printed twice); a
# rendering of the same text with 5% of its words garbled and its header lines dropped scores 0.65
# or more (median 0.78), with 15% garbled the median is 0.48. 0.5 keeps the false hints rare and
# still finds a second PDF of a decision whose text layer differs.
SIMILAR_THRESHOLD = 0.5
_WORD_RE = re.compile(r"[^\W_]+")


def shingles(text: str) -> frozenset[str]:
    words = _WORD_RE.findall(tr_lower(text))
    return frozenset(
        " ".join(words[i : i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)
    )


def containment(a: frozenset[str], b: frozenset[str]) -> float:
    """Share of the smaller set found in the other; 0.0 when either is too small to compare."""
    smaller = min(len(a), len(b))
    if smaller < MIN_SHINGLES:
        return 0.0
    return len(a & b) / smaller
