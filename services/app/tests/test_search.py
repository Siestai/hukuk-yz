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
from app.chunk_index import (
    embed_pending,
    sync_admin_act_section,
    sync_decision,
    sync_statute_article,
)
from app.db import make_engine
from app.embeddings import Embedder, get_embedder
from app.kb import approve_extraction, approve_statute_article, reject_statute_article
from app.loaders import statutes as statute_loader
from app.loaders.statutes_report import StatuteCounts
from app.main import app
from app.models.chunk import Chunk
from app.models.common import (
    Extraction,
    License,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
)
from app.models.user import AppUser, UserRole
from app.search import _tsquery
from app.settings import Settings, get_settings
from tests.conftest import FakeEmbedder
from tests.test_chunk_index import SUMMARY, load_decision
from tests.test_loaders_admin_acts import TEXT, act_record, load_acts

PASSWORD = "correct horse battery"
Factory = async_sessionmaker[AsyncSession]
SettingsFor = Callable[[tuple[str, ...]], None]
OFF: tuple[str, ...] = ()
TEST_BANDS = ("high", "medium")


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
    def set_up(bands: tuple[str, ...]) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(kb_test_source_bands=bands)
        embedder: Embedder = fake_embedder
        app.dependency_overrides[get_embedder] = lambda: embedder

    return set_up


async def index_all(factory: Factory, embedder: FakeEmbedder, *, articles: bool = True) -> None:
    async with factory() as session:
        for source_id in (await session.execute(select(Source.id))).scalars().all():
            if not articles:
                await sync_decision(session, source_id)
        if articles:
            for article in ("18", "Geçici 1", "Ek 2", "5"):
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
    configure(TEST_BANDS)
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


async def set_band(factory: Factory, band: str) -> None:
    """The confidence band of every loaded extraction, as the loader would have set it."""
    async with factory() as session:
        await session.execute(update(Extraction).values(confidence={"band": band, "reasons": []}))
        await session.commit()


async def test_unreviewed_records_show_only_in_the_listed_bands(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_decision(kb_factory)
    await index_all(kb_factory, fake_embedder, articles=False)
    await set_band(kb_factory, "medium")
    configure(OFF)
    assert await search(client, headers, q="işe iade kıdem") == []
    configure(("high",))
    assert await search(client, headers, q="işe iade kıdem") == []
    configure(TEST_BANDS)
    results = await search(client, headers, q="işe iade kıdem")
    assert len(results) == 1 and results[0]["category"] == "decision"
    assert (results[0]["review_status"], results[0]["band"]) == ("analyzed", "medium")
    await set_band(kb_factory, "low")
    assert await search(client, headers, q="işe iade kıdem") == []


async def test_unreviewed_articles_are_searched_by_band_and_never_when_rejected(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    reviewer: AppUser,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await index_all(kb_factory, fake_embedder)

    async def articles() -> dict[str, tuple[str, str | None]]:
        found = await search(client, headers, q="Madde metin metni", category="statute")
        return {r["ref"]: (r["review_status"], r["band"]) for r in found}

    configure(OFF)
    assert await articles() == {}
    configure(TEST_BANDS)
    # "Ek 2" is in the low band: indexed, never returned
    assert await articles() == {
        "4857 m.18": ("analyzed", "medium"),
        "4857 m.5": ("analyzed", "high"),
        "4857 Geçici 1": ("analyzed", "high"),
    }
    async with kb_factory() as session:
        await reject_statute_article(session, statutes_loaded["5"], reviewer.id, "wrong text")
        await approve_statute_article(session, statutes_loaded["18"], reviewer.id)
        await session.commit()
    assert await articles() == {
        "4857 m.18": ("approved", None),
        "4857 Geçici 1": ("analyzed", "high"),
    }
    configure(OFF)
    assert await articles() == {"4857 m.18": ("approved", None)}


async def test_a_superseded_or_rejected_extraction_is_not_searched_even_if_its_chunks_are_left(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    statutes_loaded: dict[str, uuid.UUID],
    statute_record: dict[str, Any],
    reviewer: AppUser,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await index_all(kb_factory, fake_embedder)
    configure(TEST_BANDS)

    async def refs() -> set[str]:
        found = await search(client, headers, q="Madde metin metni", category="statute")
        return {r["ref"] for r in found}

    assert await refs() == {"4857 m.18", "4857 m.5", "4857 Geçici 1"}
    # a reject review alone, without the index being synced
    async with kb_factory() as session:
        session.add(
            Review(
                extraction_id=statutes_loaded["5"],
                reviewer_id=reviewer.id,
                decision=ReviewDecision.reject,
            )
        )
        await session.commit()
    assert await refs() == {"4857 m.18", "4857 Geçici 1"}
    # a newer extraction in the low band; the loader does not touch the index
    newer = {**statute_record, "parser_version": "2"}
    newer["articles"] = [{**a, "confidence": "low"} for a in statute_record["articles"]]
    await statute_loader.load(kb_factory, statute_loader.prepare([newer]), {}, StatuteCounts())
    assert await refs() == set()


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
    configure(OFF)
    results = await search(client, headers, q="işe iade kıdem")
    assert len(results) == 1
    assert (results[0]["review_status"], results[0]["band"]) == ("approved", None)
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
    configure(TEST_BANDS)
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
    configure(TEST_BANDS)
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
    configure(TEST_BANDS)
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
    app.dependency_overrides[get_settings] = lambda: Settings(kb_test_source_bands=TEST_BANDS)
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
    configure(TEST_BANDS)
    app.dependency_overrides[get_embedder] = lambda: None
    assert len(await search(client, headers, q="İADE")) == 1


async def test_search_service_key_is_scoped_to_kb(
    client: httpx.AsyncClient,
    configure: SettingsFor,
) -> None:
    from pydantic import SecretStr

    from app.settings import get_settings

    configure(OFF)
    original = app.dependency_overrides[get_settings]()
    original.kb_service_key = SecretStr("test-kb-key-18")
    app.dependency_overrides[get_settings] = lambda: original
    assert (
        await client.get("/kb/search?q=test", headers={"X-Service-Key": "wrong"})
    ).status_code == 401
    response = await client.get("/kb/search?q=test", headers={"X-Service-Key": "test-kb-key-18"})
    assert response.status_code == 200
    assert response.json()["results"] == []


async def _index_sections(factory: Factory, embedder: FakeEmbedder) -> None:
    async with factory() as session:
        for section in ("1", "1.1", "1.2", "1.4", "2"):
            await sync_admin_act_section(session, "2020/8", section)
        await session.commit()
        await embed_pending(session, embedder)


async def test_unreviewed_genelge_sections_are_searched_by_band_and_never_when_rejected(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    reviewer: AppUser,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_acts(kb_factory)
    await _index_sections(kb_factory, fake_embedder)

    async def sections() -> dict[str, tuple[str, str | None]]:
        found = await search(
            client, headers, q="idari para cezaları bildirge numara işlem", category="admin_act"
        )
        return {r["ref"]: (r["review_status"], r["band"]) for r in found}

    configure(OFF)
    assert await sections() == {}
    configure(("high",))
    assert await sections() == {
        "2020/8 m.1": ("analyzed", "high"),
        "2020/8 m.2": ("analyzed", "high"),
    }
    configure(TEST_BANDS)
    # "1.4" is in the low band: indexed, never returned ("1.1" is repealed and has no chunk)
    assert await sections() == {
        "2020/8 m.1": ("analyzed", "high"),
        "2020/8 m.1.2": ("analyzed", "medium"),
        "2020/8 m.2": ("analyzed", "high"),
    }
    async with kb_factory() as session:
        extraction_id = (
            await session.execute(
                select(Extraction.id).where(Extraction.fields["section_no"].as_string() == "2")
            )
        ).scalar_one()
        session.add(
            Review(
                extraction_id=extraction_id, reviewer_id=reviewer.id, decision=ReviewDecision.reject
            )
        )
        await session.commit()
    assert set(await sections()) == {"2020/8 m.1", "2020/8 m.1.2"}


async def test_the_old_chunk_of_a_reloaded_genelge_section_is_not_served(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    fake_embedder: FakeEmbedder,
    configure: SettingsFor,
) -> None:
    await load_acts(kb_factory)
    await _index_sections(kb_factory, fake_embedder)
    configure(TEST_BANDS)
    before = await search(client, headers, q="bildirge on gün içinde", category="admin_act")
    assert "2020/8 m.1.2" in {r["ref"] for r in before}

    # a reload with a changed section adds a newer extraction; the index still holds the old chunk
    await load_acts(kb_factory, act_record(TEXT.replace("on gün", "on beş gün")))

    after = await search(client, headers, q="bildirge on gün içinde", category="admin_act")
    assert "2020/8 m.1.2" not in {r["ref"] for r in after}
    await _index_sections(kb_factory, fake_embedder)
    again = await search(client, headers, q="bildirge on beş gün içinde", category="admin_act")
    (hit,) = [r for r in again if r["ref"] == "2020/8 m.1.2"]
    assert "on beş gün" in hit["matches"][0]["text"]
