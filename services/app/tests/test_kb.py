import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import (
    StaleExtraction,
    approve_extraction,
    publish_batch,
    publish_decision,
    queue,
    reject_extraction,
)
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
from hukuk_models import ReviewFilters

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


# --- queue and the writes after a review ------------------------------------------------------


async def _first_high(session: AsyncSession) -> uuid.UUID:
    rows = (await session.execute(queue("high", ReviewFilters(), "sha256"))).all()
    first: uuid.UUID = rows[0].id
    return first


async def _count(session: AsyncSession, model: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_the_queue_in_sha256_order_resumes_after_a_cursor(
    kb_loaded: async_sessionmaker[AsyncSession],
) -> None:
    async with kb_loaded() as session:
        rows = (await session.execute(queue(None, ReviewFilters(), "sha256"))).all()
        assert [r.sha256 for r in rows] == sorted(r.sha256 for r in rows)
        assert len(rows) > 3
        after = (
            await session.execute(queue(None, ReviewFilters(), "sha256", rows[2].sha256))
        ).all()
        assert [r.id for r in after] == [r.id for r in rows[3:]]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            "INSERT INTO extraction (file_id, source_id, parser_name, parser_version, fields, "
            "confidence, warnings) SELECT file_id, source_id, parser_name, 'next', fields, "
            "confidence, warnings FROM extraction WHERE id = :id",
            "newer extraction",
        ),
        (
            "UPDATE extraction SET confidence = jsonb_set(confidence, '{band}', '\"medium\"') "
            "WHERE id = :id",
            "band high",
        ),
        (
            "UPDATE source SET status = 'rejected' "
            "WHERE id = (SELECT source_id FROM extraction WHERE id = :id)",
            "no longer in review",
        ),
    ],
    ids=["newer extraction", "other band", "source left review"],
)
async def test_a_batch_rechecks_the_extraction_under_the_lock(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser, change: str, reason: str
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)  # what the reviewer saw ...
        await session.execute(text(change), {"id": extraction_id})  # ... then the state moved on
        result = await publish_batch(session, [extraction_id], reviewer.id, "high")
        assert (result.published, result.conflicts) == (0, [])
        [(failed_id, message)] = result.failed
        assert failed_id == extraction_id
        assert reason in message
        assert (await _count(session, Review), await _count(session, Decision)) == (0, 0)


async def test_an_unknown_reviewer_is_a_failure_not_a_conflict(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)
        with pytest.raises(ValueError, match="fk_review_reviewer_id_app_user"):
            await approve_extraction(session, extraction_id, uuid.uuid4())
        result = await publish_batch(session, [extraction_id], uuid.uuid4(), "high")
        assert (result.published, result.conflicts) == (0, [])
        assert "fk_review_reviewer_id_app_user" in result.failed[0][1]
        assert await _count(session, Review) == 0
        # the session is still usable: the same record goes through with a real reviewer
        assert (await publish_batch(session, [extraction_id], reviewer.id, "high")).published == 1


async def test_a_live_key_collision_stays_an_integrity_error(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        first, second = await _extraction(session, 13), await _extraction(session, 30)
        await approve_extraction(session, first.id, reviewer.id)
        with pytest.raises(IntegrityError):
            await approve_extraction(session, second.id, reviewer.id)
        assert await _count(session, Review) == 1


async def test_reject_marks_the_source_once(
    kb_loaded: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    async with kb_loaded() as session:
        extraction_id = await _first_high(session)
        review_id = await reject_extraction(session, extraction_id, reviewer.id, "kopya")
        review = await session.get(Review, review_id)
        assert review is not None
        assert (review.decision, review.note) == (ReviewDecision.reject, "kopya")
        status = (
            await session.execute(
                select(Source.status)
                .join(Extraction, Extraction.source_id == Source.id)
                .where(Extraction.id == extraction_id)
            )
        ).scalar_one()
        assert status is RecordStatus.rejected
        with pytest.raises(StaleExtraction, match="no longer in review"):
            await reject_extraction(session, extraction_id, reviewer.id, "tekrar")
        assert await _count(session, Decision) == 0
