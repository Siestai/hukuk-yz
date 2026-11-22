"""Genelge API (handoff 2026-11-22, A3): what a section of a genelge said on a date.

    GET /admin-acts/{ref}/sections/{section_no}?as_of=YYYY-MM-DD

`ref` is the genelge number with a dash for the slash ("2020-8" for 2020/8), `section_no` the
numbered heading ("2.6.2.5", "K2-B3-2.1.1", "giris"). The sections come from the review queue
(`app.loaders.admin_acts`): they have no approval path yet, so every one is unreviewed and which
of them may be read is decided by `unreviewed_bands` alone. A section outside those bands, a
`low` one and a rejected one are never returned.
"""

import re
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Db, kb_reader
from app.errors import ApiError
from app.models.common import (
    ADMIN_ACT_PARSER_NAME,
    Extraction,
    Review,
    ReviewDecision,
    Source,
)
from app.statutes import parse_date
from hukuk_ingest.admin_acts.citation import citation
from hukuk_ingest.admin_acts.split import INTRO
from hukuk_models import Band, ErrorCode

router = APIRouter(prefix="/admin-acts", tags=["admin-acts"], dependencies=[Depends(kb_reader)])

FOUND, GAP, NOT_IN_FORCE, UNKNOWN_SECTION = "found", "gap", "not_in_force", "unknown_section"
# No reviewer has approved a genelge section: there is no approval path for them yet.
REVIEW_STATUS: Literal["analyzed"] = "analyzed"
NEVER_READABLE: frozenset[Band] = frozenset({"low"})

_REF_RE = re.compile(r"^(\d{4})[-_/]0*(\d+)$")
_PART_RE = re.compile(r"^(k\d+)(?:-(b\d+))?(?:-(.+))?$", re.IGNORECASE)
_INTRO_ALIASES = {"giris", "giriş"}


def unreviewed_bands() -> frozenset[Band]:
    """The confidence bands in which an unreviewed genelge section may be read (K1 of the
    handoff). Empty: approved sources only, so nothing is readable yet. This is the one place
    to connect to the `KB_TEST_SOURCE_BANDS` setting; `low` is refused whatever it returns."""
    return frozenset()


UnreviewedBands = Annotated[frozenset[Band], Depends(unreviewed_bands)]


class SectionVersionOut(BaseModel):
    text: str
    heading: str | None
    valid_from: date | None
    valid_to: date | None  # None: no later wording is on file
    change_kind: Literal["original", "amended", "repealed"]
    amendments: list[dict[str, Any]]  # the notes in the text: kind, date, ref


class SectionGapOut(BaseModel):
    """An interval with no text on file: the section was amended and only its present wording is
    known. It never carries text (md. 25: a gap cannot be cited)."""

    model_config = ConfigDict(populate_by_name=True)

    from_: date | None = Field(alias="from")
    to: date
    reason: str


class SectionAsOf(BaseModel):
    """What a genelge section said on a date. Only fields that apply to the status are present:
    `version` for found / repealed, `gap` for gap, `reason` for unknown_section
    (`not_published`) and for a repealed section (`repealed`); the rest describe the section
    whenever it was readable."""

    status: Literal["found", "gap", "not_in_force", "unknown_section"]
    reason: Literal["repealed", "not_published"] | None = None
    ref: str | None = None  # "2020/8"
    section_no: str | None = None
    citation: str | None = None  # "2020/8 m.2.6.2.5"
    title: str | None = None
    version: SectionVersionOut | None = None
    gap: SectionGapOut | None = None
    children: list[str] | None = None  # the sections under this heading
    # `stale`: the date is after the newest date the file itself shows, so the text may have
    # been amended since.
    latest_snapshot_date: date | None = None
    stale: bool | None = None
    review_status: Literal["approved", "analyzed"] | None = None
    band: Band | None = None
    warnings: list[str] | None = None
    source_id: uuid.UUID | None = None
    extraction_id: uuid.UUID | None = None


def normalize_ref(raw: str) -> str:
    """ "2020/8" for it or the URL form "2020-8" ("2020_8", "2020-08"); anything else is only
    trimmed and left to the lookup."""
    raw = raw.strip()
    m = _REF_RE.match(raw)
    return f"{m.group(1)}/{m.group(2)}" if m else raw


def normalize_section_no(raw: str) -> str:
    """The stored section number for it or an alias: "2.6.2.5." and "m.2.6.2.5" are "2.6.2.5",
    "k2-b3-2.1" is "K2-B3-2.1", "giris" is the opening text."""
    raw = raw.strip().removeprefix("m.").rstrip(".-").strip()
    if raw.lower() in _INTRO_ALIASES or raw == INTRO:
        return INTRO
    if m := _PART_RE.match(raw):
        return "-".join(
            p for p in (m.group(1).upper(), (m.group(2) or "").upper(), m.group(3) or "") if p
        )
    return raw


def _allowed(bands: frozenset[Band]) -> list[str]:
    return sorted(bands - NEVER_READABLE)


async def act_is_readable(db: AsyncSession, ref: str, bands: frozenset[Band]) -> bool:
    """Whether the genelge has a section in the readable bands at all."""
    return bool(
        await db.scalar(
            select(
                exists().where(
                    Extraction.parser_name == ADMIN_ACT_PARSER_NAME,
                    Extraction.fields["act_ref"].as_string() == ref,
                    Extraction.confidence["band"].as_string().in_(_allowed(bands)),
                )
            )
        )
    )


async def section_as_of(
    db: AsyncSession, ref: str, section_no: str, as_of: date, bands: frozenset[Band]
) -> dict[str, Any]:
    """What the newest extraction of a section says for `as_of`, as `SectionAsOf`. The section
    is unknown (`not_published`) when it is not loaded, its band is not in `bands`, it is `low`
    or a reviewer rejected it. A `gap` result has no `version`, so it carries no text."""
    row = (
        await db.execute(
            select(Extraction, Source.title)
            .join(Source, Source.id == Extraction.source_id)
            .where(
                Extraction.parser_name == ADMIN_ACT_PARSER_NAME,
                Extraction.fields["act_ref"].as_string() == ref,
                Extraction.fields["section_no"].as_string() == section_no,
            )
            .order_by(Extraction.extracted_at.desc(), Extraction.id)
            .limit(1)
        )
    ).one_or_none()
    unknown = {"status": UNKNOWN_SECTION, "reason": "not_published"}
    if row is None:
        return unknown
    extraction, title = row
    band = extraction.confidence["band"]
    rejected = await db.scalar(
        select(
            exists().where(
                Review.extraction_id == extraction.id, Review.decision == ReviewDecision.reject
            )
        )
    )
    if band not in _allowed(bands) or rejected:
        return unknown
    f = extraction.fields
    latest = f["latest_snapshot_date"]
    base = {
        "ref": ref,
        "section_no": section_no,
        "citation": citation(ref, section_no),
        "title": title,
        "children": f["children"],
        "latest_snapshot_date": latest,
        "stale": as_of > date.fromisoformat(latest) if latest else None,
        "review_status": REVIEW_STATUS,
        "band": band,
        "warnings": extraction.warnings,
        "source_id": extraction.source_id,
        "extraction_id": extraction.id,
    }
    for v in f["versions"]:
        if v["valid_from"] and date.fromisoformat(v["valid_from"]) <= as_of:
            if v["change_kind"] == "repealed":
                return {"status": NOT_IN_FORCE, "reason": "repealed", "version": v, **base}
            return {"status": FOUND, "version": v, **base}
    for g in f["gaps"]:
        if (not g["from"] or date.fromisoformat(g["from"]) <= as_of) and as_of < date.fromisoformat(
            g["to"]
        ):
            return {"status": GAP, "gap": g, **base}
    return {"status": NOT_IN_FORCE, **base}


@router.get("/{ref}/sections/{section_no}", response_model_exclude_unset=True)
async def get_section(
    ref: str, section_no: str, as_of: str, db: Db, bands: UnreviewedBands
) -> SectionAsOf:
    day = parse_date(as_of)
    number = normalize_ref(ref)
    result = await section_as_of(db, number, normalize_section_no(section_no), day, bands)
    if result["status"] == UNKNOWN_SECTION and not await act_is_readable(db, number, bands):
        raise ApiError(404, ErrorCode.not_found, {"ref": number})
    return SectionAsOf.model_validate(result)
