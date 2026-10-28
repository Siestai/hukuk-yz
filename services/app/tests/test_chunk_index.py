"""Chunks in the database and their embeddings (task 14). The database tests are skipped when
DATABASE_URL is unset; CI sets it."""

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunk_index import (
    EXTRACTION,
    STATUTE_ARTICLE,
    embed_pending,
    sync_decision,
    sync_statute_article,
)
from app.kb import (
    approve_extraction,
    approve_statute_article,
    reject_extraction,
    reject_statute_article,
    reopen_extraction,
)
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.models.chunk import Chunk
from app.models.common import ChunkKind, Extraction, License, Source
from app.models.user import AppUser
from tests.conftest import FakeEmbedder

FIXTURE = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"
Factory = async_sessionmaker[AsyncSession]

PARAGRAPH = (
    "Davacı işe iade talebinde bulunmuştur ve altı aylık kıdem şartının dolup dolmadığı "
    "tartışılmıştır. Dosya kapsamına göre davalı işveren feshi geçerli nedene dayandırmamıştır."
)
BODY = "\n\n".join(f"{n}. {PARAGRAPH}" for n in range(1, 25))  # ~720 words: windowed
SUMMARY = "Editoryal özet: kıdem şartı ve işe iade."


async def load_decision(factory: Factory, **fields: Any) -> uuid.UUID:
    """One fixture decision (an analyzed source with its extraction); returns the source id."""
    rows, _, _ = read_rows(FIXTURE)
    row = {
        **rows[0],
        "full_text": BODY,
        "editorial_summary": SUMMARY,
        "text_completeness": "full",
        **fields,
    }
    prepared, _ = prepare([row], {})
    await load(factory, prepared, LoadCounts())
    async with factory() as session:
        return (await session.execute(select(Source.id))).scalars().one()


async def chunks(factory: Factory, **where: Any) -> list[Chunk]:
    async with factory() as session:
        stmt = select(Chunk).order_by(Chunk.kind, Chunk.parent_kind, Chunk.ordinal)
        for name, value in where.items():
            stmt = stmt.where(getattr(Chunk, name) == value)
        return list((await session.execute(stmt)).scalars())


async def test_an_analyzed_decision_is_indexed_from_its_extraction(kb_factory: Factory) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        result = await sync_decision(session, source_id)
        await session.commit()
    assert result.written
    stored = await chunks(kb_factory)
    body = [c for c in stored if c.kind is ChunkKind.body]
    summary = [c for c in stored if c.kind is ChunkKind.editorial_summary]
    assert len(body) > 1 and len(summary) == 1
    assert {c.parent_kind for c in stored} == {EXTRACTION}
    assert {c.source_id for c in stored} == {source_id}
    assert summary[0].license is License.internal_only
    assert summary[0].text == SUMMARY
    assert {c.license for c in body} == {License.unknown}
    assert all(c.embedding is None and c.tsv for c in stored)
    assert (body[0].header or "").startswith("Yargıtay 9. HD, E. 2003/2518")
    assert all(BODY[c.char_start : c.char_end] == c.text for c in body)
    assert body[0].title and body[0].doc_date and body[0].court_level


async def test_syncing_again_changes_nothing(kb_factory: Factory) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
    before = {c.id for c in await chunks(kb_factory)}
    async with kb_factory() as session:
        again = await sync_decision(session, source_id)
        await session.commit()
    assert not again.written
    assert {c.id for c in await chunks(kb_factory)} == before


async def test_a_summary_only_decision_has_the_summary_chunk_and_no_body(
    kb_factory: Factory,
) -> None:
    source_id = await load_decision(kb_factory, full_text="", text_completeness="summary_only")
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
    assert [c.kind for c in await chunks(kb_factory)] == [ChunkKind.editorial_summary]


async def test_approval_rebuilds_the_chunks_from_the_decision_and_keeps_the_vectors(
    kb_factory: Factory, reviewer: AppUser, fake_embedder: FakeEmbedder
) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
        await embed_pending(session, fake_embedder)
    assert all(c.embedding is not None for c in await chunks(kb_factory))
    embedded_texts = sum(len(call) for call in fake_embedder.calls)
    async with kb_factory() as session:
        extraction_id = (await session.execute(select(Extraction.id))).scalars().one()
        await approve_extraction(session, extraction_id, reviewer.id)
        await session.commit()
    stored = await chunks(kb_factory)
    assert {c.parent_kind for c in stored} == {"decision"}
    assert all(c.embedding is not None for c in stored)  # carried over, not embedded again
    async with kb_factory() as session:
        report = await embed_pending(session, fake_embedder)
    assert report.chunks == 0
    assert sum(len(call) for call in fake_embedder.calls) == embedded_texts


async def test_rejecting_removes_the_chunks_and_reopening_brings_them_back(
    kb_factory: Factory, reviewer: AppUser
) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
        extraction_id = (await session.execute(select(Extraction.id))).scalars().one()
        await reject_extraction(session, extraction_id, reviewer.id, "not a decision")
        await session.commit()
    assert await chunks(kb_factory) == []
    async with kb_factory() as session:
        await reopen_extraction(session, extraction_id, reviewer.id, None)
        await session.commit()
    assert {c.parent_kind for c in await chunks(kb_factory)} == {EXTRACTION}


async def test_a_rejected_source_is_never_indexed_by_the_sync(
    kb_factory: Factory, reviewer: AppUser
) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        extraction_id = (await session.execute(select(Extraction.id))).scalars().one()
        await reject_extraction(session, extraction_id, reviewer.id, "no")
        await session.commit()
        result = await sync_decision(session, source_id)
    assert result.rows == []
    assert await chunks(kb_factory) == []


async def test_a_statute_article_is_indexed_per_version_and_a_gap_has_no_chunk(
    kb_factory: Factory, statutes_loaded: dict[str, uuid.UUID]
) -> None:
    async with kb_factory() as session:
        await sync_statute_article(session, "4857", "18")
        await session.commit()
    stored = await chunks(kb_factory)
    assert [
        (c.text, str(c.valid_from), str(c.valid_to) if c.valid_to else None) for c in stored
    ] == [
        ("Madde 18 eski metin.", "2016-05-13", "2018-01-01"),
        ("Madde 18 yeni metin.", "2018-01-01", None),
    ]
    assert {c.parent_kind for c in stored} == {EXTRACTION}
    assert stored[0].ref == "4857 m.18"
    assert stored[0].header == (
        "4857 sayılı Kanun · m.18 · Feshin geçerli sebebe dayandırılması · yürürlük 2016-05-13"
    )
    assert {c.category.value for c in stored} == {"statute"}
    assert {c.license for c in stored} == {License.public}


async def test_publishing_an_article_moves_its_chunks_to_the_versions_and_a_repealed_one_has_none(
    kb_factory: Factory, statutes_loaded: dict[str, uuid.UUID], reviewer: AppUser
) -> None:
    async with kb_factory() as session:
        for article in ("18", "Geçici 1"):
            await sync_statute_article(session, "4857", article)
        await session.commit()
        await approve_statute_article(session, statutes_loaded["18"], reviewer.id)
        await approve_statute_article(session, statutes_loaded["Geçici 1"], reviewer.id)
        await session.commit()
    eighteen = [c for c in await chunks(kb_factory) if c.ref == "4857 m.18"]
    assert {c.parent_kind for c in eighteen} == {STATUTE_ARTICLE}
    assert all(c.version_id is not None for c in eighteen)
    first = [c for c in await chunks(kb_factory) if c.ref == "4857 Geçici 1"]
    assert [c.text for c in first] == ["Geçici Madde 1 geçerli metin."]  # the repealed stub is out


async def test_rejecting_an_article_removes_its_chunks(
    kb_factory: Factory, statutes_loaded: dict[str, uuid.UUID], reviewer: AppUser
) -> None:
    async with kb_factory() as session:
        await sync_statute_article(session, "4857", "5")
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Chunk)) == 1
        await reject_statute_article(session, statutes_loaded["5"], reviewer.id, "wrong")
        await session.commit()
    assert await chunks(kb_factory) == []


async def test_embedding_runs_in_batches_and_a_second_run_embeds_nothing(
    kb_factory: Factory, fake_embedder: FakeEmbedder
) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
        first = await embed_pending(session, fake_embedder)
        second = await embed_pending(session, fake_embedder)
    stored = await chunks(kb_factory)
    assert first.chunks == len(stored) and first.tokens > 0 and first.failed == 0
    assert second.chunks == 0
    assert {c.embedding_model for c in stored} == {fake_embedder.model_id}
    assert all(len(c.embedding) == 1024 for c in stored if c.embedding is not None)
    # the model is in the input: the header comes first, then the text
    assert fake_embedder.calls[0][0].startswith(stored[0].header or "")


async def test_a_new_model_embeds_everything_again(
    kb_factory: Factory, fake_embedder: FakeEmbedder
) -> None:
    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
        await embed_pending(session, fake_embedder)
        other = FakeEmbedder()
        other.model_id = "other-model:1024"
        report = await embed_pending(session, other)
    assert report.chunks == len(await chunks(kb_factory))


async def test_a_failing_batch_is_counted_and_left_for_the_next_run(kb_factory: Factory) -> None:
    class Broken(FakeEmbedder):
        async def embed(self, texts: Any) -> Any:
            raise RuntimeError("rate limit")

    source_id = await load_decision(kb_factory)
    async with kb_factory() as session:
        await sync_decision(session, source_id)
        await session.commit()
        report = await embed_pending(session, Broken())
    stored = await chunks(kb_factory)
    assert (report.chunks, report.failed) == (0, len(stored))
    assert all(c.embedding is None for c in stored)
