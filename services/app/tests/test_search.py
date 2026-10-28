"""`GET /kb/search` (task 14). The database tests are skipped when DATABASE_URL is unset; CI sets
it. Embeddings come from a fake client."""

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.chunk_index import embed_pending, sync_decision, sync_statute_article
from app.db import make_engine
from app.embeddings import Embedder, get_embedder
from app.kb import approve_extraction
from app.main import app
from app.models.chunk import Chunk
from app.models.common import Extraction, License, RecordStatus, Source
from app.models.user import AppUser, UserRole
from app.search import _tsquery
from app.settings import Settings, get_settings
from tests.conftest import FakeEmbedder
from tests.test_chunk_index import SUMMARY, load_decision

PASSWORD = "correct horse battery"
Factory = async_sessionmaker[AsyncSession]
SettingsFor = Callable[[bool], None]


@pytest.fixture
async def client(database_url: str, kb_factory: Factory) -> AsyncIterator[httpx.AsyncClient]:
    app.state.engine = make_engine(database_url)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        await app.state.engine.dispose()


@pytest.fixture
async def headers(client: httpx.AsyncClient, kb_factory: Factory) -> dict[str, str]:
    async with kb_factory() as session:
        session.add(
            AppUser(
                email="user@x.test",
                display_name="User",
                role=UserRole.reviewer,
                password_hash=hash_password(PASSWORD),
            )
        )
        await session.commit()
    response = await client.post("/auth/login", json={"email": "user@x.test", "password": PASSWORD})
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def configure(fake_embedder: FakeEmbedder) -> SettingsFor:
    def set_up(include_unreviewed: bool) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(
            kb_search_include_unreviewed=include_unreviewed
        )
        embedder: Embedder = fake_embedder
        app.dependency_overrides[get_embedder] = lambda: embedder

    return set_up


async def index_all(factory: Factory, embedder: FakeEmbedder, *, articles: bool = True) -> None:
    async with factory() as session:
        for source_id in (await session.execute(select(Source.id))).scalars().all():
            if not articles:
                await sync_decision(session, source_id)
        if articles:
            for article in ("18", "Geçici 1", "5"):
                await sync_statute_article(session, "4857", article)
        await session.commit()
        await embed_pending(session, embedder)


async def search(
    client: httpx.AsyncClient, headers: dict[str, str], **params: Any
) -> list[dict[str, Any]]:
    response = await client.get("/kb/search", params=params, headers=headers)
    assert response.status_code == 200, response.text
    results: list[dict[str, Any]] = response.json()["results"]
    return results


def test_the_tsquery_folds_turkish_capitals() -> None:
    assert _tsquery("İşe iade") == "işe | iade"
    assert _tsquery("ISIK") == "ısık"
    assert _tsquery("işe iade, işe") == "işe | iade"


async def test_search_needs_a_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/kb/search", params={"q": "kıdem"})).status_code == 401


async def test_a_statute_search_returns_the_version_in_force_on_as_of(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    configure(True)
    await index_all(kb_factory, fake_embedder)

    async def eighteen(as_of: str) -> list[tuple[str, str, str | None]]:
        found = await search(client, headers, q="Madde 18 metin", category="statute", as_of=as_of)
        return [
            (r["matches"][0]["text"], r["valid_from"], r["valid_to"])
            for r in found
            if r["ref"] == "4857 m.18"
        ]

    assert await eighteen("2017-06-01") == [("Madde 18 eski metin.", "2016-05-13", "2018-01-01")]
    assert await eighteen("2020-01-01") == [("Madde 18 yeni metin.", "2018-01-01", None)]
    # a day in the gap before the first version: the article has no version in force
    assert await eighteen("2015-01-01") == []


async def test_unreviewed_records_show_only_while_the_setting_is_on(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    configure(False)
    assert await search(client, headers, q="işe iade kıdem") == []
    configure(True)
    results = await search(client, headers, q="işe iade kıdem")
    assert len(results) == 1 and results[0]["review_status"] == "analyzed"
    assert results[0]["category"] == "decision"


async def test_approved_records_show_with_the_setting_off(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    reviewer: AppUser,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    async with kb_factory() as session:
        extraction_id = (await session.execute(select(Extraction.id))).scalars().one()
        await approve_extraction(session, extraction_id, reviewer.id)
        await session.commit()
    configure(False)
    results = await search(client, headers, q="işe iade kıdem")
    assert len(results) == 1 and results[0]["review_status"] == "approved"
    assert results[0]["verification"] is not None


async def test_a_rejected_status_is_not_searched_even_if_a_chunk_is_left(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    async with kb_factory() as session:
        await session.execute(update(Source).values(status=RecordStatus.rejected))
        await session.commit()
    configure(True)
    assert await search(client, headers, q="işe iade kıdem") == []


async def test_internal_only_text_is_never_returned(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    configure(True)
    # only the editorial summary has these words
    results = await search(client, headers, q="Editoryal özet")
    assert len(results) == 1
    shown = results[0]["matches"]
    assert shown and all(m["text"] != SUMMARY for m in shown)
    async with kb_factory() as session:
        internal = (
            (await session.execute(select(Chunk.id).where(Chunk.license == License.internal_only)))
            .scalars()
            .all()
        )
    assert internal and not {m["chunk_id"] for m in shown} & {str(i) for i in internal}
    assert (
        SUMMARY
        not in (
            await client.get("/kb/search", params={"q": "Editoryal özet"}, headers=headers)
        ).text
    )


async def test_filters_and_validation(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    configure(True)
    assert await search(client, headers, q="işe iade", category="statute") == []
    assert len(await search(client, headers, q="işe iade", category="decision")) == 1
    assert await search(client, headers, q="işe iade", as_of="1990-01-01") == []
    assert await search(client, headers, q="işe iade", date_from="2999-01-01") == []
    assert (
        await client.get("/kb/search", params={"q": "x", "limit": 51}, headers=headers)
    ).status_code == 422
    assert (await client.get("/kb/search", headers=headers)).status_code == 422


async def test_without_an_embedder_the_search_is_full_text_only(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    app.dependency_overrides[get_settings] = lambda: Settings(kb_search_include_unreviewed=True)
    app.dependency_overrides[get_embedder] = lambda: None
    response = await client.get("/kb/search", params={"q": "işe iade"}, headers=headers)
    assert response.json()["mode"] == "fulltext" and len(response.json()["results"]) == 1


async def test_a_capital_dotted_i_query_finds_the_lowercase_text(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    configure(True)
    app.dependency_overrides[get_embedder] = lambda: None
    assert len(await search(client, headers, q="İADE")) == 1
