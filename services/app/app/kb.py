"""Knowledge-base writes that follow a human review (data-model.md §3-§4)."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import (
    Court,
    CourtLevel,
    Extraction,
    Jurisdiction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    SourceCategory,
    TextCompleteness,
    Verification,
)
from app.models.decision import Decision

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
