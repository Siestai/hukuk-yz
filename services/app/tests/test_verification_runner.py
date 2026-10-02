"""run_court with a stub source: no network. Database tests skip when DATABASE_URL is unset."""

import random
import uuid
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.common import Court, Verification
from app.models.decision import Decision, DecisionVerification
from app.verification.runner import RunOptions, SourceStats, describe, run_court, year_band
from app.verification.store import Candidate, candidates
from hukuk_verify import DecisionKey, Outcome
from hukuk_verify.adapters import SourceAdapter
from hukuk_verify.errors import RateLimitExhausted, SourceUnavailable
from hukuk_verify.models import LookupResult, OfficialRow, OfficialText
from hukuk_verify.ratelimit import RateLimiter

NewDecision = Callable[..., Awaitable[uuid.UUID]]


class StubSource(SourceAdapter):
    """Knows the decisions of `known` (esas numbers); fails for those of `broken`."""

    SOURCE = "karararama_yargitay"
    VERIFIED = Outcome.verified_official
    ORIGIN = "https://stub.invalid"
    PRE_2009_SKIP = True

    def __init__(
        self, known: Collection[str] = (), broken: Collection[str] = (), stop: str = ""
    ) -> None:
        super().__init__(httpx.AsyncClient(), RateLimiter())
        self.known, self.broken, self.stop = known, broken, stop
        self.queried: list[str] = []

    def supports(self, key: DecisionKey) -> bool:
        return key.esas_no is not None

    async def lookup(self, key: DecisionKey) -> LookupResult:
        assert key.esas_no and key.karar_no
        self.queried.append(key.esas_no)
        if key.esas_no == self.stop:
            raise RateLimitExhausted("three consecutive 429 answers")
        if key.esas_no in self.broken:
            raise SourceUnavailable("ConnectTimeout")
        if key.esas_no not in self.known:
            return LookupResult([])
        return LookupResult(
            [
                OfficialRow(
                    "77",
                    "https://stub.invalid/77",
                    "9. Hukuk Dairesi",
                    key.esas_no,
                    key.karar_no,
                    key.decision_date,
                )
            ]
        )

    async def fetch_text(self, ref: str) -> OfficialText | None:
        return OfficialText(f"text {ref}", {"data": f"text {ref}"})


def candidate(esas: str, year: int = 2020) -> Candidate:
    key = DecisionKey(
        "yargitay", "daire", "9. HD", "", "", esas, "2020/1", date(year, 5, 1), "karar"
    )
    return Candidate(None, key)


async def run(
    adapter: StubSource, todo: list[Candidate], skip_pre_2009: bool = True
) -> SourceStats:
    options = RunOptions(skip_pre_2009=skip_pre_2009, rng=random.Random(1))
    return await run_court(None, "yargitay", adapter, todo, options)


def test_year_bands_and_names() -> None:
    assert [year_band(candidate("1", y).key) for y in (2009, 2010, 2014, 2015)] == [
        "<=2009",
        "2010-14",
        "2010-14",
        "2015+",
    ]
    assert describe(candidate("2017/5").key) == "yargitay 9. HD E. 2017/5 K. 2020/1"


async def test_outcomes_are_counted_by_year_band() -> None:
    stats = await run(
        StubSource(known={"2020/1"}), [candidate("2020/1"), candidate("2020/2", 2012)]
    )
    assert dict(stats.outcomes) == {"verified_official": 1, "not_in_source": 1}
    assert stats.by_band["2015+"]["verified_official"] == 1
    assert stats.by_band["2010-14"]["not_in_source"] == 1


async def test_a_failed_lookup_is_an_error_and_the_run_goes_on() -> None:
    stub = StubSource(known={"2020/3"}, broken={"2020/2"})
    stats = await run(stub, [candidate("2020/1"), candidate("2020/2"), candidate("2020/3")])
    assert stats.errors == {"SourceUnavailable": 1}
    assert stats.outcomes["verified_official"] == 1
    assert stats.outcomes["not_in_source"] == 1  # the error is not counted as one
    assert stub.queried == ["2020/1", "2020/2", "2020/3"]


async def test_a_stopped_source_ends_the_run() -> None:
    stub = StubSource(stop="2020/2")
    stats = await run(stub, [candidate("2020/1"), candidate("2020/2"), candidate("2020/3")])
    assert stats.stopped is not None and stats.stopped.startswith("RateLimitExhausted")
    assert stub.queried == ["2020/1", "2020/2"]


async def test_three_network_errors_in_a_row_stop_the_source() -> None:
    names = [f"2020/{n}" for n in range(1, 7)]
    stub = StubSource(broken=names)
    stats = await run(stub, [candidate(n) for n in names])
    assert stats.stopped is not None and stats.stopped.startswith("SourceUnreachable")
    assert stub.queried == names[:3]  # the other three are not tried
    assert stats.errors == {"SourceUnavailable": 3}


async def test_a_success_resets_the_network_error_count() -> None:
    names = [f"2020/{n}" for n in range(1, 7)]
    stub = StubSource(known={"2020/3"}, broken={"2020/1", "2020/2", "2020/4", "2020/5"})
    stats = await run(stub, [candidate(n) for n in names])
    assert stats.stopped is None
    assert stub.queried == names
    assert stats.errors == {"SourceUnavailable": 4}


async def test_decisions_without_what_the_query_needs_are_counted_apart() -> None:
    stub = StubSource()
    no_esas = Candidate(
        None, DecisionKey("yargitay", "daire", "9. HD", "", "", None, None, None, "karar")
    )
    stats = await run(stub, [no_esas, candidate("2020/1")])
    assert (stats.unsupported, stats.candidates) == (1, 1)


async def test_up_to_2009_is_skipped_after_a_clean_coverage_sample() -> None:
    old = [candidate(f"2001/{n}", 2001) for n in range(25)]
    stub = StubSource()
    stats = await run(stub, old)
    assert len(stub.queried) == 20  # the random sample, queried for real
    assert (stats.skipped_pre_2009, stats.outcomes["not_in_source"]) == (5, 25)
    assert stats.sample == {"checked": 20, "found": 0, "heuristic_disabled": False}


async def test_a_found_sample_decision_switches_the_skip_off() -> None:
    old = [candidate(f"2001/{n}", 2001) for n in range(25)]
    stub = StubSource(known={f"2001/{n}" for n in range(25)})
    stats = await run(stub, old)
    assert len(stub.queried) == 25  # the other five are queried too
    assert stats.skipped_pre_2009 == 0
    assert stats.sample == {"checked": 20, "found": 20, "heuristic_disabled": True}


async def test_the_skip_can_be_turned_off() -> None:
    old = [candidate(f"2001/{n}", 2001) for n in range(25)]
    stub = StubSource()
    stats = await run(stub, old, skip_pre_2009=False)
    assert len(stub.queried) == 25
    assert (stats.skipped_pre_2009, stats.sample) == (0, None)


async def test_a_database_run_writes_decisions_and_the_official_cache(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision, tmp_path: Path
) -> None:
    async with kb_factory() as session:
        found = await new_decision(session, esas_no="2020/1")
        missing = await new_decision(session, esas_no="2020/2")
        broken = await new_decision(session, esas_no="2020/3")
        await session.commit()
        todo = await candidates(session, Court.yargitay, datetime.now(UTC), recheck_mismatch=False)

    stub = StubSource(known={"2020/1"}, broken={"2020/3"})
    stats = await run_court(
        kb_factory, "yargitay", stub, todo, RunOptions(cache_dir=tmp_path / "official")
    )
    assert stats.errors == {"SourceUnavailable": 1}

    async with kb_factory() as session:
        states = {d.id: d.verification for d in (await session.execute(select(Decision))).scalars()}
        assert states == {
            found: Verification.verified_official,
            missing: Verification.not_in_source,
            broken: Verification.unverified,
        }
        outcomes = {
            r.outcome for r in (await session.execute(select(DecisionVerification))).scalars()
        }
        assert outcomes == {"verified_official", "not_in_source", "error"}
    assert (tmp_path / "official" / "karararama_yargitay" / "77.json").read_text() == (
        '{"data": "text 77"}'
    )


async def test_a_stopped_source_writes_no_error_row_for_the_rest(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        for n in range(5):
            await new_decision(session, esas_no=f"2020/{n + 1}")
        await session.commit()
        todo = await candidates(session, Court.yargitay, datetime.now(UTC), recheck_mismatch=False)

    stub = StubSource(broken=[c.key.esas_no or "" for c in todo])
    stats = await run_court(kb_factory, "yargitay", stub, todo, RunOptions())
    assert stats.stopped is not None
    async with kb_factory() as session:
        rows = (await session.execute(select(DecisionVerification))).scalars().all()
        assert [r.outcome for r in rows] == ["error"] * 3


async def test_a_dry_run_writes_nothing(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision, tmp_path: Path
) -> None:
    async with kb_factory() as session:
        decision_id = await new_decision(session, esas_no="2020/1")
        await session.commit()
        todo = await candidates(session, Court.yargitay, datetime.now(UTC), recheck_mismatch=False)

    stats = await run_court(
        kb_factory,
        "yargitay",
        StubSource(known={"2020/1"}),
        todo,
        RunOptions(dry_run=True, cache_dir=tmp_path / "official"),
    )
    assert stats.outcomes["verified_official"] == 1
    async with kb_factory() as session:
        decision = await session.get(Decision, decision_id)
        assert decision is not None
        assert decision.verification is Verification.unverified
        assert (await session.execute(select(DecisionVerification))).first() is None
    assert not (tmp_path / "official").exists()


async def test_a_second_run_finds_nothing_due_and_adds_no_rows(
    kb_factory: async_sessionmaker[AsyncSession], new_decision: NewDecision
) -> None:
    async with kb_factory() as session:
        await new_decision(session, esas_no="2020/1")
        await session.commit()
        todo = await candidates(session, Court.yargitay, datetime.now(UTC), recheck_mismatch=False)
    stub = StubSource(known={"2020/1"})
    await run_court(kb_factory, "yargitay", stub, todo, RunOptions())
    async with kb_factory() as session:
        assert (
            await candidates(session, Court.yargitay, datetime.now(UTC), recheck_mismatch=False)
            == []
        )
