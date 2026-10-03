from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import publish_decision
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.models.common import (
    Court,
    Extraction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    Verification,
)
from app.models.decision import Decision
from app.models.user import AppUser

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"


@pytest.fixture
async def kb_loaded(
    kb_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """`kb_factory` with the decision fixture loaded as review-queue rows."""
    rows, _, _ = read_rows(FIXTURE)
    prepared, _ = prepare(rows, {})
    await load(kb_factory, prepared, LoadCounts())
    return kb_factory


async def _extraction(session: AsyncSession, journal_page: int) -> Extraction:
    rows = (await session.execute(select(Extraction))).scalars().all()
    return next(e for e in rows if e.fields["journal_page"] == journal_page)


def _review(
    extraction: Extraction,
    reviewer: AppUser,
    decision: ReviewDecision,
    edits: dict[str, Any] | None = None,
) -> Review:
    return Review(
        extraction_id=extraction.id, reviewer_id=reviewer.id, decision=decision, edits=edits
    )


async def test_publish_copies_fields_and_overlays_edits(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(
            extraction, reviewer, ReviewDecision.edit, {"outcome": "onama", "chamber": "10. HD"}
        )
        session.add(review)
        await session.flush()
        decision_id = await publish_decision(session, extraction.id, review.id)
        await session.commit()

        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.court is Court.yargitay
        assert (decision.chamber, decision.outcome) == ("10. HD", "onama")
        assert (decision.esas_no, decision.karar_no) == ("2003/2518", "2003/15276")
        assert decision.decision_date == date(2003, 9, 23)
        assert decision.full_text == extraction.fields["full_text"]
        assert decision.editorial_summary == extraction.fields["editorial_summary"]
        assert decision.related_articles == extraction.fields["related_articles"]
        assert (decision.source_id, decision.extraction_id, decision.review_id) == (
            extraction.source_id,
            extraction.id,
            review.id,
        )
        assert decision.verification is Verification.unverified
        source = await session.get(Source, extraction.source_id)
        assert source is not None
        assert source.status is RecordStatus.approved


async def test_empty_fields_become_null(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 18)  # no esas_no
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        decision_id = await publish_decision(session, extraction.id, review.id)
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.esas_no is None


async def test_a_rejected_review_does_not_publish(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(extraction, reviewer, ReviewDecision.reject)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="rejected"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_source_is_published_once(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 10)
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        await publish_decision(session, extraction.id, review.id)
        with pytest.raises(ValueError, match="analyzed"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_review_of_another_extraction_is_refused(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction, other = await _extraction(session, 10), await _extraction(session, 12)
        review = _review(other, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="does not belong"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_decision_without_a_court_cannot_be_published(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction = await _extraction(session, 21)  # court is empty
        review = _review(extraction, reviewer, ReviewDecision.approve)
        session.add(review)
        await session.flush()
        with pytest.raises(ValueError, match="court"):
            await publish_decision(session, extraction.id, review.id)


async def test_a_live_key_collision_is_an_integrity_error(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        first, second = await _extraction(session, 13), await _extraction(session, 30)
        for extraction in (first, second):  # the same_text pair shares its key
            review = _review(extraction, reviewer, ReviewDecision.approve)
            session.add(review)
            await session.flush()
            if extraction is first:
                await publish_decision(session, extraction.id, review.id)
        with pytest.raises(IntegrityError):
            await publish_decision(session, second.id, review.id)
