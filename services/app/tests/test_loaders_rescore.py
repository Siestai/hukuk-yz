import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.loaders.rescore import rescore
from app.models.common import Extraction

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
STALE = {"score": 40, "band": "low", "reasons": ["missing_karar_no"]}


async def _stored(factory: async_sessionmaker[AsyncSession]) -> list[tuple[Any, ...]]:
    async with factory() as session:
        rows = await session.execute(
            select(Extraction.id, Extraction.fields, Extraction.confidence).order_by(Extraction.id)
        )
        return [tuple(row) for row in rows]


async def _load_application(factory: async_sessionmaker[AsyncSession]) -> None:
    rows, _, _ = read_rows(FIXTURE)
    record = {
        **rows[0],
        "court": "aym",
        "court_level": "aym",
        "chamber": "",
        "decision_kind": "bireysel_basvuru",
        "esas_no": "2014/19081",
        "karar_no": "",
    }
    prepared, _ = prepare([record], {})
    await load(factory, prepared, LoadCounts())
    async with factory() as session:
        await session.execute(update(Extraction).values(confidence=STALE))
        await session.commit()


async def test_rescore_rewrites_a_stale_confidence_and_nothing_else(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(kb_factory)
    before = await _stored(kb_factory)

    assert await rescore(kb_factory) == 1

    ((id_, fields, confidence),) = await _stored(kb_factory)
    assert (id_, fields) == (before[0][0], before[0][1])
    assert confidence != STALE
    assert "missing_karar_no" not in confidence["reasons"]


async def test_rescore_is_idempotent(kb_factory: async_sessionmaker[AsyncSession]) -> None:
    await _load_application(kb_factory)
    assert await rescore(kb_factory) == 1
    after_first = await _stored(kb_factory)
    assert await rescore(kb_factory) == 0
    assert await _stored(kb_factory) == after_first


async def test_a_dry_run_counts_and_writes_nothing(
    kb_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _load_application(kb_factory)
    assert await rescore(kb_factory, dry_run=True) == 1
    ((_, _, confidence),) = await _stored(kb_factory)
    assert json.dumps(confidence, sort_keys=True) == json.dumps(STALE, sort_keys=True)
