"""Review API of statute article timelines (task 11c-1): queue, detail, approve / reject and bulk
approval of the high band. Same shape as the decision review (`app.review`): HTTP only, the queue
query and the writes after a review are in `app.kb`, shared with the `--approve-band` CLI of the
statute loader. The review unit is the article: one `statutes` extraction holds its whole
timeline, and a decision extraction id is a 404 here (as a statute one is there)."""

import uuid
from datetime import date
from pathlib import PurePath
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Db
from app.errors import ApiError
from app.kb import (
    STATUTE_PARSER_NAME,
    StaleExtraction,
    approve_statute_article,
    format_amending_ref,
    publish_statute_batch,
    reject_statute_article,
    statute_article_status,
    statute_queue,
    unpublished_statute_articles,
    version_evidence,
)
from app.models.common import Extraction, Review, Source, SourceCategory
from app.models.statute import Statute, StatuteArticle, StatuteArticleVersion
from app.models.user import AppUser
from app.review_common import Limit, Offset, Reviewer, page, reviewer_check
from app.review_common import bulk_approve as run_bulk_approve
from hukuk_models import (
    Band,
    BulkApproveResponse,
    ErrorCode,
    ListStatus,
    ReviewOut,
    StatuteBulkApproveRequest,
    StatuteReviewActionRequest,
    StatuteReviewActionResponse,
    StatuteReviewDetail,
    StatuteReviewListItem,
    StatuteReviewListResponse,
    StatuteReviewSummary,
    StatuteSnapshotOut,
    StatuteSummaryRow,
    TimelineEntry,
    TimelineGap,
    TimelineVersion,
)

router = APIRouter(
    prefix="/review/statutes", tags=["review-statutes"], dependencies=[Depends(reviewer_check)]
)


@router.get("")
async def list_articles(
    db: Db,
    statute: str | None = None,
    band: Band | None = None,
    status: ListStatus = "pending",
    q: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> StatuteReviewListResponse:
    total, rows = await page(db, statute_queue(band, status, statute, q), limit, offset)
    return StatuteReviewListResponse(
        total=total,
        items=[
            StatuteReviewListItem(
                extraction_id=r.id,
                source_id=r.source_id,
                statute_number=r.statute_number,
                article_no=r.article_no,
                ordinal=r.ordinal,
                heading=r.heading,
                band=r.band,
                reasons=r.reasons,
                version_count=r.version_count,
                gap_count=r.gap_count,
                latest_snapshot_date=date.fromisoformat(r.latest_snapshot_date),
                status=r.status,
            )
            for r in rows
        ],
    )


@router.get("/summary")
async def summary(db: Db) -> StatuteReviewSummary:
    articles = statute_queue(status="all").subquery()
    rows = (
        await db.execute(
            select(articles.c.statute_number, articles.c.band, articles.c.status, func.count())
            .group_by(articles.c.statute_number, articles.c.band, articles.c.status)
            .order_by(articles.c.statute_number, articles.c.band, articles.c.status)
        )
    ).all()
    return StatuteReviewSummary(
        items=[
            StatuteSummaryRow(statute_number=n, band=b, status=s, count=c) for n, b, s, c in rows
        ]
    )


@router.post("/bulk-approve")
async def bulk_approve(
    body: StatuteBulkApproveRequest, user: Reviewer, db: Db
) -> BulkApproveResponse:
    return await run_bulk_approve(
        db,
        band=body.band,
        cursor=body.cursor,
        expected_count=body.expected_count,
        limit=body.limit,
        pending=lambda after: unpublished_statute_articles(body.band, body.statute, after),
        cursor_of=lambda row: row.id,
        publish=lambda ids: publish_statute_batch(db, ids, user.id, body.band),
    )


@router.get("/{extraction_id}")
async def get_article(extraction_id: uuid.UUID, db: Db) -> StatuteReviewDetail:
    extraction, source = await _statute_extraction(db, extraction_id)
    fields = extraction.fields
    number = fields["statute_number"]
    reviews = (
        await db.execute(
            select(Review, AppUser.display_name)
            .outerjoin(AppUser, AppUser.id == Review.reviewer_id)
            .where(Review.extraction_id == extraction_id)
            .order_by(Review.reviewed_at, Review.id)
        )
    ).all()
    live_extraction_id = (
        await db.execute(
            select(StatuteArticleVersion.extraction_id)
            .join(StatuteArticle, StatuteArticle.id == StatuteArticleVersion.article_id)
            .join(Statute, Statute.id == StatuteArticle.statute_id)
            .where(
                Statute.number == number,
                StatuteArticle.article_no == fields["article_no"],
                StatuteArticleVersion.superseded_at.is_(None),
                StatuteArticleVersion.extraction_id != extraction_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return StatuteReviewDetail(
        extraction_id=extraction.id,
        source_id=source.id,
        source_status=source.status.value,
        statute_number=number,
        statute_title=source.title,
        article_no=fields["article_no"],
        ordinal=fields["ordinal"],
        heading=fields["heading"],
        status=await statute_article_status(db, extraction),
        band=extraction.confidence["band"],
        reasons=extraction.confidence["reasons"],
        warnings=extraction.warnings,
        timeline=_timeline(fields),
        snapshots=[
            StatuteSnapshotOut(
                file_name=PurePath(s["path"]).name,
                date=date.fromisoformat(s["date"]) if s["date"] else None,
            )
            for s in fields.get("snapshots", [])
        ],
        latest_snapshot_date=date.fromisoformat(fields["latest_snapshot_date"]),
        reviews=[
            ReviewOut(
                id=r.id,
                reviewer_id=r.reviewer_id,
                reviewer_name=name,
                decision=r.decision.value,
                edits=r.edits,
                note=r.note,
                reviewed_at=r.reviewed_at,
            )
            for r, name in reviews
        ],
        live_extraction_id=live_extraction_id,
    )


@router.post("/{extraction_id}")
async def act(
    extraction_id: uuid.UUID, body: StatuteReviewActionRequest, user: Reviewer, db: Db
) -> StatuteReviewActionResponse:
    _, source = await _statute_extraction(db, extraction_id)
    try:
        if body.action == "reject":
            if body.note is None:  # the request model guarantees it; narrows the type
                raise ApiError(422, ErrorCode.validation_error, {"fields": ["note"]})
            review_id = await reject_statute_article(db, extraction_id, user.id, body.note)
            article_id = None
        else:
            review_id, article_id = await approve_statute_article(
                db, extraction_id, user.id, note=body.note, idempotent=False
            )
    except StaleExtraction:
        raise ApiError(409, ErrorCode.review_conflict) from None
    except ValueError:  # the publish refused the timeline; which part is not a UI concern
        raise ApiError(422, ErrorCode.validation_error, {"fields": []}) from None
    await db.commit()
    await db.refresh(source)
    return StatuteReviewActionResponse(
        review_id=review_id, article_id=article_id, source_status=source.status.value
    )


def _timeline(fields: dict[str, Any]) -> list[TimelineEntry]:
    """The versions and the gaps of a timeline in one list, by start date (a gap that starts at
    the statute's own entry into force first)."""
    entries: list[tuple[date, int, TimelineEntry]] = [
        (
            date.fromisoformat(v["valid_from"]),
            0,
            TimelineVersion(
                kind="version",
                text=v["text"],
                heading=v["heading"],
                valid_from=v["valid_from"],
                valid_to=v["valid_to"],
                change_kind=v["change_kind"],
                amending_ref=format_amending_ref(v["amending_ref"]),
                evidence=version_evidence(v),
                confidence=v["confidence"],
                footnotes=v["footnotes"],
                warnings=v["warnings"],
            ),
        )
        for v in fields["versions"]
    ]
    entries += [
        (
            date.fromisoformat(g["from"]) if g["from"] else date.min,
            1,
            TimelineGap.model_validate({**g, "kind": "gap"}),
        )
        for g in fields["gaps"]
    ]
    return [entry for _, _, entry in sorted(entries, key=lambda e: e[:2])]


async def _statute_extraction(
    db: AsyncSession, extraction_id: uuid.UUID
) -> tuple[Extraction, Source]:
    """The extraction of a statute source with its source, or 404."""
    row = (
        await db.execute(
            select(Extraction, Source)
            .join(Source, Source.id == Extraction.source_id)
            .where(
                Extraction.id == extraction_id,
                Extraction.parser_name == STATUTE_PARSER_NAME,
                Source.category == SourceCategory.statute,
            )
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, ErrorCode.extraction_not_found)
    extraction, source = row
    return extraction, source
