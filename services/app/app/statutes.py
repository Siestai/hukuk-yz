"""Statute API (task 11b): what an article said on a date. A published article is read by
`app.kb.article_as_of`. One that no reviewer has approved yet is read from the timeline of its
newest extraction, only in the confidence bands of `KB_TEST_SOURCE_BANDS` (decision K1; never
`low`, never a rejected one), and says so: `review_status` "analyzed" and its `band`."""

import re
from collections.abc import Sequence
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Db, kb_reader
from app.errors import ApiError
from app.kb import (
    article_as_of,
    format_amending_ref,
    statute_article_status,
    statute_is_published,
    version_evidence,
)
from app.models.common import STATUTE_PARSER_NAME, Extraction
from app.settings import Settings, TestBand, get_settings
from hukuk_ingest.statutes import timeline
from hukuk_models import ArticleAsOf, ErrorCode

router = APIRouter(prefix="/statutes", tags=["statutes"], dependencies=[Depends(kb_reader)])

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


async def unreviewed_article_as_of(
    db: AsyncSession, number: str, article_no: str, day: date, bands: Sequence[TestBand]
) -> dict[str, Any] | None:
    """What the newest extraction of an article says about `day`, in the shape of
    `article_as_of` plus `review_status` and `band`; None unless that extraction waits for its
    review in one of `bands`. A version without a start date is not read: nobody can say it was
    in force on the day, nor that it was not, so a day that only such a version could cover is
    None too. `version.id` is absent: there is no published row, so `extraction_id` names the
    record that was read."""
    newest = (
        await db.execute(
            select(Extraction)
            .where(
                Extraction.parser_name == STATUTE_PARSER_NAME,
                Extraction.fields["statute_number"].as_string() == number,
                Extraction.fields["article_no"].as_string() == article_no,
            )
            .order_by(Extraction.extracted_at.desc(), Extraction.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if newest is None or newest.confidence.get("band") not in bands:
        return None
    if await statute_article_status(db, newest) != "pending":
        return None
    versions = newest.fields["versions"]
    dated = [v for v in versions if v["valid_from"]]
    result = timeline.as_of({**newest.fields, "versions": dated}, day)
    if len(dated) < len(versions) and "version" not in result and "gap" not in result:
        return None  # the undated version may cover the day: not "not in force"
    if version := result.get("version"):
        result["version"] = {
            **version,
            "amending_ref": format_amending_ref(version["amending_ref"]),
            "evidence": version_evidence(version),
        }
    return {
        **result,
        "review_status": "analyzed",
        "band": newest.confidence["band"],
        "extraction_id": newest.id,
    }


@router.get("/{number}/articles/{article_no:path}", response_model_exclude_unset=True)
async def get_article(
    number: str,
    article_no: str,
    as_of: str,
    db: Db,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArticleAsOf:
    day = parse_date(as_of)
    article = normalize_article_no(article_no)
    result = await article_as_of(db, number, article, day)
    if result["status"] != timeline.UNKNOWN_ARTICLE:
        return ArticleAsOf.model_validate({**result, "review_status": "approved"})
    if settings.kb_test_source_bands:
        unreviewed = await unreviewed_article_as_of(
            db, number, article, day, settings.kb_test_source_bands
        )
        if unreviewed:
            return ArticleAsOf.model_validate(unreviewed)
    if not await statute_is_published(db, number):
        raise ApiError(404, ErrorCode.statute_not_found, {"number": number})
    return ArticleAsOf.model_validate(result)
