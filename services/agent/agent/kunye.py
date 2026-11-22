"""The künye strings of the topic templates ("4857 m.18", "2020/8 m.2.6.2.5",
"9. HD E.2016/28920 K.2017/17860"): which knowledge base record each one names.

A künye that is not in the form of its category names no record. It is never searched as free
text: the reader reports it as a missing source instead (md. 25).
"""

import re
from typing import NamedTuple

from agent.topics import SourceRef

_STATUTE = re.compile(r"(\d+) m\.(\S.*)")
_ADMIN_ACT = re.compile(r"(\d{4}/\d+)(?: m\.(\d+(?:\.\d+)*))?")
_DECISION = re.compile(r"\S.* E\.\s?\d{4}/\d+ K\.\s?\d{4}/\d+")


class StatuteArticle(NamedTuple):
    number: str
    article: str


class AdminActSection(NamedTuple):
    act: str
    # None: the künye names the whole act ("2020/8").
    section: str | None


def statute_article(ref: str) -> StatuteArticle | None:
    found = _STATUTE.fullmatch(ref.strip())
    return StatuteArticle(*found.groups()) if found else None


def admin_act_section(ref: str) -> AdminActSection | None:
    found = _ADMIN_ACT.fullmatch(ref.strip())
    return AdminActSection(*found.groups()) if found else None


def mapped(ref: SourceRef) -> bool:
    """The künye names a record of its category. Only statutes, administrative acts and
    decisions have a künye form; a source of another category cannot be required by künye."""
    if ref.category == "statute":
        return statute_article(ref.ref) is not None
    if ref.category == "admin_act":
        return admin_act_section(ref.ref) is not None
    if ref.category == "decision":
        return _DECISION.fullmatch(ref.ref.strip()) is not None
    return False
