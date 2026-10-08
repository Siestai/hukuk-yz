"""Statute API (task 11b): what a published article said on a date. HTTP only: the query is
`app.kb.article_as_of`."""

import re
from datetime import date

from fastapi import APIRouter, Depends

from app.auth import Db, current_user
from app.errors import ApiError
from app.kb import article_as_of, statute_is_published
from hukuk_models import ArticleAsOf, ErrorCode

router = APIRouter(prefix="/statutes", tags=["statutes"], dependencies=[Depends(current_user)])

# "gecici-4" / "ek-2" / "18-a" are accepted next to the canonical "Geçici 4" / "Ek 2" / "18/A".
_ALIAS_RE = re.compile(r"^(?:(ek|gecici)[-_ ])?(\d+)(?:[-/]?([a-z]))?$", re.IGNORECASE)
_PREFIXES = {"ek": "Ek", "gecici": "Geçici"}


def normalize_article_no(raw: str) -> str:
    """The canonical article number ("18", "18/A", "Ek 2", "Geçici 4") for it or an ASCII alias;
    anything else is only trimmed and left to the lookup."""
    raw = " ".join(raw.split())
    if not (m := _ALIAS_RE.match(raw)):
        return raw
    prefix, number, letter = m.groups()
    out = f"{number}/{letter.upper()}" if letter else number
    return f"{_PREFIXES[prefix.lower()]} {out}" if prefix else out


def parse_date(raw: str) -> date:
    try:
        if len(raw) == 10:
            return date.fromisoformat(raw)
    except ValueError:
        pass
    raise ApiError(422, ErrorCode.invalid_date, {"field": "as_of"})


@router.get("/{number}/articles/{article_no:path}", response_model_exclude_unset=True)
async def get_article(number: str, article_no: str, as_of: str, db: Db) -> ArticleAsOf:
    day = parse_date(as_of)
    if not await statute_is_published(db, number):
        raise ApiError(404, ErrorCode.statute_not_found, {"number": number})
    return ArticleAsOf.model_validate(
        await article_as_of(db, number, normalize_article_no(article_no), day)
    )
