import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kb import approve_extraction
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.loaders.rescore import rescore
from app.models.common import Extraction
from app.models.user import AppUser

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
STALE = {"score": 40, "band": "low", "reasons": ["missing_karar_no"]}


async def _stored(factory: async_sessionmaker[AsyncSession]) -> list[tuple[Any, ...]]:
    async with factory() as session:
        rows = await session.execute(
            select(Extraction.id, Extraction.fields, Extraction.confidence).order_by(Extraction.id)
        )
        return [tuple(row) for row in rows]


async def _load_application(
    factory: async_sessionmaker[AsyncSession], *, stale: bool = True, **overrides: Any
) -> None:
    rows, _, _ = read_rows(FIXTURE)
    record = {
        **rows[0],
        "court": "aym",
        "court_level": "aym",
        "chamber": "",
        "decision_kind": "bireysel_basvuru",
        "esas_no": "2014/19081",
        "karar_no": "",
        **overrides,
    }
    prepared, _ = prepare([record], {})
    await load(factory, prepared, LoadCounts())
    if stale:
        async with factory() as session:
            await session.execute(update(Extraction).values(confidence=STALE))
            await session.commit()


async def test_rescore_rewrites_a_stale_confidence_and_nothing_else(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(kb_factory)
    before = await _stored(kb_factory)

    assert await rescore(kb_factory) == {"low->high": 1}

    ((id_, fields, confidence),) = await _stored(kb_factory)
    assert (id_, fields) == (before[0][0], before[0][1])
    assert confidence != STALE
    assert "missing_karar_no" not in confidence["reasons"]


async def test_rescore_is_idempotent(kb_factory: async_sessionmaker[AsyncSession]) -> None:
    await _load_application(kb_factory)
    assert sum((await rescore(kb_factory)).values()) == 1
    after_first = await _stored(kb_factory)
    assert not await rescore(kb_factory)
    assert await _stored(kb_factory) == after_first


async def test_a_dry_run_counts_and_writes_nothing(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(kb_factory)
    assert await rescore(kb_factory, dry_run=True) == {"low->high": 1}
    ((_, _, confidence),) = await _stored(kb_factory)
    assert json.dumps(confidence, sort_keys=True) == json.dumps(STALE, sort_keys=True)


async def _tables(factory: async_sessionmaker[AsyncSession]) -> list[Any]:
    async with factory() as session:
        return [
            (await session.execute(text(f"SELECT to_jsonb(t) FROM {table} t ORDER BY id"))).all()
            for table in ("source", "review", "decision")
        ]


async def test_rescore_leaves_an_approved_record_approved(
    kb_factory: async_sessionmaker[AsyncSession], reviewer: AppUser
) -> None:
    await _load_application(kb_factory)
    async with kb_factory() as session:
        extraction_id = (await session.execute(select(Extraction.id))).scalar_one()
        await approve_extraction(session, extraction_id, reviewer.id)
        await session.execute(update(Extraction).values(confidence=STALE))
        await session.commit()
    before = await _tables(kb_factory)
    assert before[1] and before[2]  # one review row, one published decision

    assert await rescore(kb_factory) == {"low->high": 1}

    assert await _tables(kb_factory) == before


async def test_rescore_keeps_the_band_of_a_norm_review_and_a_foreign_court(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(
        kb_factory, stale=False, decision_kind="norm_denetimi", esas_no="2015/12"
    )
    assert not await rescore(kb_factory)
    assert (await _stored(kb_factory))[0][2]["band"] == "low"

    async with kb_factory() as session:
        await session.execute(text("DELETE FROM extraction"))
        await session.commit()
    await _load_application(
        kb_factory, stale=False, court="abad", court_level="foreign", decision_kind="", esas_no=""
    )
    assert not await rescore(kb_factory)
    assert (await _stored(kb_factory))[0][2]["band"] == "low"


async def test_rescore_does_not_crash_on_a_row_without_decision_kind(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(kb_factory)
    async with kb_factory() as session:
        await session.execute(
            text(
                "UPDATE extraction SET fields = fields - 'decision_kind',"
                ' confidence = \'{"score": 100, "band": "high", "reasons": []}\''
            )
        )
        await session.commit()
    assert await rescore(kb_factory) == {"high->low": 1}
