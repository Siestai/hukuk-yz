"""Statute API (task 11b): what a published article said on a date. HTTP only: the query is
`app.kb.article_as_of`."""

import re
from datetime import date

from fastapi import APIRouter, Depends

from app.auth import Db, current_user
from app.errors import ApiError
from app.kb import article_as_of, statute_is_published
from hukuk_ingest.statutes.timeline import UNKNOWN_ARTICLE
from hukuk_models import ArticleAsOf, ErrorCode

router = APIRouter(prefix="/statutes", tags=["statutes"], dependencies=[Depends(current_user)])

# "gecici-4" / "ek-2" / "18-a" / "gecici-79-2" are accepted next to the canonical "Geçici 4" /
# "Ek 2" / "18/A" / "Geçici 79 (2)"; the match is on the Turkish-lowercased text.
_ALIAS_RE = re.compile(
    r"^(?:(ek|ge[cç][iı]c[iı])[-_ ])?(\d+)"
    r"(?:[-/]?([a-zçğıöşü])|[-_ ]?\((\d+)\)|[-_](\d+))?$"
)
_PREFIXES = {"ek": "Ek", "geçici": "Geçici"}
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _lower_tr(text: str) -> str:
    """Lowercase with the Turkish dotted/dotless i (İ -> i, I -> ı)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _upper_tr(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def normalize_article_no(raw: str) -> str:
    """The canonical article number ("18", "18/A", "Ek 2", "Geçici 4", "Geçici 79 (2)") for it or
    an alias (any case, ASCII or Turkish letters); anything else is only trimmed and left to the
    lookup."""
    raw = " ".join(raw.split())
    if not (m := _ALIAS_RE.match(_lower_tr(raw))):
        return raw
    prefix, number, letter, bracketed, dashed = m.groups()
    out = f"{number}/{_upper_tr(letter)}" if letter else number
    if sub := bracketed or dashed:
        out = f"{out} ({sub})"
    if not prefix:
        return out
    return f"{_PREFIXES['ek' if prefix == 'ek' else 'geçici']} {out}"


def parse_date(raw: str) -> date:
    try:
        if _DATE_RE.match(raw):
            return date.fromisoformat(raw)
    except ValueError:
        pass
    raise ApiError(422, ErrorCode.invalid_date, {"field": "as_of"})


@router.get("/{number}/articles/{article_no:path}", response_model_exclude_unset=True)
async def get_article(number: str, article_no: str, as_of: str, db: Db) -> ArticleAsOf:
    day = parse_date(as_of)
    result = await article_as_of(db, number, normalize_article_no(article_no), day)
    if result["status"] == UNKNOWN_ARTICLE and not await statute_is_published(db, number):
        raise ApiError(404, ErrorCode.statute_not_found, {"number": number})
    return ArticleAsOf.model_validate(result)
