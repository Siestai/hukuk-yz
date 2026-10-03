"""Review API of decision extractions (task 09): queue, detail, approve / edit / reject and
bulk approval of the high band. HTTP only: the queue query and the writes after a review are in
`app.kb`, shared with the `--approve-band` CLI of the loader.
"""

import asyncio
import hashlib
import logging
import os
import stat
import uuid
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.auth import Db, require_role
from app.errors import ApiError
from app.kb import (
    PARSER_NAME,
    StaleExtraction,
    approve_extraction,
    publish_batch,
    queue,
    reject_extraction,
)
from app.models.common import (
    Court,
    Extraction,
    IngestFile,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
)
from app.models.decision import Decision
from app.models.user import AppUser
from app.settings import get_settings
from hukuk_models import (
    Band,
    BulkApproveRequest,
    BulkApproveResponse,
    BulkFailure,
    Confidence,
    DuplicateOut,
    ErrorCode,
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

logger = logging.getLogger("app")

TOP_REASONS = 15

ListSort = Literal["score_asc", "score_desc"]

_reviewer = require_role("reviewer")
Reviewer = Annotated[AppUser, Depends(_reviewer)]
router = APIRouter(prefix="/review/decisions", tags=["review"], dependencies=[Depends(_reviewer)])


async def _count(db: AsyncSession, stmt: Select[Any]) -> int:
    return (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()


def _list_item(row: Any) -> ReviewListItem:
    return ReviewListItem(
        extraction_id=row.id,
        source_id=row.source_id,
        title=row.title,
        court=row.court,
        chamber=row.chamber,
        esas_no=row.esas_no,
        karar_no=row.karar_no,
        decision_date=row.decision_date,
        journal_issue=row.journal_issue,
        band=row.band,
        score=row.score,
        reasons=row.confidence["reasons"],
        duplicate_group=row.duplicate_group,
    )


@router.get("")
async def list_decisions(
    db: Db,
    band: Band | None = None,
    court: str | None = None,
    reason: str | None = None,
    journal_issue: int | None = None,
    q: str | None = None,
    sort: ListSort = "score_asc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewListResponse:
    filters = ReviewFilters(court=court, reason=reason, journal_issue=journal_issue, q=q)
    stmt = queue(band, filters, sort)
    rows = (
        await db.execute(
            stmt.add_columns(func.count().over().label("total")).limit(limit).offset(offset)
        )
    ).all()
    if rows:
        total = rows[0].total
    elif offset:  # past the last page
        total = await _count(db, stmt)
    else:
        total = 0
    return ReviewListResponse(total=total, items=[_list_item(r) for r in rows])


@router.get("/summary")
async def summary(db: Db) -> ReviewSummary:
    pending = queue(None, ReviewFilters()).subquery()
    by_band: dict[str, int] = dict(
        (await db.execute(select(pending.c.band, func.count()).group_by(pending.c.band))).all()
    )
    by_court = (
        await db.execute(select(pending.c.court, func.count()).group_by(pending.c.court))
    ).all()
    reason = func.jsonb_array_elements_text(pending.c.confidence["reasons"]).column_valued("reason")
    reasons = (
        await db.execute(
            select(reason, func.count().label("n"))
            .select_from(pending)
            .group_by(reason)
            .order_by(func.count().desc(), reason)
            .limit(TOP_REASONS)
        )
    ).all()
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
        by_band={
            "high": by_band.get("high", 0),
            "medium": by_band.get("medium", 0),
            "low": by_band.get("low", 0),
        },
        by_court=dict(by_court),
        top_reasons=[ReasonCount(reason=reason, count=count) for reason, count in reasons],
        approved=counts.get(ReviewDecision.approve, 0) + counts.get(ReviewDecision.edit, 0),
        rejected=counts.get(ReviewDecision.reject, 0),
    )


@router.post("/bulk-approve")
async def bulk_approve(body: BulkApproveRequest, user: Reviewer, db: Db) -> BulkApproveResponse:
    def pending(after: str | None) -> Select[Any]:
        return queue(body.band, body.filters, "sha256", after)

    if body.band != "high":
        raise ApiError(422, ErrorCode.bulk_band_not_allowed)
    total = await _count(db, pending(body.cursor))
    if total != body.expected_count:
        raise ApiError(
            409,
            ErrorCode.bulk_count_changed,
            {"total": total, "expected": body.expected_count},
        )
    rows = (await db.execute(pending(body.cursor).limit(body.limit))).all()
    result = await publish_batch(db, [row.id for row in rows], user.id, body.band)
    await db.commit()
    last = rows[-1].sha256 if rows else None
    remaining = await _count(db, pending(last)) if last else 0
    return BulkApproveResponse(
        published=result.published,
        conflicts=result.conflicts,
        failed=[BulkFailure(extraction_id=i, reason=reason) for i, reason in result.failed],
        remaining=remaining,
        next_cursor=last if remaining else None,
    )


@router.get("/{extraction_id}")
async def get_decision(extraction_id: uuid.UUID, db: Db) -> ReviewDetail:
    extraction, source = await _decision_extraction(db, extraction_id)
    duplicates: list[DuplicateOut] = []
    if extraction.duplicate_key is not None:
        # Candidates by the indexed group key first; of those, the newest of their source.
        newer = aliased(Extraction)
        rows = await db.execute(
            select(
                Extraction.id,
                Extraction.confidence,
                func.length(Extraction.fields["full_text"].as_string()),
            )
            .join(Source, Source.id == Extraction.source_id)
            .where(
                Extraction.duplicate_key == extraction.duplicate_key,
                Extraction.parser_name == PARSER_NAME,
                Extraction.id != extraction_id,
                Source.category == SourceCategory.decision,
                ~exists().where(
                    newer.source_id == Extraction.source_id,
                    newer.parser_name == PARSER_NAME,
                    or_(
                        newer.extracted_at > Extraction.extracted_at,
                        and_(
                            newer.extracted_at == Extraction.extracted_at,
                            newer.id < Extraction.id,
                        ),
                    ),
                ),
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
        await db.execute(
            select(Review, AppUser.display_name)
            .join(AppUser, AppUser.id == Review.reviewer_id)
            .where(Review.extraction_id == extraction_id)
            .order_by(Review.reviewed_at, Review.id)
        )
    ).all()
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
                reviewer_name=name,
                decision=r.decision.value,
                edits=r.edits,
                note=r.note,
                reviewed_at=r.reviewed_at,
            )
            for r, name in reviews
        ],
    )


@router.get(
    "/{extraction_id}/file",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def get_file(extraction_id: uuid.UUID, db: Db) -> Response:
    """The original PDF of a decision extraction, for the detail screen.

    Copyright: the archive PDFs are pages of the journal Çalışma ve Toplum. They are served
    only to a logged-in reviewer, for internal review, never publicly.

    `ingest_file.path` is relative to `ARCHIVE_ROOT` (the loader stores the path under the Drive
    copy, e.g. `Yargi_Kararlari_Arsivi/...`). The file is served only if it resolves inside the
    root (no `..`, no symlink out), is within `ARCHIVE_MAX_FILE_BYTES` and its SHA-256 equals
    `ingest_file.sha256`: no file rather than the wrong one. It is opened once, and the bytes
    that were hashed are the bytes sent, so the file cannot change in between.
    """
    extraction, _ = await _decision_extraction(db, extraction_id)
    ingest_file = await db.get(IngestFile, extraction.file_id)
    assert ingest_file is not None  # extraction.file_id is a foreign key
    if ingest_file.detected_type != "pdf":
        raise ApiError(415, ErrorCode.file_not_previewable)
    root = get_settings().archive_root
    if root is None:
        raise ApiError(404, ErrorCode.file_not_found)
    try:
        path = (root / ingest_file.path).resolve(strict=True)
    except OSError:
        raise ApiError(404, ErrorCode.file_not_found) from None
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ApiError(404, ErrorCode.file_not_found)
    content = await asyncio.to_thread(
        _read_archive_file, path, get_settings().archive_max_file_bytes
    )
    if content is None:
        logger.warning(
            "archive file unreadable or over the size cap (extraction %s)", extraction_id
        )
        raise ApiError(404, ErrorCode.file_not_found)
    if hashlib.sha256(content).hexdigest() != ingest_file.sha256:
        logger.warning("archive file does not match its sha256 (extraction %s)", extraction_id)
        raise ApiError(404, ErrorCode.file_not_found)
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{ingest_file.sha256}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{extraction_id}")
async def act(
    extraction_id: uuid.UUID, body: ReviewActionRequest, user: Reviewer, db: Db
) -> ReviewActionResponse:
    extraction, _ = await _decision_extraction(db, extraction_id)
    edits = (
        body.edits.model_dump(mode="json", exclude_unset=True)
        if body.action == "edit" and body.edits
        else None
    )
    try:
        if body.action == "reject":
            assert body.note  # ReviewActionRequest guarantees it
            review_id = await reject_extraction(db, extraction_id, user.id, body.note)
            decision_id = None
        else:
            review_id, decision_id = await approve_extraction(
                db, extraction_id, user.id, ReviewDecision(body.action), edits, body.note
            )
    except StaleExtraction:
        raise ApiError(409, ErrorCode.review_conflict) from None
    except IntegrityError:  # a live-key collision; any other violation is a ValueError
        conflict = await _live_conflict(db, {**extraction.fields, **(edits or {})})
        raise ApiError(
            409, ErrorCode.decision_conflict, {"decision_id": str(conflict) if conflict else None}
        ) from None
    except ValueError:  # the publish refused the merged fields; which one is not a UI concern
        raise ApiError(422, ErrorCode.validation_error, {"fields": []}) from None
    await db.commit()
    return ReviewActionResponse(
        review_id=review_id,
        decision_id=decision_id,
        source_status="rejected" if body.action == "reject" else "approved",
    )


def _read_archive_file(path: Path, max_bytes: int) -> bytes | None:
    """The bytes of a regular file of at most `max_bytes`, opened without following a symlink;
    None when it is none of that."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            return None
        content = f.read(max_bytes + 1)
    return content if len(content) <= max_bytes else None


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
        raise ApiError(404, ErrorCode.extraction_not_found)
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
