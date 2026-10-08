"""Statute review API (task 11c-1). The database tests are skipped when DATABASE_URL is unset; CI
sets it. Fixtures of conftest: the statute fixture (4857: "18" medium with a gap, "Geçici 1" and
"5" high, "Ek 2" low with a gap), loaded as `statutes_loaded`."""

import copy
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.db import make_engine
from app.loaders import statutes as statute_loader
from app.loaders.decisions import load, prepare, read_rows
from app.loaders.report import LoadCounts
from app.loaders.statutes_report import StatuteCounts
from app.main import app
from app.models.common import Extraction, Review
from app.models.statute import StatuteArticleVersion
from app.models.user import AppUser, UserRole

PASSWORD = "correct horse battery"
BASE = "/review/statutes"
Factory = async_sessionmaker[AsyncSession]
Ids = dict[str, uuid.UUID]
DECISIONS = Path(__file__).parent / "fixtures" / "decisions_fixture.jsonl"


@dataclass
class Login:
    id: uuid.UUID
    headers: dict[str, str]


async def _login_as(
    client: httpx.AsyncClient, factory: Factory, email: str, role: UserRole
) -> Login:
    async with factory() as session:
        user = AppUser(
            email=email, display_name=email, role=role, password_hash=hash_password(PASSWORD)
        )
        session.add(user)
        await session.commit()
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    client.cookies.clear()  # the tests authenticate with the Bearer token only
    return Login(user.id, {"Authorization": f"Bearer {response.json()['token']}"})


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
async def me(client: httpx.AsyncClient, kb_factory: Factory) -> Login:
    return await _login_as(client, kb_factory, "baran@x.test", UserRole.reviewer)


async def _list(
    client: httpx.AsyncClient, me: Login, **params: Any
) -> tuple[int, dict[str, dict[str, Any]]]:
    response = await client.get(BASE, params=params, headers=me.headers)
    assert response.status_code == 200
    body = response.json()
    return body["total"], {i["article_no"]: i for i in body["items"]}


async def _act(
    client: httpx.AsyncClient, me: Login, extraction_id: uuid.UUID, **body: Any
) -> httpx.Response:
    return await client.post(f"{BASE}/{extraction_id}", json=body, headers=me.headers)


def _error(response: httpx.Response, status: int, code: str) -> None:
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)


async def _as_of(client: httpx.AsyncClient, me: Login, article: str, day: str) -> dict[str, Any]:
    response = await client.get(
        f"/statutes/4857/articles/{article}", params={"as_of": day}, headers=me.headers
    )
    body: dict[str, Any] = response.json()
    return body


# --- queue ------------------------------------------------------------------------------------


async def test_the_queue_lists_the_pending_articles_by_statute_and_ordinal(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    response = await client.get(BASE, headers=me.headers)
    body = response.json()
    assert body["total"] == 4
    assert [i["article_no"] for i in body["items"]] == ["5", "18", "Geçici 1", "Ek 2"]
    a18 = next(i for i in body["items"] if i["article_no"] == "18")
    assert a18 == {
        "extraction_id": str(statutes_loaded["18"]),
        "source_id": a18["source_id"],
        "statute_number": "4857",
        "article_no": "18",
        "ordinal": 18,
        "heading": "Feshin geçerli sebebe dayandırılması",
        "band": "medium",
        "reasons": ["before_earliest_snapshot", "exception_effective"],
        "version_count": 2,
        "gap_count": 1,
        "latest_snapshot_date": "2026-04-22",
        "status": "pending",
    }


async def test_the_queue_filters_by_statute_band_and_search(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    assert (await _list(client, me, statute="4857"))[0] == 4
    assert (await _list(client, me, statute="5510"))[0] == 0
    total, items = await _list(client, me, band="high")
    assert (total, set(items)) == (2, {"Geçici 1", "5"})
    assert set((await _list(client, me, band="low"))[1]) == {"Ek 2"}
    # article number, or margin heading, in any Turkish case
    assert set((await _list(client, me, q="geçici"))[1]) == {"Geçici 1"}
    assert set((await _list(client, me, q="GEÇİCİ"))[1]) == {"Geçici 1"}
    assert set((await _list(client, me, q="FESHİN GEÇERLİ"))[1]) == {"18"}
    assert set((await _list(client, me, q="feshin"))[1]) == {"18"}
    assert set((await _list(client, me, q="18"))[1]) == {"18"}
    assert (await _list(client, me, q="no such"))[0] == 0
    assert (await _list(client, me, q="%"))[0] == 0  # a wildcard is a letter


async def test_the_queue_pages_like_the_decision_queue(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    response = await client.get(BASE, params={"limit": 2, "offset": 2}, headers=me.headers)
    body = response.json()
    assert (body["total"], [i["article_no"] for i in body["items"]]) == (4, ["Geçici 1", "Ek 2"])
    past = (await client.get(BASE, params={"offset": 10}, headers=me.headers)).json()
    assert (past["total"], past["items"]) == (4, [])
    for params in ({"limit": 0}, {"limit": 201}, {"offset": -1}, {"band": "x"}, {"status": "x"}):
        _error(await client.get(BASE, params=params, headers=me.headers), 422, "validation_error")


async def test_status_tabs_follow_the_reviews(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    await _act(client, me, statutes_loaded["Geçici 1"], action="approve")
    await _act(client, me, statutes_loaded["Ek 2"], action="reject", note="Tarih yanlış")
    assert set((await _list(client, me))[1]) == {"5", "18"}
    assert set((await _list(client, me, status="approved"))[1]) == {"Geçici 1"}
    assert set((await _list(client, me, status="rejected"))[1]) == {"Ek 2"}
    total, items = await _list(client, me, status="all")
    assert total == 4
    assert {n: i["status"] for n, i in items.items()} == {
        "5": "pending",
        "18": "pending",
        "Geçici 1": "approved",
        "Ek 2": "rejected",
    }


async def test_summary_counts_statute_band_and_status(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    await _act(client, me, statutes_loaded["5"], action="approve")
    await _act(client, me, statutes_loaded["Ek 2"], action="reject", note="x")
    body = (await client.get(f"{BASE}/summary", headers=me.headers)).json()
    rows = {(r["statute_number"], r["band"], r["status"]): r["count"] for r in body["items"]}
    assert rows == {
        ("4857", "high", "approved"): 1,
        ("4857", "high", "pending"): 1,
        ("4857", "medium", "pending"): 1,
        ("4857", "low", "rejected"): 1,
    }


# --- detail -----------------------------------------------------------------------------------


async def test_the_detail_has_a_timeline_of_versions_and_gaps_in_date_order(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    response = await client.get(f"{BASE}/{statutes_loaded['18']}", headers=me.headers)
    assert response.status_code == 200
    body = response.json()
    assert (body["statute_number"], body["article_no"], body["status"]) == ("4857", "18", "pending")
    assert body["statute_title"] == "İŞ KANUNU"
    assert body["heading"] == "Feshin geçerli sebebe dayandırılması"
    assert (body["band"], body["reasons"]) == (
        "medium",
        ["before_earliest_snapshot", "exception_effective"],
    )
    assert body["source_status"] == "analyzed"
    assert body["latest_snapshot_date"] == "2026-04-22"
    assert body["reviews"] == [] and body["live_extraction_id"] is None
    timeline = body["timeline"]
    assert [e["kind"] for e in timeline] == ["gap", "version", "version"]
    gap, first, second = timeline
    assert (gap["from"], gap["to"], gap["reason"]) == (
        "2003-06-10",
        "2016-05-13",
        "before_earliest_snapshot",
    )
    assert gap["known_amendments"][0]["law"] == "6552"
    assert "text" not in gap and "heading" not in gap  # a gap carries no article text
    assert (first["valid_from"], first["valid_to"]) == ("2016-05-13", "2018-01-01")
    assert (second["valid_from"], second["valid_to"]) == ("2018-01-01", None)
    assert second["text"] and second["change_kind"] == "amended"
    assert second["amending_ref"] and second["evidence"]["amendments"]
    assert set(second) >= {"heading", "evidence", "footnotes", "warnings", "confidence"}
    assert [(s["file_name"], s["date"]) for s in body["snapshots"]] == [
        ("4857 sayılı İş Kanunu 13.05.2016 .docx", "2016-05-13"),
        ("4857 sayılı İş Kanunu.pdf", "2026-04-22"),
    ]


async def test_the_detail_of_an_old_shape_extraction_has_no_snapshots(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, statutes_loaded: Ids
) -> None:
    async with kb_factory() as session:
        extraction = await session.get(Extraction, statutes_loaded["18"])
        assert extraction is not None
        extraction.fields = {k: v for k, v in extraction.fields.items() if k != "snapshots"}
        await session.commit()
    response = await client.get(f"{BASE}/{statutes_loaded['18']}", headers=me.headers)
    assert response.status_code == 200
    assert response.json()["snapshots"] == []


async def test_an_open_gap_comes_first(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    body = (await client.get(f"{BASE}/{statutes_loaded['Ek 2']}", headers=me.headers)).json()
    assert [e["kind"] for e in body["timeline"]] == ["gap", "version"]
    assert body["timeline"][0]["from"] is None


async def test_the_detail_shows_earlier_reviews_and_the_live_extraction(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    statutes_loaded: Ids,
    statute_record: dict[str, Any],
    extraction_ids: Any,
) -> None:
    await _act(client, me, statutes_loaded["Geçici 1"], action="approve")
    newer = copy.deepcopy(statute_record)
    newer["parser_version"] = "2"
    newer["articles"][1]["versions"][1]["text"] = "Geçici madde 1 değişmiş metin."
    await statute_loader.load(kb_factory, statute_loader.prepare([newer]), {}, StatuteCounts())
    new_id = (await extraction_ids("2"))["Geçici 1"]
    old = (await client.get(f"{BASE}/{statutes_loaded['Geçici 1']}", headers=me.headers)).json()
    assert old["status"] == "approved" and old["live_extraction_id"] is None
    assert [(r["decision"], r["reviewer_name"], r["note"]) for r in old["reviews"]] == [
        ("approve", "baran@x.test", None)
    ]
    # the new extraction of the same article waits and points to the one that is live
    fresh = (await client.get(f"{BASE}/{new_id}", headers=me.headers)).json()
    assert fresh["status"] == "pending"
    assert fresh["live_extraction_id"] == str(statutes_loaded["Geçici 1"])
    assert (await _act(client, me, new_id, action="approve")).status_code == 200
    # the old one is replaced now: not actionable, and it points to the new one
    old = (await client.get(f"{BASE}/{statutes_loaded['Geçici 1']}", headers=me.headers)).json()
    assert old["status"] == "superseded" and old["live_extraction_id"] == str(new_id)
    _error(
        await _act(client, me, statutes_loaded["Geçici 1"], action="approve"),
        409,
        "review_conflict",
    )


async def test_decision_and_statute_ids_are_not_interchangeable(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, statutes_loaded: Ids
) -> None:
    rows, _, _ = read_rows(DECISIONS)
    prepared, _ = prepare(rows, {})
    await load(kb_factory, prepared, LoadCounts())
    async with kb_factory() as session:
        decision_id = (
            await session.execute(
                select(Extraction.id).where(Extraction.parser_name == "decisions").limit(1)
            )
        ).scalar_one()
    _error(
        await client.get(f"{BASE}/{decision_id}", headers=me.headers), 404, "extraction_not_found"
    )
    _error(await _act(client, me, decision_id, action="approve"), 404, "extraction_not_found")
    _error(
        await client.get(f"/review/decisions/{statutes_loaded['18']}", headers=me.headers),
        404,
        "extraction_not_found",
    )
    _error(
        await client.post(
            f"/review/decisions/{statutes_loaded['18']}",
            json={"action": "approve"},
            headers=me.headers,
        ),
        404,
        "extraction_not_found",
    )
    _error(
        await client.get(f"{BASE}/{uuid.uuid4()}", headers=me.headers), 404, "extraction_not_found"
    )
    assert (await _list(client, me))[0] == 4  # the decisions are not in the article queue


# --- approve / reject ---------------------------------------------------------------------------


async def test_approving_publishes_the_article_for_as_of(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    # nothing of the statute is published yet: the statute itself is unknown
    assert (await _as_of(client, me, "18", "2020-01-01"))["error"]["code"] == "statute_not_found"
    response = await _act(client, me, statutes_loaded["18"], action="approve", note="ok")
    assert response.status_code == 200
    body = response.json()
    assert (body["source_status"], body["article_id"] is not None) == ("approved", True)
    found = await _as_of(client, me, "18", "2020-01-01")
    assert found["status"] == "found" and found["version"]["text"]
    assert (await _as_of(client, me, "18", "2010-01-01"))["status"] == "gap"
    detail = (await client.get(f"{BASE}/{statutes_loaded['18']}", headers=me.headers)).json()
    assert detail["status"] == "approved" and detail["source_status"] == "approved"
    assert [(r["decision"], r["note"]) for r in detail["reviews"]] == [("approve", "ok")]


async def test_rejecting_keeps_the_article_out_of_as_of_and_the_source_as_it_was(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, statutes_loaded: Ids
) -> None:
    response = await _act(client, me, statutes_loaded["18"], action="reject", note="Gap yanlış")
    assert response.status_code == 200
    body = response.json()
    assert (body["article_id"], body["source_status"]) == (None, "analyzed")
    await _act(client, me, statutes_loaded["5"], action="approve")  # the statute is published
    assert (await _as_of(client, me, "18", "2020-01-01"))["reason"] == "not_published"
    detail = (await client.get(f"{BASE}/{statutes_loaded['18']}", headers=me.headers)).json()
    assert detail["status"] == "rejected"
    assert [(r["decision"], r["note"]) for r in detail["reviews"]] == [("reject", "Gap yanlış")]
    async with kb_factory() as session:
        versions = (
            await session.execute(
                select(func.count())
                .select_from(StatuteArticleVersion)
                .where(StatuteArticleVersion.extraction_id == statutes_loaded["18"])
            )
        ).scalar_one()
    assert versions == 0


async def test_a_rejection_needs_a_note_and_an_edit_is_not_an_action(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    for body in (
        {"action": "reject"},
        {"action": "reject", "note": "   "},
        {"action": "edit", "edits": {}},
        {"action": "maybe"},
    ):
        response = await _act(client, me, statutes_loaded["18"], **body)
        _error(response, 422, "validation_error")
    assert (await _list(client, me))[0] == 4


async def test_a_second_review_of_the_same_extraction_conflicts(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, statutes_loaded: Ids
) -> None:
    await _act(client, me, statutes_loaded["18"], action="approve")
    await _act(client, me, statutes_loaded["5"], action="reject", note="x")
    for article in ("18", "5"):
        for body in ({"action": "approve"}, {"action": "reject", "note": "y"}):
            _error(await _act(client, me, statutes_loaded[article], **body), 409, "review_conflict")
    async with kb_factory() as session:
        reviews = (await session.execute(select(func.count()).select_from(Review))).scalar_one()
    assert reviews == 2


async def test_a_rejected_extraction_is_publishable_only_through_a_newer_one(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    statutes_loaded: Ids,
    statute_record: dict[str, Any],
    extraction_ids: Any,
) -> None:
    await _act(client, me, statutes_loaded["5"], action="reject", note="x")
    newer = copy.deepcopy(statute_record)
    newer["parser_version"] = "2"
    await statute_loader.load(kb_factory, statute_loader.prepare([newer]), {}, StatuteCounts())
    new_id = (await extraction_ids("2"))["5"]
    assert (await _list(client, me, status="rejected"))[0] == 0  # the newest one is not rejected
    _error(await _act(client, me, statutes_loaded["5"], action="approve"), 409, "review_conflict")
    assert (await _act(client, me, new_id, action="approve")).status_code == 200
    assert (await _as_of(client, me, "5", "2020-01-01"))["status"] == "found"


async def test_an_extraction_that_is_no_longer_the_newest_conflicts(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    statutes_loaded: Ids,
    statute_record: dict[str, Any],
) -> None:
    newer = copy.deepcopy(statute_record)
    newer["parser_version"] = "2"
    await statute_loader.load(kb_factory, statute_loader.prepare([newer]), {}, StatuteCounts())
    for body in ({"action": "approve"}, {"action": "reject", "note": "x"}):
        _error(await _act(client, me, statutes_loaded["18"], **body), 409, "review_conflict")
    old = (await client.get(f"{BASE}/{statutes_loaded['18']}", headers=me.headers)).json()
    assert old["status"] == "superseded"


# --- bulk approval ------------------------------------------------------------------------------


def _bulk(count: int, **body: Any) -> dict[str, Any]:
    return {"band": "high", "expected_count": count, **body}


async def test_bulk_approval_takes_the_high_band_only(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    for band in ("medium", "low"):
        response = await client.post(
            f"{BASE}/bulk-approve", json={**_bulk(1), "band": band}, headers=me.headers
        )
        _error(response, 422, "bulk_band_not_allowed")
    assert (await _list(client, me))[0] == 4


async def test_bulk_approval_refuses_a_count_that_is_not_the_one_on_screen(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    for count in (1, 3):
        response = await client.post(f"{BASE}/bulk-approve", json=_bulk(count), headers=me.headers)
        assert response.status_code == 409
        assert response.json() == {
            "error": {"code": "bulk_count_changed", "params": {"total": 2, "expected": count}}
        }
    assert (await _list(client, me, status="approved"))[0] == 0


async def test_bulk_approval_runs_in_steps_with_a_cursor(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    first = await client.post(f"{BASE}/bulk-approve", json=_bulk(2, limit=1), headers=me.headers)
    assert first.status_code == 200
    body = first.json()
    assert (body["published"], body["conflicts"], body["failed"], body["remaining"]) == (
        1,
        [],
        [],
        1,
    )
    assert body["next_cursor"]
    second = await client.post(
        f"{BASE}/bulk-approve",
        json=_bulk(1, limit=1, cursor=body["next_cursor"]),
        headers=me.headers,
    )
    assert second.json() == {
        "published": 1,
        "conflicts": [],
        "failed": [],
        "remaining": 0,
        "next_cursor": None,
    }
    total, items = await _list(client, me, status="approved")
    assert (total, set(items)) == (2, {"Geçici 1", "5"})
    assert (await _list(client, me))[0] == 2  # medium and low are left
    assert (await _as_of(client, me, "5", "2020-01-01"))["status"] == "found"
    assert (await _as_of(client, me, "18", "2020-01-01"))["reason"] == "not_published"


async def test_bulk_approval_skips_rejected_articles_and_can_be_limited_to_a_statute(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    await _act(client, me, statutes_loaded["5"], action="reject", note="x")
    other = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(0, statute="5510"), headers=me.headers
    )
    assert other.json()["published"] == 0
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(1, statute="4857"), headers=me.headers
    )
    assert response.json()["published"] == 1
    assert set((await _list(client, me, status="approved"))[1]) == {"Geçici 1"}
    assert set((await _list(client, me, status="rejected"))[1]) == {"5"}


async def test_bulk_input_is_validated(
    client: httpx.AsyncClient, me: Login, statutes_loaded: Ids
) -> None:
    for body in (_bulk(1, limit=101), _bulk(1, limit=0), _bulk(-1), _bulk(1, cursor="nope")):
        response = await client.post(f"{BASE}/bulk-approve", json=body, headers=me.headers)
        _error(response, 422, "validation_error")


# --- access -------------------------------------------------------------------------------------


async def test_every_route_asks_for_a_login(
    client: httpx.AsyncClient, statutes_loaded: Ids
) -> None:
    some = statutes_loaded["18"]
    responses = [
        await client.get(BASE),
        await client.get(f"{BASE}/summary"),
        await client.get(f"{BASE}/{some}"),
        await client.post(f"{BASE}/{some}", json={"action": "approve"}),
        await client.post(f"{BASE}/bulk-approve", json=_bulk(2)),
    ]
    assert [r.status_code for r in responses] == [401] * 5
    assert {r.json()["error"]["code"] for r in responses} == {"unauthorized"}


async def test_an_admin_may_review_too(
    client: httpx.AsyncClient, kb_factory: Factory, statutes_loaded: Ids
) -> None:
    admin = await _login_as(client, kb_factory, "orhan@x.test", UserRole.admin)
    assert (await _list(client, admin))[0] == 4
    assert (await _act(client, admin, statutes_loaded["5"], action="approve")).status_code == 200
