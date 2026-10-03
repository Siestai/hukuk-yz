"""Knowledge-base writes that follow a human review (data-model.md §3-§4)."""

import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, Subquery, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import (
    Court,
    CourtLevel,
    Extraction,
    IngestFile,
    Jurisdiction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
    TextCompleteness,
    Verification,
)
from app.models.decision import LIVE_KEY_INDEX, Decision
from hukuk_models import Band, ReviewFilters

PARSER_NAME = "decisions"
Sort = Literal["score_asc", "score_desc", "sha256"]

# `decision` columns copied as they are from fields + edits; '' becomes NULL.
_NULLABLE_TEXT = ("esas_no", "karar_no", "outcome", "full_text", "editorial_summary")


async def publish_decision(
    session: AsyncSession, extraction_id: uuid.UUID, review_id: uuid.UUID
) -> uuid.UUID:
    """Copy an approved decision extraction (`fields` overlaid with `review.edits`) into
    `decision` and move its source to `approved`; the caller commits.

    `verification` is always `unverified`: the journal archive is a search aid, and only the
    official-source check (task 06) may make a decision citable. `approved` does not open it to
    citation. A live (court, bam_region, chamber, esas_no, karar_no) collision raises
    IntegrityError at flush."""
    review = await session.get(Review, review_id)
    extraction = await session.get(Extraction, extraction_id)
    if review is None or extraction is None or review.extraction_id != extraction_id:
        raise ValueError("review does not belong to the extraction")
    if review.decision is ReviewDecision.reject:
        raise ValueError("a rejected review cannot be published")
    source = (
        (
            await session.execute(
                select(Source)
                .where(Source.id == extraction.source_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if extraction.source_id
        else None
    )
    if source is None or source.category is not SourceCategory.decision:
        raise ValueError("extraction has no source of category 'decision'")
    if source.status is not RecordStatus.analyzed:
        raise ValueError("extraction has no source in status 'analyzed'")

    merged: dict[str, Any] = {**extraction.fields, **(review.edits or {})}
    if not merged["court"] or not merged["court_level"]:
        raise ValueError("court and court_level are required")
    decision = Decision(
        source_id=source.id,
        extraction_id=extraction_id,
        review_id=review_id,
        recorded_by=str(review.reviewer_id),
        court=Court(merged["court"]),
        court_level=CourtLevel(merged["court_level"]),
        chamber=merged["chamber"],
        source_chamber=merged["source_chamber"],
        bam_region=merged["bam_region"],
        decision_kind=merged["decision_kind"],
        decision_date=date.fromisoformat(merged["decision_date"])
        if merged["decision_date"]
        else None,
        jurisdiction=Jurisdiction(merged["jurisdiction"]) if merged["jurisdiction"] else None,
        related_articles=merged["related_articles"],
        keywords=merged["keywords"],
        text_completeness=TextCompleteness(merged["text_completeness"]),
        verification=Verification.unverified,
        journal_issue=merged["journal_issue"],
        journal_page=merged["journal_page"],
        **{name: merged[name] or None for name in _NULLABLE_TEXT},
    )
    session.add(decision)
    source.status = RecordStatus.approved
    await session.flush()
    return decision.id


def newest_extractions(source_id: uuid.UUID | None = None) -> Subquery:
    """The newest `decisions` extraction of every decision source (of one source if given), with
    what the queue filters and shows. None of it is read from `fields`: the generated columns
    of `extraction` hold it."""
    stmt = (
        select(
            Extraction.id,
            Extraction.source_id,
            IngestFile.sha256,
            Source.title,
            Source.status,
            Extraction.confidence,
            Extraction.court,
            Extraction.chamber,
            Extraction.esas_no,
            Extraction.karar_no,
            Extraction.decision_date,
            Extraction.journal_issue,
            Extraction.duplicate_group,
        )
        .ext(distinct_on(Extraction.source_id))
        .join(IngestFile, IngestFile.id == Extraction.file_id)
        .join(Source, Source.id == Extraction.source_id)
        .where(Extraction.parser_name == PARSER_NAME, Source.category == SourceCategory.decision)
        .order_by(Extraction.source_id, Extraction.extracted_at.desc(), Extraction.id)
    )
    if source_id:
        stmt = stmt.where(Extraction.source_id == source_id)
    return stmt.subquery()


def queue(
    band: Band | None,
    filters: ReviewFilters,
    sort: Sort = "score_asc",
    after: str | None = None,
) -> Select[Any]:
    """The review queue: newest extraction of every `analyzed` decision source, filtered and
    ordered (most suspicious first by default, ties by sha256; `sha256` is the stable order of
    bulk runs, of which `after` is the cursor: only records with a greater sha256)."""
    newest = newest_extractions()
    score = newest.c.confidence["score"].as_integer()
    conditions: list[ColumnElement[bool]] = [newest.c.status == RecordStatus.analyzed]
    if band:
        conditions.append(newest.c.confidence["band"].as_string() == band)
    if filters.court is not None:
        conditions.append(newest.c.court == filters.court)
    if filters.reason is not None:
        conditions.append(newest.c.confidence["reasons"].contains([filters.reason]))
    if filters.journal_issue is not None:
        conditions.append(newest.c.journal_issue == filters.journal_issue)
    if filters.q:
        conditions.append(
            or_(
                newest.c.esas_no.icontains(filters.q, autoescape=True),
                newest.c.karar_no.icontains(filters.q, autoescape=True),
                newest.c.title.icontains(filters.q, autoescape=True),
            )
        )
    if after is not None:
        conditions.append(newest.c.sha256 > after)
    order = {
        "score_asc": (score.asc(), newest.c.sha256),
        "score_desc": (score.desc(), newest.c.sha256),
        "sha256": (newest.c.sha256,),
    }[sort]
    return (
        select(
            *newest.c,
            newest.c.confidence["band"].as_string().label("band"),
            score.label("score"),
        )
        .where(*conditions)
        .order_by(*order)
    )


class StaleExtraction(ValueError):
    """The extraction is no longer what the reviewer saw: its source left review, a newer
    extraction replaced it, or it left the requested band."""


async def lock_pending(
    session: AsyncSession, extraction_id: uuid.UUID, band: Band | None = None
) -> Source:
    """Lock the source of the extraction (the row lock `publish_decision` takes) and check under
    it that the source is still `analyzed`, that the extraction is still the newest of its
    source and, if `band` is given, still in that band. Raises StaleExtraction otherwise; the
    lock lasts to the end of the transaction."""
    source_id = (
        await session.execute(select(Extraction.source_id).where(Extraction.id == extraction_id))
    ).scalar_one_or_none()
    if source_id is None:
        raise ValueError("extraction has no source")
    source = (
        await session.execute(
            select(Source)
            .where(Source.id == source_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if source.status is not RecordStatus.analyzed:
        raise StaleExtraction("source is no longer in review")
    newest = newest_extractions(source_id)
    row = (
        await session.execute(select(newest.c.id, newest.c.confidence["band"].as_string()))
    ).one_or_none()
    if row is None:
        raise ValueError("extraction has no source of category 'decision'")
    if row[0] != extraction_id:
        raise StaleExtraction("source has a newer extraction")
    if band is not None and row[1] != band:
        raise StaleExtraction(f"extraction is no longer in band {band}")
    return source


def _violated_constraint(exc: IntegrityError) -> str | None:
    return getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)


@asynccontextmanager
async def _reviewed(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ReviewDecision,
    edits: dict[str, Any] | None,
    note: str | None,
    band: Band | None,
) -> AsyncIterator[tuple[Source, Review]]:
    """The one path of every review: in a savepoint, lock and check the extraction
    (`lock_pending`) and write the `review` row; the body does the rest. An IntegrityError other
    than the live-key collision (an unknown reviewer, say) becomes a ValueError; the collision
    stays an IntegrityError. On any error the savepoint is rolled back and nothing is left."""
    try:
        async with session.begin_nested():
            source = await lock_pending(session, extraction_id, band)
            review = Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer_id,
                decision=decision,
                edits=edits,
                note=note,
            )
            session.add(review)
            await session.flush()
            yield source, review
            await session.flush()
    except IntegrityError as exc:
        if (name := _violated_constraint(exc)) == LIVE_KEY_INDEX:
            raise
        raise ValueError(f"database constraint violated: {name}") from exc


async def approve_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ReviewDecision = ReviewDecision.approve,
    edits: dict[str, Any] | None = None,
    note: str | None = None,
    band: Band | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """`review` row + `publish_decision`; returns (review_id, decision_id). Raises
    StaleExtraction (see `lock_pending`), ValueError (not publishable) or IntegrityError (live-key
    collision); the caller commits."""
    async with _reviewed(session, extraction_id, reviewer_id, decision, edits, note, band) as (
        _,
        review,
    ):
        return review.id, await publish_decision(session, extraction_id, review.id)


async def reject_extraction(
    session: AsyncSession, extraction_id: uuid.UUID, reviewer_id: uuid.UUID, note: str
) -> uuid.UUID:
    """`review` row (reject) and the source `rejected`; returns the review id. Raises like
    `approve_extraction`; the caller commits."""
    async with _reviewed(
        session, extraction_id, reviewer_id, ReviewDecision.reject, None, note, None
    ) as (source, review):
        source.status = RecordStatus.rejected
    return review.id


@dataclass
class BatchResult:
    published: int = 0
    conflicts: list[uuid.UUID] = field(default_factory=list)
    failed: list[tuple[uuid.UUID, str]] = field(default_factory=list)


async def publish_batch(
    session: AsyncSession,
    extraction_ids: Sequence[uuid.UUID],
    reviewer_id: uuid.UUID,
    band: Band,
) -> BatchResult:
    """Approve and publish each extraction in its own savepoint: a live-key collision goes to
    `conflicts`, any other record `approve_extraction` refuses (not publishable, stale, no
    longer in `band`) to `failed` (id, reason); neither stops the run. The caller commits."""
    result = BatchResult()
    for extraction_id in extraction_ids:
        try:
            await approve_extraction(session, extraction_id, reviewer_id, band=band)
            result.published += 1
        except IntegrityError:
            result.conflicts.append(extraction_id)
        except ValueError as exc:
            result.failed.append((extraction_id, str(exc)))
    return result
