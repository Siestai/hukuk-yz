"""Genelge API (handoff 2026-11-22, A3): what a section of a genelge said on a date.

    GET /admin-acts/{ref}/sections/{section_no}?as_of=YYYY-MM-DD
    GET /admin-acts/{ref}/sections

`ref` is the genelge number with a dash for the slash ("2020-8" for 2020/8), `section_no` the
numbered heading ("2.6.2.5", "K2-B3-2.1.1", "giris"). The sections come from the review queue
(`app.loaders.admin_acts`): they have no approval path yet, so every one is unreviewed and which
of them may be read is decided by `unreviewed_bands` alone (the `KB_TEST_SOURCE_BANDS` setting).
A section outside those bands, a `low` one and a rejected one are never returned. The list names
the readable sections of a genelge, for a künye without a section ("2020/8").
"""

import re
from collections.abc import Collection
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import Select, exists, select
from sqlalchemy.dialects.postgresql import distinct_on
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
from app.settings import Settings, get_settings
from app.statutes import parse_date
from hukuk_ingest.admin_acts.citation import citation
from hukuk_ingest.admin_acts.split import INTRO
from hukuk_models import AdminActSectionAsOf, AdminActSections, Band, ErrorCode

router = APIRouter(prefix="/admin-acts", tags=["admin-acts"], dependencies=[Depends(kb_reader)])

FOUND, GAP, NOT_IN_FORCE, UNKNOWN_SECTION = "found", "gap", "not_in_force", "unknown_section"
# No reviewer has approved a genelge section: there is no approval path for them yet.
REVIEW_STATUS: Literal["analyzed"] = "analyzed"
NEVER_READABLE: frozenset[Band] = frozenset({"low"})

_REF_RE = re.compile(r"^(\d{4})[-_/]0*(\d+)$")
_PART_RE = re.compile(r"^(k\d+)(?:-(b\d+))?(?:-(.+))?$", re.IGNORECASE)
_INTRO_ALIASES = {"giris", "giriş"}


def unreviewed_bands(
    settings: Annotated[Settings, Depends(get_settings)],
) -> frozenset[Band]:
    """The confidence bands in which an unreviewed genelge section may be read: those of
    `KB_TEST_SOURCE_BANDS` (decision K1). Empty: approved sources only, so nothing is readable
    yet. `low` is refused whatever this returns."""
    return frozenset(settings.kb_test_source_bands)


UnreviewedBands = Annotated[frozenset[Band], Depends(unreviewed_bands)]


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
    """What the newest extraction of a section says for `as_of`, as `AdminActSectionAsOf`. The
    section is unknown (`not_published`) when it is not loaded, its band is not in `bands`, it is
    `low` or a reviewer rejected it. A `gap` result has no `version`, so it carries no text."""
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


def readable_section_ids(bands: Collection[str], ref: str | None = None) -> Select[Any]:
    """Ids of the extractions a genelge section is read from (of one genelge if `ref` is given):
    the newest extraction of each section, when its band is in `bands` (never `low`) and no
    reviewer rejected it. An older extraction of a reloaded section is not one of them."""
    act_ref = Extraction.fields["act_ref"].as_string()
    section_no = Extraction.fields["section_no"].as_string()
    newest = (
        select(Extraction.id)
        .ext(distinct_on(act_ref, section_no))
        .where(Extraction.parser_name == ADMIN_ACT_PARSER_NAME)
        .order_by(act_ref, section_no, Extraction.extracted_at.desc(), Extraction.id)
    )
    if ref is not None:
        newest = newest.where(act_ref == ref)
    return select(Extraction.id).where(
        Extraction.id.in_(newest),
        Extraction.confidence["band"].as_string().in_(sorted(set(bands) - NEVER_READABLE)),
        ~exists().where(
            Review.extraction_id == Extraction.id, Review.decision == ReviewDecision.reject
        ),
    )


async def readable_sections(
    db: AsyncSession, ref: str, bands: frozenset[Band]
) -> dict[str, Any] | None:
    """The sections of a genelge that `section_as_of` would return, in document order; None when
    there is none."""
    rows = (
        await db.execute(
            select(Extraction, Source.title)
            .join(Source, Source.id == Extraction.source_id)
            .where(Extraction.id.in_(readable_section_ids(bands, ref)))
            .order_by(Extraction.fields["ordinal"].as_integer())
        )
    ).all()
    if not rows:
        return None
    return {
        "ref": ref,
        "title": rows[0].title,
        "sections": [
            {
                "section_no": e.fields["section_no"],
                "heading": e.fields["heading"],
                "citation": citation(ref, e.fields["section_no"]),
                "children": e.fields["children"],
                "review_status": REVIEW_STATUS,
                "band": e.confidence["band"],
                "extraction_id": e.id,
            }
            for e, _ in rows
        ],
    }


@router.get("/{ref}/sections")
async def list_sections(ref: str, db: Db, bands: UnreviewedBands) -> AdminActSections:
    number = normalize_ref(ref)
    result = await readable_sections(db, number, bands)
    if result is None:
        raise ApiError(404, ErrorCode.not_found, {"ref": number})
    return AdminActSections.model_validate(result)


@router.get("/{ref}/sections/{section_no}", response_model_exclude_unset=True)
async def get_section(
    ref: str, section_no: str, as_of: str, db: Db, bands: UnreviewedBands
) -> AdminActSectionAsOf:
    day = parse_date(as_of)
    number = normalize_ref(ref)
    result = await section_as_of(db, number, normalize_section_no(section_no), day, bands)
    if result["status"] == UNKNOWN_SECTION and not await act_is_readable(db, number, bands):
        raise ApiError(404, ErrorCode.not_found, {"ref": number})
    return AdminActSectionAsOf.model_validate(result)
