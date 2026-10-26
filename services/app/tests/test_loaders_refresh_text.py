"""`app.loaders.refresh_text` (task 04b). The database tests are skipped when DATABASE_URL is
unset; CI sets it."""

import dataclasses
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import approve_extraction, queue, reject_extraction
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.refresh_text import refresh_text
from app.loaders.report import LoadCounts, PreparedRecord
from app.models.common import (
    Extraction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    TextCompleteness,
    Verification,
)
from app.models.decision import Decision, DecisionVerification
from app.models.user import AppUser
from hukuk_models import ReviewFilters

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
NEW_TEXT = "tam karar metni " * 20
SUMMARY_ONLY: dict[str, Any] = {"full_text": "", "text_completeness": "summary_only", "outcome": ""}


async def _load_v5(
    factory: async_sessionmaker[AsyncSession], count: int = 1, **fields: Any
) -> list[PreparedRecord]:
    """`count` fixture decisions as parser v5 output with no text; returns them."""
    rows, _, _ = read_rows(FIXTURE)
    prepared, _ = prepare([{**r, **SUMMARY_ONLY, **fields} for r in rows[:count]], {})
    await load(factory, prepared, LoadCounts())
    return prepared


async def _load_v6(
    factory: async_sessionmaker[AsyncSession], record: PreparedRecord, **fields: Any
) -> None:
    """The v6 extraction of a record: the same fields, now with a full text."""
    new = {"full_text": NEW_TEXT, "text_completeness": "full", "outcome": "bozma", **fields}
    await load(
        factory,
        [dataclasses.replace(record, parser_version="6", fields={**record.fields, **new})],
        LoadCounts(),
    )


async def _extraction_id(session: AsyncSession, record: PreparedRecord, version: str) -> Any:
    return (
        await session.execute(
            select(Extraction.id).where(
                Extraction.fields["journal_page"].as_integer() == record.fields["journal_page"],
                Extraction.parser_version == version,
            )
        )
    ).scalar_one()


async def _approve(
    factory: async_sessionmaker[AsyncSession],
    reviewer: AppUser,
    record: PreparedRecord,
    edits: dict[str, Any] | None = None,
) -> None:
    async with factory() as session:
        await approve_extraction(
            session,
            await _extraction_id(session, record, "5"),
            reviewer.id,
            ReviewDecision.edit if edits else ReviewDecision.approve,
            edits,
        )
        await session.commit()


async def _decisions(factory: async_sessionmaker[AsyncSession]) -> list[Decision]:
    async with factory() as session:
        return list(
            (await session.execute(select(Decision).order_by(Decision.recorded_at, Decision.id)))
            .scalars()
            .all()
        )


async def test_an_approved_decision_gets_the_new_text_and_keeps_the_rest(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record, {"chamber": "10. HD"})
    async with kb_factory() as session:  # verification state that must survive
        await session.execute(
            update(Decision).values(
                verification=Verification.verified_official,
                verification_source="karararama_yargitay",
                verification_ref="ref-1",
                verified_at=func.now(),
            )
        )
        await session.commit()
    (old,) = await _decisions(kb_factory)
    assert (old.full_text, old.text_completeness) == (None, TextCompleteness.summary_only)
    await _load_v6(kb_factory, record)

    assert await refresh_text(kb_factory) == {"refreshed": 1, "summary_only->full": 1}

    old, new = await _decisions(kb_factory)
    assert old.superseded_at is not None and new.superseded_at is None
    assert (new.full_text, new.text_completeness, new.outcome) == (
        NEW_TEXT,
        TextCompleteness.full,
        "bozma",
    )
    assert new.chamber == "10. HD"  # the reviewer's edit
    for column in (
        "source_id", "review_id", "recorded_by", "court", "esas_no", "karar_no",
        "decision_date", "editorial_summary", "keywords", "related_articles",
        "verification", "verification_source", "verification_ref", "verified_at",
    ):  # fmt: skip
        assert getattr(new, column) == getattr(old, column), column
    assert new.verification is Verification.verified_official
    async with kb_factory() as session:
        assert new.extraction_id == await _extraction_id(session, record, "6")
        assert (await session.get(Source, new.source_id)).status is RecordStatus.approved  # type: ignore[union-attr]
        # the approval review still belongs to the extraction it was written for
        review = await session.get(Review, new.review_id)
        assert review is not None
        assert review.extraction_id == await _extraction_id(session, record, "5")
        assert new.tsv is not None


async def test_a_second_run_refreshes_nothing(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    refreshed, same = await _load_v5(kb_factory, 2)
    await _approve(kb_factory, reviewer, refreshed)
    await _approve(kb_factory, reviewer, same)
    async with kb_factory() as session:  # the live text of `same` already equals the v6 text
        await session.execute(
            update(Decision)
            .where(Decision.esas_no == same.fields["esas_no"])
            .values(full_text=NEW_TEXT, text_completeness=TextCompleteness.full, outcome="bozma")
        )
        await session.commit()
    await _load_v6(kb_factory, refreshed)
    await _load_v6(kb_factory, same)
    assert await refresh_text(kb_factory) == {
        "refreshed": 1,
        "summary_only->full": 1,
        "skipped_same": 1,
    }
    after_first = [(d.id, d.superseded_at) for d in await _decisions(kb_factory)]

    # The skipped one keeps its old extraction_id, so it is counted again; nothing else moves.
    assert await refresh_text(kb_factory) == {"skipped_same": 1}
    assert await refresh_text(kb_factory) == {"skipped_same": 1}
    assert [(d.id, d.superseded_at) for d in await _decisions(kb_factory)] == after_first


async def test_a_dry_run_counts_and_writes_nothing(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record)
    await _load_v6(kb_factory, record)
    before = [(d.id, d.superseded_at, d.full_text) for d in await _decisions(kb_factory)]

    assert await refresh_text(kb_factory, dry_run=True) == {"refreshed": 1, "summary_only->full": 1}

    assert [(d.id, d.superseded_at, d.full_text) for d in await _decisions(kb_factory)] == before


async def test_an_edited_field_is_never_overwritten(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record, {"full_text": "elle yazılmış metin"})
    await _load_v6(kb_factory, record)

    assert await refresh_text(kb_factory) == {"refreshed": 1, "summary_only->full": 1}

    _, new = await _decisions(kb_factory)
    assert new.full_text == "elle yazılmış metin"
    assert new.text_completeness is TextCompleteness.full  # not edited: refreshed


async def test_a_decision_whose_changes_are_all_edited_is_skipped(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(
        kb_factory,
        reviewer,
        record,
        {"full_text": "elle", "text_completeness": "excerpt", "outcome": "onama"},
    )
    await _load_v6(kb_factory, record)

    assert await refresh_text(kb_factory) == {"skipped_edits": 1}
    assert len(await _decisions(kb_factory)) == 1


async def test_the_outcome_is_filled_only_when_empty(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    empty, filled = await _load_v5(kb_factory, 2)
    await _approve(kb_factory, reviewer, empty)
    await _approve(kb_factory, reviewer, filled)
    async with kb_factory() as session:  # the second one already has an outcome
        await session.execute(
            update(Decision)
            .where(Decision.esas_no == filled.fields["esas_no"])
            .values(outcome="onama")
        )
        await session.commit()
    await _load_v6(kb_factory, empty, outcome="bozma")
    await _load_v6(kb_factory, filled, outcome="bozma")

    assert (await refresh_text(kb_factory))["refreshed"] == 2

    outcomes = {
        d.esas_no: d.outcome for d in await _decisions(kb_factory) if d.superseded_at is None
    }
    assert outcomes == {empty.fields["esas_no"]: "bozma", filled.fields["esas_no"]: "onama"}


async def test_a_new_extraction_without_text_leaves_the_text_alone(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory, full_text="eski metin", text_completeness="excerpt")
    await _approve(kb_factory, reviewer, record)
    await _load_v6(kb_factory, record, full_text="", text_completeness="summary_only")

    assert await refresh_text(kb_factory) == {"skipped_same": 1}
    (only,) = await _decisions(kb_factory)
    assert (only.full_text, only.text_completeness) == ("eski metin", TextCompleteness.excerpt)


async def test_an_identical_new_text_is_skipped(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory, full_text=NEW_TEXT, text_completeness="full")
    await _approve(kb_factory, reviewer, record)
    await _load_v6(kb_factory, record, outcome="")

    assert await refresh_text(kb_factory) == {"skipped_same": 1}
    assert len(await _decisions(kb_factory)) == 1


async def test_rejected_and_pending_sources_are_not_touched(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    rejected, pending = await _load_v5(kb_factory, 2)
    async with kb_factory() as session:
        await reject_extraction(
            session, await _extraction_id(session, rejected, "5"), reviewer.id, "kopya"
        )
        await session.commit()
    await _load_v6(kb_factory, rejected)
    await _load_v6(kb_factory, pending)

    assert not await refresh_text(kb_factory)

    assert await _decisions(kb_factory) == []
    async with kb_factory() as session:
        statuses = (await session.execute(select(Source.status))).scalars().all()
        assert sorted(s.value for s in statuses) == ["analyzed", "rejected"]
        # the rejected one stays in its tab, with the reviewer; the pending one is just pending
        rows = (await session.execute(queue(None, ReviewFilters(), status="rejected"))).all()
        assert [(r.review_decision, r.reviewer_name) for r in rows] == [
            (ReviewDecision.reject, reviewer.display_name)
        ]


async def test_a_review_with_json_null_edits_is_treated_as_no_edits(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record)
    async with kb_factory() as session:  # JSON null, not SQL NULL
        await session.execute(update(Review).values(edits=JSON.NULL))
        await session.commit()
        stored = (await session.execute(select(Review.edits))).scalar_one()
        assert stored is None

    await _load_v6(kb_factory, record)
    assert await refresh_text(kb_factory) == {"refreshed": 1, "summary_only->full": 1}


async def test_the_verification_history_stays_on_the_closed_row(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record)
    (live,) = await _decisions(kb_factory)
    async with kb_factory() as session:
        session.add(
            DecisionVerification(decision_id=live.id, source="karararama_yargitay", outcome="match")
        )
        await session.commit()
    await _load_v6(kb_factory, record)

    assert (await refresh_text(kb_factory))["refreshed"] == 1

    old, new = await _decisions(kb_factory)
    async with kb_factory() as session:
        owners = (await session.execute(select(DecisionVerification.decision_id))).scalars().all()
    assert list(owners) == [old.id] and new.id != old.id


async def test_a_live_row_without_an_extraction_is_refreshed(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    # No published extraction to compare with: it counts as older than any parser run.
    (record,) = await _load_v5(kb_factory)
    await _approve(kb_factory, reviewer, record)
    async with kb_factory() as session:
        await session.execute(update(Decision).values(extraction_id=None))
        await session.commit()

    assert await refresh_text(kb_factory) == {"refreshed": 1, "summary_only->full": 1}

    old, new = await _decisions(kb_factory)
    async with kb_factory() as session:
        assert old.extraction_id is None
        assert new.extraction_id == await _extraction_id(session, record, "5")
    assert new.superseded_at is None


async def test_a_failing_source_is_counted_and_the_others_still_run(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    bad, good = await _load_v5(kb_factory, 2)
    await _approve(kb_factory, reviewer, bad)
    await _approve(kb_factory, reviewer, good)
    await _load_v6(kb_factory, bad, text_completeness="not-a-completeness")
    await _load_v6(kb_factory, good)

    counts = await refresh_text(kb_factory)

    assert counts == {"refreshed": 1, "summary_only->full": 1, "failed": 1}
    live = {d.esas_no: d for d in await _decisions(kb_factory) if d.superseded_at is None}
    assert live[good.fields["esas_no"]].full_text == NEW_TEXT
    assert live[bad.fields["esas_no"]].full_text is None  # rolled back, untouched
