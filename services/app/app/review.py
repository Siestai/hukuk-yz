"""Review API of decision extractions (task 09): queue, detail, approve / edit / reject and
bulk approval of the high band.

The queue is the newest `decisions` extraction of every source still `analyzed`. `queue()` and
`publish_batch()` are the one query and the one publish path of both this API and the
`--approve-band` CLI of the loader.
"""

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, Select, Subquery, func, literal, literal_column, or_, select
from sqlalchemy.dialects.postgresql import JSONB, distinct_on
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Db, require_role
from app.kb import publish_decision
from app.models.common import (
    Court,
    Extraction,
    IngestFile,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
)
from app.models.decision import Decision
from app.models.user import AppUser
from hukuk_models import (
    Band,
    BulkApproveRequest,
    BulkApproveResponse,
    BulkFailure,
    Confidence,
    DuplicateOut,
    ReasonCount,
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewDetail,
    ReviewFilters,
    ReviewListItem,
    ReviewListResponse,
    ReviewOut,
    ReviewSummary,
)

PARSER_NAME = "decisions"
TOP_REASONS = 15

Sort = Literal["score_asc", "score_desc"]

_reviewer = require_role("reviewer")
Reviewer = Annotated[AppUser, Depends(_reviewer)]
router = APIRouter(prefix="/review/decisions", tags=["review"], dependencies=[Depends(_reviewer)])


def _slim(fields: Any) -> Any:
    """`fields` without the two long texts."""
    return fields.op("-", return_type=JSONB)(
        literal_column("ARRAY['full_text', 'editorial_summary']")
    )


def newest_extractions(source_id: uuid.UUID | None = None, with_slim: bool = False) -> Subquery:
    """The newest `decisions` extraction of every decision source (of one source if given).
    `fields` hold the decision text (some 25 KB per row, out of line), so the subquery reads
    them only on request: `slim` (`fields` without the long texts, cut once per row) is there
    for the filters that need a field."""
    stmt = (
        select(
            Extraction.id,
            Extraction.source_id,
            IngestFile.sha256,
            Source.title,
            Source.status,
            Extraction.confidence,
        )
        .ext(distinct_on(Extraction.source_id))
        .join(IngestFile, IngestFile.id == Extraction.file_id)
        .join(Source, Source.id == Extraction.source_id)
        .where(Extraction.parser_name == PARSER_NAME, Source.category == SourceCategory.decision)
        .order_by(Extraction.source_id, Extraction.extracted_at.desc(), Extraction.id)
    )
    if with_slim:
        stmt = stmt.add_columns(_slim(Extraction.fields).label("slim"))
    if source_id:
        stmt = stmt.where(Extraction.source_id == source_id)
    return stmt.subquery()


def queue(band: Band | None, filters: ReviewFilters, sort: Sort = "score_asc") -> Select[Any]:
    """The review queue: newest extraction of every `analyzed` decision source, filtered and
    ordered (most suspicious first by default; ties by sha256). Rows carry no fields."""
    newest = newest_extractions(
        with_slim=filters.court is not None or filters.journal_issue is not None or bool(filters.q)
    )
    score = newest.c.confidence["score"].as_integer()
    conditions: list[ColumnElement[bool]] = [newest.c.status == RecordStatus.analyzed]
    if band:
        conditions.append(newest.c.confidence["band"].as_string() == band)
    if filters.court is not None:
        conditions.append(newest.c.slim["court"].as_string() == filters.court)
    if filters.reason is not None:
        conditions.append(newest.c.confidence["reasons"].contains([filters.reason]))
    if filters.journal_issue is not None:
        conditions.append(newest.c.slim["journal_issue"].as_integer() == filters.journal_issue)
    if filters.q:
        conditions.append(
            or_(
                newest.c.slim["esas_no"].as_string().icontains(filters.q, autoescape=True),
                newest.c.slim["karar_no"].as_string().icontains(filters.q, autoescape=True),
                newest.c.title.icontains(filters.q, autoescape=True),
            )
        )
    return (
        select(
            newest.c.id,
            newest.c.source_id,
            newest.c.sha256,
            newest.c.title,
            newest.c.confidence,
            newest.c.confidence["band"].as_string().label("band"),
            score.label("score"),
        )
        .where(*conditions)
        .order_by(score.asc() if sort == "score_asc" else score.desc(), newest.c.sha256)
    )


async def approve_extraction(
    session: AsyncSession,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: ReviewDecision = ReviewDecision.approve,
    edits: dict[str, Any] | None = None,
    note: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """`review` row + `publish_decision` in a savepoint; returns (review_id, decision_id). On
    IntegrityError (live-key collision) or ValueError (not publishable) the savepoint is rolled
    back and nothing is left behind; the caller commits."""
    async with session.begin_nested():
        review = Review(
            extraction_id=extraction_id,
            reviewer_id=reviewer_id,
            decision=decision,
            edits=edits,
            note=note,
        )
        session.add(review)
        await session.flush()
        return review.id, await publish_decision(session, extraction_id, review.id)


@dataclass
class BatchResult:
    published: int = 0
    conflicts: list[uuid.UUID] = field(default_factory=list)
    failed: list[tuple[uuid.UUID, str]] = field(default_factory=list)


async def publish_batch(
    session: AsyncSession, extraction_ids: Sequence[uuid.UUID], reviewer_id: uuid.UUID
) -> BatchResult:
    """Approve and publish each extraction in its own savepoint: a live-key collision goes to
    `conflicts`, any other record `publish_decision` refuses to `failed` (id, reason); neither
    stops the run. The caller commits."""
    result = BatchResult()
    for extraction_id in extraction_ids:
        try:
            await approve_extraction(session, extraction_id, reviewer_id)
            result.published += 1
        except IntegrityError:
            result.conflicts.append(extraction_id)
        except ValueError as exc:
            result.failed.append((extraction_id, str(exc)))
    return result


def _list_item(row: Any, slim: dict[str, Any]) -> ReviewListItem:
    return ReviewListItem(
        extraction_id=row.id,
        source_id=row.source_id,
        title=row.title,
        court=slim["court"],
        chamber=slim["chamber"],
        esas_no=slim["esas_no"],
        karar_no=slim["karar_no"],
        decision_date=slim["decision_date"],
        journal_issue=slim["journal_issue"],
        band=row.band,
        score=row.score,
        reasons=row.confidence["reasons"],
        duplicate_group=slim.get("duplicate_group"),
    )


@router.get("")
async def list_decisions(
    db: Db,
    band: Band | None = None,
    court: str | None = None,
    reason: str | None = None,
    journal_issue: int | None = None,
    q: str | None = None,
    sort: Sort = "score_asc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewListResponse:
    filters = ReviewFilters(court=court, reason=reason, journal_issue=journal_issue, q=q)
    stmt = queue(band, filters, sort)
    # One scan for page and total: a filter on a field reads every `fields` once.
    rows = (
        await db.execute(
            stmt.add_columns(func.count().over().label("total")).limit(limit).offset(offset)
        )
    ).all()
    if rows:
        total = rows[0].total
    elif offset:  # past the last page
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    else:
        total = 0
    slims: dict[uuid.UUID, dict[str, Any]] = dict(
        (
            await db.execute(
                select(Extraction.id, _slim(Extraction.fields)).where(
                    Extraction.id.in_([row.id for row in rows])
                )
            )
        ).all()
    )
    return ReviewListResponse(total=total, items=[_list_item(r, slims[r.id]) for r in rows])


@router.get("/summary")
async def summary(db: Db) -> ReviewSummary:
    pending_query = queue(None, ReviewFilters())
    pending = (await db.execute(pending_query)).all()
    court = Extraction.fields["court"].as_string().label("court")
    by_court = (
        await db.execute(
            select(court, func.count())
            .where(Extraction.id.in_(select(pending_query.subquery().c.id)))
            .group_by(court)
        )
    ).all()
    reasons = Counter(r for row in pending for r in row.confidence["reasons"])
    bands = Counter(row.band for row in pending)
    counts = dict(
        (
            await db.execute(
                select(Review.decision, func.count())
                .join(Extraction, Extraction.id == Review.extraction_id)
                .join(Source, Source.id == Extraction.source_id)
                .where(Source.category == SourceCategory.decision)
                .group_by(Review.decision)
            )
        ).all()
    )
    return ReviewSummary(
        by_band={"high": bands["high"], "medium": bands["medium"], "low": bands["low"]},
        by_court=dict(by_court),
        top_reasons=[
            ReasonCount(reason=reason, count=count)
            for reason, count in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))[
                :TOP_REASONS
            ]
        ],
        approved=counts.get(ReviewDecision.approve, 0) + counts.get(ReviewDecision.edit, 0),
        rejected=counts.get(ReviewDecision.reject, 0),
    )


@router.post("/bulk-approve")
async def bulk_approve(body: BulkApproveRequest, user: Reviewer, db: Db) -> BulkApproveResponse:
    stmt = queue(body.band, body.filters)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    if total != body.expected_count:
        raise HTTPException(
            status_code=409,
            detail=f"Eşleşen kayıt sayısı değişti: {total} (beklenen {body.expected_count})",
        )
    ids = [row.id for row in (await db.execute(stmt.limit(body.limit))).all()]
    result = await publish_batch(db, ids, user.id)
    await db.commit()
    return BulkApproveResponse(
        published=result.published,
        conflicts=result.conflicts,
        failed=[BulkFailure(extraction_id=i, reason=reason) for i, reason in result.failed],
        remaining=total - result.published,
    )


@router.get("/{extraction_id}")
async def get_decision(extraction_id: uuid.UUID, db: Db) -> ReviewDetail:
    extraction, source = await _decision_extraction(db, extraction_id)
    duplicates: list[DuplicateOut] = []
    if group := extraction.fields.get("duplicate_group"):
        newest = newest_extractions(with_slim=True)
        rows = await db.execute(
            select(
                Extraction.id,
                Extraction.confidence,
                func.length(Extraction.fields["full_text"].as_string()),
            )
            .join(newest, newest.c.id == Extraction.id)
            .where(
                newest.c.slim["duplicate_group"]["key"] == literal(group["key"], JSONB),
                Extraction.id != extraction_id,
            )
            .order_by(Extraction.id)
        )
        duplicates = [
            DuplicateOut(
                extraction_id=id_, band=conf["band"], score=conf["score"], text_length=length
            )
            for id_, conf, length in rows
        ]
    reviews = (
        (
            await db.execute(
                select(Review)
                .where(Review.extraction_id == extraction_id)
                .order_by(Review.reviewed_at, Review.id)
            )
        )
        .scalars()
        .all()
    )
    return ReviewDetail(
        extraction_id=extraction.id,
        source_id=source.id,
        source_status=source.status.value,
        title=source.title,
        fields=extraction.fields,
        warnings=extraction.warnings,
        confidence=Confidence(**extraction.confidence),
        raw_text_ref=extraction.raw_text_ref,
        duplicates=duplicates,
        reviews=[
            ReviewOut(
                id=r.id,
                reviewer_id=r.reviewer_id,
                decision=r.decision.value,
                edits=r.edits,
                note=r.note,
                reviewed_at=r.reviewed_at,
            )
            for r in reviews
        ],
    )


@router.post("/{extraction_id}")
async def act(
    extraction_id: uuid.UUID, body: ReviewActionRequest, user: Reviewer, db: Db
) -> ReviewActionResponse:
    extraction, source = await _decision_extraction(db, extraction_id)
    # Lock the source: a concurrent action on it waits here and then sees the new status.
    await db.refresh(source, with_for_update=True)
    if source.status is not RecordStatus.analyzed:
        raise HTTPException(status_code=409, detail="Kayıt artık incelemede değil")
    newest = newest_extractions(source.id)
    if (await db.execute(select(newest.c.id))).scalar_one() != extraction_id:
        raise HTTPException(status_code=409, detail="Kaynağın daha yeni bir extraction'ı var")

    if body.action == "reject":
        review = Review(
            extraction_id=extraction_id,
            reviewer_id=user.id,
            decision=ReviewDecision.reject,
            note=body.note,
        )
        db.add(review)
        source.status = RecordStatus.rejected
        await db.flush()
        await db.commit()
        return ReviewActionResponse(review_id=review.id, decision_id=None, source_status="rejected")

    edits = (
        body.edits.model_dump(mode="json", exclude_unset=True)
        if body.action == "edit" and body.edits
        else None
    )
    merged = {**extraction.fields, **(edits or {})}
    try:
        review_id, decision_id = await approve_extraction(
            db, extraction_id, user.id, ReviewDecision(body.action), edits, body.note
        )
    except IntegrityError:
        conflict = await _live_conflict(db, merged)
        if conflict is None:
            raise
        raise HTTPException(
            status_code=409,
            detail={"message": "Aynı künyeli canlı karar var", "decision_id": str(conflict)},
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    await db.commit()
    return ReviewActionResponse(
        review_id=review_id, decision_id=decision_id, source_status="approved"
    )


async def _decision_extraction(
    db: AsyncSession, extraction_id: uuid.UUID
) -> tuple[Extraction, Source]:
    """The extraction of a decision source with its source, or 404."""
    row = (
        await db.execute(
            select(Extraction, Source)
            .join(Source, Source.id == Extraction.source_id)
            .where(
                Extraction.id == extraction_id,
                Extraction.parser_name == PARSER_NAME,
                Source.category == SourceCategory.decision,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Extraction bulunamadı")
    extraction, source = row
    return extraction, source


async def _live_conflict(db: AsyncSession, merged: dict[str, Any]) -> uuid.UUID | None:
    """Id of the live decision with the key (court, bam_region, chamber, esas_no, karar_no)."""
    return (
        await db.execute(
            select(Decision.id).where(
                Decision.superseded_at.is_(None),
                Decision.court == Court(merged["court"]),
                Decision.bam_region == merged["bam_region"],
                Decision.chamber == merged["chamber"],
                Decision.esas_no == merged["esas_no"],
                Decision.karar_no == merged["karar_no"],
            )
        )
    ).scalar_one_or_none()
