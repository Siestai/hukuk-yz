"""Source-independent text normalisation. Journal-specific cleanup belongs to the parser task."""

import re
import unicodedata

_BULLET_RE = re.compile("[⚫•▪]")
# Invisible characters that carry no meaning in running text: soft hyphen, zero-width space,
# word joiner, BOM. Removed before NFC so that no new composable sequence appears afterwards.
_INVISIBLE_RE = re.compile("[­​⁠﻿]")
# No-break and narrow/figure spaces become a plain space.
_SPACES_RE = re.compile("[   ]")
_CONJUNCTIONS = "ve|veya|ile|ya|de|da|mi|mı|mu|mü"
# A word broken at a line end: "kıdem-\ntazminatı". Both sides must be lowercase letters, so
# "4857 s.-\n", "İşK-\n18" and list dashes stay. A conjunction on the next line ("kıdem-\nve
# ihbar") is a suspended hyphen, not a hyphenation, and also stays.
# Known ambiguity: "e-\ndevlet" and "iş-\nveren" are indistinguishable from a suspended hyphen
# without a dictionary; we join (the raw text keeps the original).
_HYPHEN_BREAK_RE = re.compile(
    rf"(?<=[a-zçğıöşü])-\n(?=(?!(?:{_CONJUNCTIONS})(?![^\W\d_]))[a-zçğıöşü])"
)


def clean_text(raw: str) -> str:
    text = _INVISIBLE_RE.sub("", raw)
    text = _SPACES_RE.sub(" ", text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # The lookaround-only pattern removes one hyphen per match without consuming letters, so
    # chains ("a-\nb-\nc") resolve in one pass. The loop makes idempotence structural: a joined
    # word can change which word follows a hyphen (e.g. "ve-\nc" -> "vec").
    while (joined := _HYPHEN_BREAK_RE.sub("", text)) != text:
        text = joined
    return _BULLET_RE.sub("•", text)
