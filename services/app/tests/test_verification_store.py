"""Database behaviour of the verification (skipped when DATABASE_URL is unset; CI sets it)."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.common import (
    Court,
    CourtLevel,
    Source,
    SourceRank,
    Verification,
)
from app.models.decision import Decision, DecisionVerification
from app.verification.store import apply_error, apply_result, candidates
from hukuk_verify import Outcome, VerifyResult
from hukuk_verify.models import OfficialText

NewDecision = Callable[..., Awaitable[uuid.UUID]]
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=1)


def found(
    outcome: Outcome = Outcome.verified_official, ref: str = "100", text: str = "x"
) -> VerifyResult:
    return VerifyResult(
        outcome,
        "karararama_yargitay",
        ref,
        f"https://example/{ref}",
        {"chamber": "match"},
        OfficialText(text, {"data": text}),
    )


async def rank_of(session: AsyncSession, decision_id: uuid.UUID) -> SourceRank:
    decision = await session.get(Decision, decision_id)
    assert decision is not None
    source = await session.get(Source, decision.source_id, populate_existing=True)
    assert source is not None
    return source.source_rank


async def attempts(session: AsyncSession, decision_id: uuid.UUID) -> list[DecisionVerification]:
    rows = await session.execute(
        select(DecisionVerification)
        .where(DecisionVerification.decision_id == decision_id)
        .order_by(DecisionVerification.attempted_at)
    )
    return list(rows.scalars())


async def test_verified_raises_the_source_rank(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        applied = await apply_result(session, decision_id, found(), NOW)
        await session.commit()

        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert applied.new_row
        assert decision.verification is Verification.verified_official
        assert (decision.verification_source, decision.verification_ref) == (
            "karararama_yargitay",
            "100",
        )
        assert decision.verified_at == NOW
        assert await rank_of(session, decision_id) is SourceRank.official_primary
        [row] = await attempts(session, decision_id)
        assert (row.outcome, row.official_url) == ("verified_official", "https://example/100")
        assert row.matched == {"chamber": "match"}
        assert row.official_text_sha256 == found().official_text.sha256  # type: ignore[union-attr]


async def test_uyap_is_verified_uyap(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session, court=Court.bam)
        await apply_result(session, decision_id, found(Outcome.verified_uyap), NOW)
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.verification is Verification.verified_uyap
        assert await rank_of(session, decision_id) is SourceRank.official_primary


@pytest.mark.parametrize("outcome", [Outcome.mismatch, Outcome.not_in_source])
async def test_other_outcomes_keep_the_rank_editorial(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision, outcome: Outcome
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        await apply_result(session, decision_id, VerifyResult(outcome, "karararama_yargitay"), NOW)
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.verification is Verification(outcome.value)
        assert await rank_of(session, decision_id) is SourceRank.editorial


async def test_a_second_identical_result_adds_no_row(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        await apply_result(session, decision_id, found(), NOW)
        again = await apply_result(session, decision_id, found(), LATER)
        [row] = await attempts(session, decision_id)
        assert not again.new_row
        assert (row.attempted_at, row.last_checked_at) == (NOW, LATER)


async def test_a_changed_result_adds_a_row(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        await apply_result(session, decision_id, found(text="old"), NOW)
        await apply_result(session, decision_id, found(text="new"), LATER)
        assert len(await attempts(session, decision_id)) == 2


async def test_verified_is_never_lowered_to_not_in_source(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        await apply_result(session, decision_id, found(), NOW)
        gone = VerifyResult(Outcome.not_in_source, "karararama_yargitay")
        applied = await apply_result(session, decision_id, gone, LATER)

        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert applied.downgraded
        assert decision.verification is Verification.mismatch
        assert await rank_of(session, decision_id) is SourceRank.editorial
        last = (await attempts(session, decision_id))[-1]
        assert last.outcome == "mismatch"
        assert last.matched["downgraded_from"] == "verified_official"


async def test_an_error_is_recorded_and_leaves_the_decision_alone(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        assert await apply_error(session, decision_id, "karararama_yargitay", "ConnectTimeout", NOW)
        assert not await apply_error(
            session, decision_id, "karararama_yargitay", "ConnectTimeout", LATER
        )
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.verification is Verification.unverified
        assert decision.verified_at is None
        [row] = await attempts(session, decision_id)
        assert (row.outcome, row.error, row.last_checked_at) == ("error", "ConnectTimeout", LATER)


async def test_unknown_outcome_is_rejected_by_the_database(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session)
        session.add(DecisionVerification(decision_id=decision_id, source="s", outcome="found"))
        with pytest.raises(IntegrityError):
            await session.flush()


async def test_candidates_are_the_due_live_decisions_of_the_court(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        unverified = await new_decision(session)
        old_miss = await new_decision(
            session, verification=Verification.not_in_source, verified_at=NOW - timedelta(days=91)
        )
        await new_decision(
            session, verification=Verification.not_in_source, verified_at=NOW - timedelta(days=89)
        )
        await new_decision(session, verification=Verification.verified_official, verified_at=NOW)
        mismatch = await new_decision(session, verification=Verification.mismatch, verified_at=NOW)
        await new_decision(session, superseded_at=NOW)
        await new_decision(session, court=Court.aym, court_level=CourtLevel.aym)

        plain = {
            c.id for c in await candidates(session, Court.yargitay, NOW, recheck_mismatch=False)
        }
        assert plain == {unverified, old_miss}
        wider = await candidates(session, Court.yargitay, NOW, recheck_mismatch=True)
        assert {c.id for c in wider} == {unverified, old_miss, mismatch}
        key = next(c.key for c in wider if c.id == unverified)
        assert (key.court, key.court_level, key.chamber) == ("yargitay", "daire", "9. HD")
        assert key.decision_date == date(2020, 12, 9)
