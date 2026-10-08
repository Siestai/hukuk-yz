"""Statute API (task 11b). The database tests are skipped when DATABASE_URL is unset; CI sets it.

The corpus test at the end also needs a real `statutes.jsonl` (`hukuk-ingest statutes ...`); CI
has none and skips it. Run it with

    DATABASE_URL=... HUKUK_STATUTES_JSONL=data/work/statutes/statutes.jsonl \\
        uv run pytest services/app/tests/test_statutes.py -k golden
"""

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.db import make_engine
from app.loaders import statutes as statute_loader
from app.loaders.statutes_report import StatuteCounts
from app.main import app
from app.models.user import AppUser, UserRole
from app.statutes import normalize_article_no
from hukuk_ingest.statutes.golden import check_golden, load_golden
from hukuk_models import Band

PASSWORD = "correct horse battery"
Factory = async_sessionmaker[AsyncSession]


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("18", "18"),
        ("18/A", "18/A"),
        ("18-a", "18/A"),
        ("Geçici 4", "Geçici 4"),
        ("gecici-4", "Geçici 4"),
        ("Gecici 4", "Geçici 4"),
        ("GECICI_4", "Geçici 4"),
        ("ek-2", "Ek 2"),
        ("Ek 2", "Ek 2"),
        ("ek-2-b", "Ek 2/B"),
        ("geçici 4", "Geçici 4"),
        ("GEÇİCİ 4", "Geçici 4"),
        ("GECİCİ 4", "Geçici 4"),
        ("Gecici-4", "Geçici 4"),
        ("EK 2", "Ek 2"),
        ("gecici-79-2", "Geçici 79 (2)"),
        ("Geçici 79 (2)", "Geçici 79 (2)"),
        ("GEÇİCİ 79(2)", "Geçici 79 (2)"),
        ("18-ı", "18/I"),
        ("18-i", "18/İ"),
        ("  Geçici   104 ", "Geçici 104"),
        ("madde 4", "madde 4"),  # not an alias: left to the lookup, which will not find it
    ],
)
def test_ascii_aliases_are_normalized_to_the_canonical_article_number(
    raw: str, canonical: str
) -> None:
    assert normalize_article_no(raw) == canonical


@pytest.fixture
async def client(database_url: str, kb_factory: Factory) -> AsyncIterator[httpx.AsyncClient]:
    app.state.engine = make_engine(database_url)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as c:
            yield c
    finally:
        await app.state.engine.dispose()


@pytest.fixture
async def headers(client: httpx.AsyncClient, kb_factory: Factory) -> dict[str, str]:
    """A logged-in user without any review role: the API asks for a login only."""
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
    client.cookies.clear()  # the tests authenticate with the Bearer token only
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def _get(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    article: str,
    as_of: str,
    number: str = "4857",
) -> httpx.Response:
    return await client.get(
        f"/statutes/{number}/articles/{article}", params={"as_of": as_of}, headers=headers
    )


# Golden queries of the reduced fixture (fixtures/statutes_fixture.jsonl): article, date,
# status, a phrase of the text for `found` / the stub for a repealed article.
FOUND = [
    ("18", "2016-05-13", "Madde 18 eski"),
    ("18", "2017-12-31", "Madde 18 eski"),
    ("18", "2018-01-01", "Madde 18 yeni"),
    ("Geçici 1", "2009-12-31", "Geçici Madde 1 geçerli"),
    ("Ek 2", "2016-05-13", "Ek Madde 2"),
]


@pytest.mark.parametrize(("article", "day", "phrase"), FOUND)
async def test_found_returns_the_text_in_force_on_the_date(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    statutes_published: dict[str, uuid.UUID],
    article: str,
    day: str,
    phrase: str,
) -> None:
    response = await _get(client, headers, article, day)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "found"
    assert phrase in body["version"]["text"]
    assert body["version"]["valid_from"] <= day
    assert body["confidence"] == body["version"]["confidence"]
    assert body["latest_snapshot_date"] == "2026-04-22"
    assert body["stale"] is False
    assert "reason" not in body and "gap" not in body


async def test_a_found_version_carries_its_label_evidence_and_footnotes(
    client: httpx.AsyncClient, headers: dict[str, str], statutes_published: dict[str, uuid.UUID]
) -> None:
    body = (await _get(client, headers, "18", "2020-01-01")).json()
    version = body["version"]
    assert version["amending_ref"] == "7036 (12/10/2017)"
    assert version["heading"] == "Feshin geçerli sebebe dayandırılması"
    assert (version["valid_from"], version["valid_to"]) == ("2018-01-01", None)
    assert version["evidence"]["basis"] == "exception"
    assert version["evidence"]["amendments"][0]["law"] == "7036"
    assert version["footnotes"] == [{"marker": "1", "text": "Dipnot metni."}]
    assert (version["warnings"], body["confidence"]) == (["exception_effective"], "medium")
    low = (await _get(client, headers, "Ek 2", "2020-01-01")).json()
    assert low["confidence"] == "low"  # the consumer must see it


@pytest.mark.parametrize(
    ("article", "day", "start", "end"),
    [
        ("18", "2003-06-10", "2003-06-10", "2016-05-13"),
        ("18", "2014-01-01", "2003-06-10", "2016-05-13"),
        ("18", "2016-05-12", "2003-06-10", "2016-05-13"),
        ("Ek 2", "2010-01-01", None, "2016-05-13"),
    ],
)
async def test_a_gap_names_the_known_amendments_and_carries_no_text(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    statutes_published: dict[str, uuid.UUID],
    article: str,
    day: str,
    start: str | None,
    end: str,
) -> None:
    response = await _get(client, headers, article, day)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "gap"
    assert body["gap"]["from"] == start and body["gap"]["to"] == end
    assert body["gap"]["reason"] == "before_earliest_snapshot"
    assert set(body["gap"]) == {"from", "to", "reason", "known_amendments"}
    assert set(body) == {"status", "gap", "latest_snapshot_date", "stale"}
    assert "text" not in response.text and "eski metin" not in response.text
    if article == "18":
        assert body["gap"]["known_amendments"] == [
            {"law": "6552", "date": "2014-09-10", "kind": "ek", "scope": "cümle"}
        ]


async def test_a_date_after_the_newest_snapshot_is_found_but_stale(
    client: httpx.AsyncClient, headers: dict[str, str], statutes_published: dict[str, uuid.UUID]
) -> None:
    body = (await _get(client, headers, "18", "2026-04-23")).json()
    assert (body["status"], body["stale"]) == ("found", True)
    assert "Madde 18 yeni" in body["version"]["text"]


async def test_not_in_force_before_the_article_existed_and_after_it_was_repealed(
    client: httpx.AsyncClient, headers: dict[str, str], statutes_published: dict[str, uuid.UUID]
) -> None:
    before = (await _get(client, headers, "18", "2003-06-09")).json()
    assert before["status"] == "not_in_force"
    assert set(before) == {"status", "latest_snapshot_date", "stale"}
    repealed = (await _get(client, headers, "Geçici 1", "2010-01-01")).json()
    assert (repealed["status"], repealed["reason"]) == ("not_in_force", "repealed")
    assert repealed["version"]["change_kind"] == "repealed"
    assert "confidence" not in repealed


async def test_an_article_that_is_not_published_is_unknown_with_a_reason(
    client: httpx.AsyncClient, headers: dict[str, str], statutes_published: dict[str, uuid.UUID]
) -> None:
    for article in ("5", "99"):  # loaded but never approved; not in the fixture at all
        response = await _get(client, headers, article, "2020-01-01")
        assert response.status_code == 200
        assert response.json() == {"status": "unknown_article", "reason": "not_published"}


@pytest.mark.parametrize(
    "article",
    ["Ge%C3%A7ici%201", "Geçici 1", "gecici-1", "Gecici%201", "GECICI_1", "GEÇİCİ 1", "geçici 1"],
)
async def test_an_article_number_may_be_encoded_or_an_ascii_alias(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    statutes_published: dict[str, uuid.UUID],
    article: str,
) -> None:
    body = (await _get(client, headers, article, "2009-12-31")).json()
    assert body["status"] == "found"
    assert "Geçici Madde 1" in body["version"]["text"]
    ek = (await _get(client, headers, "ek-2", "2020-01-01")).json()
    assert "Ek Madde 2" in ek["version"]["text"]


async def test_errors_are_codes(
    client: httpx.AsyncClient, headers: dict[str, str], statutes_published: dict[str, uuid.UUID]
) -> None:
    unknown = await _get(client, headers, "18", "2020-01-01", number="9999")
    assert unknown.status_code == 404
    assert unknown.json() == {"error": {"code": "statute_not_found", "params": {"number": "9999"}}}
    for bad in ("2020-13-01", "20200101", "2020-1-1", "2014-W01-1", "yesterday", ""):
        response = await _get(client, headers, "18", bad)
        assert response.status_code == 422, bad
        assert response.json() == {"error": {"code": "invalid_date", "params": {"field": "as_of"}}}
    missing = await client.get("/statutes/4857/articles/18", headers=headers)
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "validation_error")


async def test_the_api_asks_for_a_login(
    client: httpx.AsyncClient, statutes_published: dict[str, uuid.UUID]
) -> None:
    response = await client.get("/statutes/4857/articles/18", params={"as_of": "2020-01-01"})
    assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthorized")


GOLDEN = Path(__file__).parents[3] / "packages/ingest/tests/fixtures/statutes/golden.toml"
STATUTES_JSONL = os.environ.get("HUKUK_STATUTES_JSONL")


@pytest.mark.skipif(not STATUTES_JSONL, reason="HUKUK_STATUTES_JSONL (real statutes.jsonl) not set")
async def test_golden_queries_through_the_database_and_the_api(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    kb_factory: Factory,
    reviewer: AppUser,
) -> None:
    """The golden set of the ingest tests, but through load -> approve -> publish -> HTTP."""
    assert STATUTES_JSONL
    records, errors = statute_loader.read_records(Path(STATUTES_JSONL))
    assert not errors
    counts = StatuteCounts()
    await statute_loader.load(kb_factory, statute_loader.prepare(records), {}, counts)
    bands: tuple[Band, ...] = ("high", "medium", "low")
    for band in bands:
        await statute_loader.approve_band(kb_factory, band, reviewer.id, counts)
    failures = [f"publish failed {ref}: {reason}" for ref, reason in counts.publish_failed]
    for q in load_golden(GOLDEN):
        response = await _get(client, headers, q["article"], str(q["as_of"]), number=q["statute"])
        if response.status_code != 200:
            failures.append(f"{q['statute']} m.{q['article']}: HTTP {response.status_code}")
        elif failure := check_golden(q, response.json()):
            failures.append(failure)
    assert not failures, "\n".join(failures)
