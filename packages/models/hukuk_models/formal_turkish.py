"""The register of the answers: formal Turkish (-mektedir / -maktadır, geniş zaman), never the
"-iyor" forms. The eval scorer and the agent's gate scan with the same expression."""

import re
from collections.abc import Iterable

PROGRESSIVE = re.compile(r"\b\w*[ıiuü]yor\w*\b", re.IGNORECASE)


def progressive_forms(texts: Iterable[str]) -> list[str]:
    """The distinct "-iyor" words in `texts`, sorted."""
    return sorted({m.group(0) for text in texts for m in PROGRESSIVE.finditer(text)})
