"""Database side of the verification: which decisions to check and what a result changes."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common import Court, Source, SourceRank, Verification
from app.models.decision import Decision, DecisionVerification
from hukuk_verify import DecisionKey, Outcome, VerifyResult

NOT_IN_SOURCE_RECHECK = timedelta(days=90)
VERIFIED = (Verification.verified_official, Verification.verified_uyap)
# `--court` names. A court the sources do not cover (AİHM, ABAD, foreign) is never a candidate.
COURTS = {
    "yargitay": Court.yargitay,
    "bam": Court.bam,
    "aym": Court.aym,
    "danistay": Court.danistay,
}


@dataclass(frozen=True)
class Candidate:
    """A decision to check; `id` is None for a key read from a file (`--keys`)."""

    id: uuid.UUID | None
    key: DecisionKey


async def candidates(
    session: AsyncSession, court: Court, now: datetime, recheck_mismatch: bool
) -> list[Candidate]:
    """Live decisions of a court that are `unverified` (a failed attempt leaves them so), or
    `not_in_source` for more than 90 days, or `mismatch` when asked. `verified_*` are never
    checked again."""
    due = [
        Decision.verification == Verification.unverified,
        and_(
            Decision.verification == Verification.not_in_source,
            Decision.verified_at < now - NOT_IN_SOURCE_RECHECK,
        ),
    ]
    if recheck_mismatch:
        due.append(Decision.verification == Verification.mismatch)
    # A source that was unreachable leaves its decisions `unverified`; never-tried ones go first,
    # then the longest-unchecked, so the same failing decisions do not head every run.
    last_checked = (
        select(
            DecisionVerification.decision_id,
            func.max(DecisionVerification.last_checked_at).label("at"),
        )
        .group_by(DecisionVerification.decision_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            Decision.id,
            Decision.court,
            Decision.court_level,
            Decision.chamber,
            Decision.source_chamber,
            Decision.bam_region,
            Decision.esas_no,
            Decision.karar_no,
            Decision.decision_date,
            Decision.decision_kind,
        )
        .outerjoin(last_checked, last_checked.c.decision_id == Decision.id)
        .where(Decision.court == court, Decision.superseded_at.is_(None), or_(*due))
        .order_by(last_checked.c.at.asc().nullsfirst(), Decision.decision_date, Decision.id)
    )
    return [
        Candidate(
            r.id,
            DecisionKey(
                court=r.court.value,
                court_level=r.court_level.value,
                chamber=r.chamber,
                source_chamber=r.source_chamber,
                bam_region=r.bam_region,
                esas_no=r.esas_no,
                karar_no=r.karar_no,
                decision_date=r.decision_date,
                decision_kind=r.decision_kind,
            ),
        )
        for r in rows
    ]


async def _latest(session: AsyncSession, decision_id: uuid.UUID) -> DecisionVerification | None:
    return (
        await session.execute(
            select(DecisionVerification)
            .where(DecisionVerification.decision_id == decision_id)
            .order_by(DecisionVerification.attempted_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class Applied:
    outcome: str  # what was written; `mismatch` instead of `not_in_source` for a downgrade
    downgraded: bool


async def apply_result(
    session: AsyncSession, decision_id: uuid.UUID, result: VerifyResult, now: datetime
) -> Applied:
    """Write one result; the caller owns the transaction. A decision that is already
    `verified_*` never falls to `not_in_source`: the official source answering without the
    decision is a `mismatch` (and reported), not a silent loss."""
    decision = await session.get(Decision, decision_id, with_for_update=True)
    assert decision is not None
    outcome = result.outcome
    matched = dict(result.matched)
    downgraded = decision.verification in VERIFIED and outcome is Outcome.not_in_source
    if downgraded:
        outcome = Outcome.mismatch
        matched["downgraded_from"] = decision.verification.value

    sha = result.official_text.sha256 if result.official_text else None
    ref = None if downgraded else result.official_ref
    last = await _latest(session, decision_id)
    # A change in `fuzzy` or `ambiguous` is history too, even when the verdict is the same.
    detail = (matched.get("fuzzy"), matched.get("ambiguous"))
    if last is not None and (
        last.outcome,
        last.official_ref,
        last.official_text_sha256,
        (last.matched.get("fuzzy"), last.matched.get("ambiguous")),
    ) == (outcome.value, ref, sha, detail):
        last.last_checked_at = now
    else:
        session.add(
            DecisionVerification(
                decision_id=decision_id,
                attempted_at=now,
                last_checked_at=now,
                source=result.source,
                outcome=outcome.value,
                official_ref=ref,
                official_url=None if downgraded else result.official_url,
                matched=matched,
                official_text_sha256=sha,
            )
        )

    decision.verification = Verification(outcome.value)
    decision.verification_source = result.source
    decision.verification_ref = ref
    decision.verified_at = now
    # The only place a source's rank changes (md. 26): official only while verified.
    source = await session.get(Source, decision.source_id)
    assert source is not None
    source.source_rank = (
        SourceRank.official_primary if decision.verification in VERIFIED else SourceRank.editorial
    )
    await session.flush()
    return Applied(outcome.value, downgraded=downgraded)


async def apply_error(
    session: AsyncSession, decision_id: uuid.UUID, source: str, error: str, now: datetime
) -> bool:
    """Record a failed attempt; the decision itself is left as it is. Returns whether a new row
    was added (a repeated failure only refreshes `last_checked_at`)."""
    last = await _latest(session, decision_id)
    if last is not None and last.outcome == "error":
        last.last_checked_at = now
        return False
    session.add(
        DecisionVerification(
            decision_id=decision_id,
            attempted_at=now,
            last_checked_at=now,
            source=source,
            outcome="error",
            error=error,
        )
    )
    await session.flush()
    return True
