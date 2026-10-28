"""The indexing command (task 14): `app.loaders.chunks.build`. Needs DATABASE_URL (CI sets it)."""

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.loaders import statutes as statute_loader
from app.loaders.chunks import build
from app.loaders.statutes_report import StatuteCounts
from app.models.chunk import Chunk
from tests.conftest import STATUTES_FIXTURE, FakeEmbedder
from tests.test_chunk_index import load_decision

Factory = async_sessionmaker[AsyncSession]


async def _load_statutes(factory: Factory) -> None:
    prepared = statute_loader.prepare([json.loads(STATUTES_FIXTURE.read_text(encoding="utf-8"))])
    await statute_loader.load(factory, prepared, {}, StatuteCounts())


async def count(factory: Factory) -> int:
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(Chunk)) or 0


async def test_dry_run_counts_and_writes_nothing(kb_factory: Factory) -> None:
    await load_decision(kb_factory)
    report = await build(kb_factory, None, dry_run=True)
    assert report.records == 1 and sum(report.chunks.values()) > 1
    assert report.estimated_tokens > 0
    assert any("dry run" in line for line in report.lines(True))
    assert await count(kb_factory) == 0


async def test_build_embeds_and_a_second_run_changes_nothing(
    kb_factory: Factory, fake_embedder: FakeEmbedder
) -> None:
    await load_decision(kb_factory)
    first = await build(kb_factory, fake_embedder, categories=("decision",))
    assert not first.failed and first.embedded_chunks == await count(kb_factory)
    calls = len(fake_embedder.calls)
    second = await build(kb_factory, fake_embedder, categories=("decision",))
    assert second.unchanged == 1 and second.embedded_chunks == 0
    assert len(fake_embedder.calls) == calls


async def test_statutes_only_and_limit(kb_factory: Factory, fake_embedder: FakeEmbedder) -> None:
    await load_decision(kb_factory)
    await _load_statutes(kb_factory)
    report = await build(kb_factory, fake_embedder, categories=("statute",), limit=1)
    assert report.records == 1
    assert {key[0] for key in report.chunks} == {"statute"}
