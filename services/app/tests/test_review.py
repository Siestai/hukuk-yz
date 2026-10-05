"""Review API (task 09). The database tests are skipped when DATABASE_URL is unset; CI sets it."""

import asyncio
import dataclasses
import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.db import make_engine
from app.loaders.decisions import load, prepare
from app.loaders.normalize import OUTCOMES
from app.loaders.report import LoadCounts, PreparedRecord
from app.main import app
from app.models.common import (
    Court,
    CourtLevel,
    Extraction,
    IngestFile,
    Jurisdiction,
    RecordStatus,
    Review,
    ReviewDecision,
    Source,
    TextCompleteness,
)
from app.models.decision import Decision
from app.models.user import AppUser, UserRole
from app.settings import Settings
from hukuk_ingest.decisions.parse import DecisionRecord
from hukuk_models import DecisionEdits, SourceStatus

PASSWORD = "correct horse battery"
BASE = "/review/decisions"
Factory = async_sessionmaker[AsyncSession]
NewDecision = Callable[..., Awaitable[uuid.UUID]]  # the `new_decision` fixture of conftest


@dataclass
class Login:
    id: uuid.UUID
    headers: dict[str, str]


async def _login_as(
    client: httpx.AsyncClient, factory: Factory, email: str, role: UserRole
) -> Login:
    async with factory() as session:
        user = AppUser(
            email=email,
            display_name=email,
            role=role,
            password_hash=hash_password(PASSWORD),
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


# --- data -------------------------------------------------------------------------------------

RECORD: dict[str, Any] = {
    "journal_issue": 3,
    "layout": "era2",
    "court": "yargitay",
    "court_level": "daire",
    "chamber": "9. HD",
    "jurisdiction": "adli",
    "decision_date": "2019-03-12",
    "outcome": "bozma",
    "editorial_summary": "Özet",
    "full_text": "gerekçe " * 50,
    "text_completeness": "full",
}


async def _seed(factory: Factory, *overrides: dict[str, Any]) -> list[PreparedRecord]:
    """One loaded decision per override, numbered 1..n (sha256 ascending with n, title "n"
    unless `source_path` is given); a complete record is `high`."""
    rows = [
        DecisionRecord(
            **{
                **RECORD,
                "source_path": f"Yargi/{n}.pdf",
                "sha256": f"{n:064x}",
                "journal_page": n,
                "esas_no": f"2017/{n}",
                "karar_no": f"2019/{n}",
                **o,
            }
        ).to_dict()
        for n, o in enumerate(overrides, 1)
    ]
    prepared, _ = prepare(rows, {})
    await load(factory, prepared, LoadCounts())
    return prepared


async def _eid(factory: Factory, record: PreparedRecord, version: str | None = None) -> uuid.UUID:
    async with factory() as session:
        return (
            await session.execute(
                select(Extraction.id)
                .join(IngestFile, IngestFile.id == Extraction.file_id)
                .where(
                    IngestFile.sha256 == record.sha256,
                    Extraction.parser_version == (version or record.parser_version),
                )
            )
        ).scalar_one()


async def _count(factory: Factory, model: Any) -> int:
    async with factory() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _status(factory: Factory, extraction_id: uuid.UUID) -> RecordStatus:
    async with factory() as session:
        return (
            await session.execute(
                select(Source.status)
                .join(Extraction, Extraction.source_id == Source.id)
                .where(Extraction.id == extraction_id)
            )
        ).scalar_one()


MEDIUM = {"warnings": ["date_from_closing"], "journal_issue": 5}  # score 75
SPREAD: tuple[dict[str, Any], ...] = (
    {},  # 1: high, 100
    MEDIUM,  # 2
    {"court": "aym", "court_level": "aym", "chamber": "", "esas_no": ""},  # 3: low, 40
    {  # 4: medium, 50
        "warnings": ["date_from_closing", "body_start_approximate"],
        "source_path": "Yargi/Özel Dosya.pdf",
        "esas_no": "2018/777",
    },
    {},  # 5: high, 100
)


async def _ids(factory: Factory, prepared: list[PreparedRecord], *numbers: int) -> list[uuid.UUID]:
    return [await _eid(factory, prepared[n - 1]) for n in numbers]


# --- list -------------------------------------------------------------------------------------


async def test_the_list_holds_the_newest_extraction_of_analyzed_sources_only(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, {}, {}, {})
    await load(kb_factory, [dataclasses.replace(prepared[0], parser_version="6")], LoadCounts())
    async with kb_factory() as session:
        source_id = (
            await session.execute(
                select(Extraction.source_id).where(
                    Extraction.id == await _eid(kb_factory, prepared[2])
                )
            )
        ).scalar_one()
        await session.execute(
            text("UPDATE source SET status = 'approved' WHERE id = :id"), {"id": source_id}
        )
        await session.commit()

    body = (await client.get(BASE, headers=me.headers)).json()
    assert body["total"] == 2
    assert {i["extraction_id"] for i in body["items"]} == {
        str(await _eid(kb_factory, prepared[0], "6")),
        str(await _eid(kb_factory, prepared[1])),
    }


async def test_the_list_filters_and_sorts(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    ids = dict(enumerate(map(str, await _ids(kb_factory, prepared, 1, 2, 3, 4, 5)), 1))

    async def listed(**params: Any) -> list[str]:
        response = await client.get(BASE, params=params, headers=me.headers)
        assert response.status_code == 200
        return [i["extraction_id"] for i in response.json()["items"]]

    def of(*numbers: int) -> list[str]:
        return [ids[n] for n in numbers]

    assert await listed() == of(3, 4, 2, 1, 5)  # most suspicious first, ties by sha256
    assert await listed(sort="score_desc") == of(1, 5, 2, 4, 3)
    assert await listed(band="medium") == of(4, 2)
    assert await listed(band="low") == of(3)
    assert await listed(court="aym") == of(3)
    assert await listed(reason="date_from_closing") == of(4, 2)
    assert await listed(reason="body_start_approximate") == of(4)
    assert await listed(journal_issue=5) == of(2)
    assert await listed(q="2018/777") == of(4)
    assert await listed(q="2019/1") == of(1)
    assert await listed(q="Dosya") == of(4)  # title
    assert await listed(q="%") == []  # not a wildcard
    assert await listed(band="medium", reason="body_start_approximate", court="yargitay") == of(4)


async def test_the_list_pages_with_a_total_and_describes_each_item(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    body = (await client.get(BASE, params={"limit": 1, "offset": 1}, headers=me.headers)).json()
    assert body["total"] == 5
    (item,) = body["items"]
    assert item == {
        "extraction_id": str(await _eid(kb_factory, prepared[3])),
        "source_id": item["source_id"],
        "source_status": "analyzed",
        "title": "Özel Dosya",
        "court": "yargitay",
        "chamber": "9. HD",
        "esas_no": "2018/777",
        "karar_no": "2019/4",
        "decision_date": "2019-03-12",
        "journal_issue": 3,
        "band": "medium",
        "score": 50,
        "reasons": ["date_from_closing", "body_start_approximate"],
        "duplicate_group": None,
        "reviewed_at": None,
        "reviewer_name": None,
        "review_decision": None,
        "note": None,
    }
    assert "full_text" not in item


@pytest.mark.parametrize("limit", [0, 201])
async def test_the_list_limit_is_capped(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, limit: int
) -> None:
    response = await client.get(BASE, params={"limit": limit}, headers=me.headers)
    assert response.status_code == 422


async def test_the_summary_counts_the_queue_and_the_reviews(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    first, second = await _ids(kb_factory, prepared, 1, 2)
    summary = (await client.get(f"{BASE}/summary", headers=me.headers)).json()
    assert summary == {
        "by_band": {"high": 2, "medium": 2, "low": 1},
        "by_court": {"yargitay": 4, "aym": 1},
        "top_reasons": [
            {"reason": "date_from_closing", "count": 2},
            {"reason": "body_start_approximate", "count": 1},
            {"reason": "missing_esas_no", "count": 1},
        ],
        "approved": 0,
        "rejected": 0,
    }
    await client.post(f"{BASE}/{first}", json={"action": "approve"}, headers=me.headers)
    await client.post(
        f"{BASE}/{second}", json={"action": "reject", "note": "yanlış"}, headers=me.headers
    )
    summary = (await client.get(f"{BASE}/summary", headers=me.headers)).json()
    assert summary["by_band"] == {"high": 1, "medium": 1, "low": 1}
    assert (summary["approved"], summary["rejected"]) == (1, 1)


async def _review_all(client: httpx.AsyncClient, me: Login, ids: dict[int, uuid.UUID]) -> None:
    """1 approved, 2 edited (approved), 3 rejected with a note, 4 and 5 left pending; the
    reviews follow in the order of the keys."""
    url = {n: f"{BASE}/{i}" for n, i in ids.items()}
    for n, body in {
        1: {"action": "approve"},
        2: {"action": "edit", "edits": {"chamber": "22. HD"}},
        3: {"action": "reject", "note": "kopya dosya"},
    }.items():
        assert (await client.post(url[n], json=body, headers=me.headers)).status_code == 200


async def test_the_list_by_status_shows_each_tab_with_its_review(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    ids = dict(zip(range(1, 6), await _ids(kb_factory, prepared, 1, 2, 3, 4, 5), strict=True))
    await _review_all(client, me, ids)

    async def listed(**params: Any) -> dict[str, Any]:
        response = await client.get(BASE, params=params, headers=me.headers)
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        return body

    def order(body: dict[str, Any]) -> list[uuid.UUID]:
        return [uuid.UUID(i["extraction_id"]) for i in body["items"]]

    pending = await listed()
    assert order(pending) == [ids[4], ids[5]]
    assert order(await listed(status="pending")) == order(pending)
    assert {i["source_status"] for i in pending["items"]} == {"analyzed"}
    assert all(i["reviewed_at"] is None and i["note"] is None for i in pending["items"])

    approved = await listed(status="approved")
    assert approved["total"] == 2
    assert order(approved) == [ids[2], ids[1]]  # the newest review first
    first, second = approved["items"]
    assert (first["review_decision"], second["review_decision"]) == ("edit", "approve")
    assert {i["source_status"] for i in approved["items"]} == {"approved"}
    assert {i["reviewer_name"] for i in approved["items"]} == {"baran@x.test"}
    assert first["reviewed_at"] >= second["reviewed_at"]
    assert first["note"] is None

    (rejected,) = (await listed(status="rejected"))["items"]
    assert rejected["extraction_id"] == str(ids[3])
    assert (rejected["source_status"], rejected["review_decision"]) == ("rejected", "reject")
    assert (rejected["note"], rejected["reviewer_name"]) == ("kopya dosya", "baran@x.test")

    everything = await listed(status="all")
    assert everything["total"] == 5
    assert order(everything) == [ids[3], ids[4], ids[2], ids[1], ids[5]]  # score_asc
    assert order(await listed(status="all", sort="score_desc")) == [
        ids[1], ids[5], ids[2], ids[4], ids[3]
    ]  # fmt: skip
    # reviewed first (newest first); the pending ones, never reviewed, come last
    assert order(await listed(status="all", sort="reviewed_desc")) == [
        ids[3], ids[2], ids[1], ids[4], ids[5]
    ]  # fmt: skip
    statuses = {i["extraction_id"]: i["source_status"] for i in everything["items"]}
    assert sorted(statuses.values()) == ["analyzed", "analyzed", "approved", "approved", "rejected"]


async def test_the_list_by_status_combines_with_the_filters_and_pages(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    ids = dict(zip(range(1, 6), await _ids(kb_factory, prepared, 1, 2, 3, 4, 5), strict=True))
    await _review_all(client, me, ids)

    async def listed(**params: Any) -> list[uuid.UUID]:
        response = await client.get(BASE, params=params, headers=me.headers)
        assert response.status_code == 200
        return [uuid.UUID(i["extraction_id"]) for i in response.json()["items"]]

    assert await listed(status="approved", band="medium") == [ids[2]]
    assert await listed(status="approved", band="low") == []
    assert await listed(status="rejected", court="aym") == [ids[3]]
    assert await listed(status="rejected", court="yargitay") == []
    assert await listed(status="all", reason="date_from_closing") == [ids[4], ids[2]]
    assert await listed(status="all", journal_issue=5) == [ids[2]]
    assert await listed(status="approved", q="2019/1") == [ids[1]]
    assert await listed(status="all", q="2019/3") == [ids[3]]

    page = (
        await client.get(
            BASE, params={"status": "all", "limit": 2, "offset": 4}, headers=me.headers
        )
    ).json()
    assert (page["total"], len(page["items"])) == (5, 1)
    past = (
        await client.get(
            BASE, params={"status": "all", "limit": 2, "offset": 10}, headers=me.headers
        )
    ).json()
    assert (past["total"], past["items"]) == (5, [])


async def test_the_list_shows_the_last_review_of_a_source_with_several(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    other = await _login_as(client, kb_factory, "ibrahim@x.test", UserRole.reviewer)
    (await client.post(f"{BASE}/{extraction_id}", json={"action": "approve"}, headers=me.headers))
    async with kb_factory() as session:  # an older and a newer review, by a second reviewer
        session.add_all(
            Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer,
                decision=ReviewDecision.reject,
                note=note,
                reviewed_at=when,
            )
            for reviewer, note, when in [
                (me.id, "eski", datetime(2000, 1, 1, tzinfo=UTC)),
                (other.id, "yeni", datetime(2100, 1, 1, tzinfo=UTC)),
            ]
        )
        await session.commit()

    body = (await client.get(BASE, params={"status": "approved"}, headers=me.headers)).json()
    (item,) = body["items"]  # one row per source, not per review
    assert body["total"] == 1
    assert (item["reviewer_name"], item["review_decision"], item["note"]) == (
        "ibrahim@x.test",
        "reject",
        "yeni",
    )
    assert item["reviewed_at"].startswith("2100-01-01")


async def test_a_note_is_shown_only_for_a_rejection(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, {}, {})
    first, second = await _ids(kb_factory, prepared, 1, 2)
    await client.post(
        f"{BASE}/{first}", json={"action": "approve", "note": "iyi"}, headers=me.headers
    )
    await client.post(
        f"{BASE}/{second}", json={"action": "reject", "note": "kötü"}, headers=me.headers
    )
    items = (await client.get(BASE, params={"status": "all"}, headers=me.headers)).json()["items"]
    assert {i["review_decision"]: i["note"] for i in items} == {"approve": None, "reject": "kötü"}


async def test_the_summary_counts_match_the_list_totals(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, *SPREAD)
    ids = dict(zip(range(1, 6), await _ids(kb_factory, prepared, 1, 2, 3, 4, 5), strict=True))
    await _review_all(client, me, ids)
    summary = (await client.get(f"{BASE}/summary", headers=me.headers)).json()
    totals = {
        status: (await client.get(BASE, params={"status": status}, headers=me.headers)).json()[
            "total"
        ]
        for status in ("pending", "approved", "rejected", "all")
    }
    assert (summary["approved"], summary["rejected"]) == (totals["approved"], totals["rejected"])
    assert sum(summary["by_band"].values()) == totals["pending"]
    assert totals == {"pending": 2, "approved": 2, "rejected": 1, "all": 5}


async def test_sorting_by_review_needs_a_reviewed_status(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    await _seed(kb_factory, {})
    for params in ({"sort": "reviewed_desc"}, {"status": "pending", "sort": "reviewed_desc"}):
        response = await client.get(BASE, params=params, headers=me.headers)
        assert response.status_code == 422
        assert response.json()["error"] == {
            "code": "validation_error",
            "params": {"fields": ["sort"]},
        }
    assert (
        await client.get(BASE, params={"status": "bogus"}, headers=me.headers)
    ).status_code == 422


async def test_the_status_tabs_need_a_login(client: httpx.AsyncClient, kb_factory: Factory) -> None:
    responses = await asyncio.gather(
        *(client.get(BASE, params={"status": s}) for s in ("approved", "rejected", "all"))
    )
    assert [r.status_code for r in responses] == [401] * 3


# --- detail -----------------------------------------------------------------------------------


async def test_the_detail_shows_fields_duplicates_and_reviews(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    # 1 and 2 share a key and differ in date: one duplicate group, both low
    prepared = await _seed(
        kb_factory,
        {"decision_date": "2019-03-12"},
        {"decision_date": "2019-03-13", "esas_no": "2017/1", "karar_no": "2019/1"},
        {},
    )
    first, second, third = await _ids(kb_factory, prepared, 1, 2, 3)
    response = await client.get(f"{BASE}/{first}", headers=me.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["extraction_id"] == str(first)
    assert body["source_status"] == "analyzed"
    assert body["fields"]["full_text"] == RECORD["full_text"]
    assert body["fields"]["editorial_summary"] == "Özet"
    assert body["confidence"]["band"] == "low"
    assert body["raw_text_ref"] == prepared[0].raw_text_ref
    assert body["reviews"] == []
    (other,) = body["duplicates"]
    assert other == {
        "extraction_id": str(second),
        "band": "low",
        "score": body["confidence"]["score"],
        "text_length": len(RECORD["full_text"]),
    }
    assert (await client.get(f"{BASE}/{third}", headers=me.headers)).json()["duplicates"] == []

    # a newer extraction of source 2 that left the group: it is no longer a duplicate of 1
    left = {k: v for k, v in prepared[1].fields.items() if k != "duplicate_group"}
    await load(
        kb_factory,
        [dataclasses.replace(prepared[1], parser_version="6", fields=left)],
        LoadCounts(),
    )
    assert (await client.get(f"{BASE}/{first}", headers=me.headers)).json()["duplicates"] == []

    await client.post(
        f"{BASE}/{third}", json={"action": "reject", "note": "kopya"}, headers=me.headers
    )
    body = (await client.get(f"{BASE}/{third}", headers=me.headers)).json()  # no longer queued
    assert body["source_status"] == "rejected"
    (review,) = body["reviews"]
    assert (review["decision"], review["note"], review["reviewer_id"]) == (
        "reject",
        "kopya",
        str(me.id),
    )
    assert review["reviewer_name"] == "baran@x.test"


async def test_an_unknown_extraction_is_404(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    url = f"{BASE}/{uuid.uuid4()}"
    got = await client.get(url, headers=me.headers)
    assert (got.status_code, got.json()["error"]["code"]) == (404, "extraction_not_found")
    response = await client.post(url, json={"action": "approve"}, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "extraction_not_found")


# --- approve, edit, reject --------------------------------------------------------------------


async def test_approve_publishes_the_decision_under_the_logged_in_user(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    response = await client.post(
        f"{BASE}/{extraction_id}", json={"action": "approve", "note": "ok"}, headers=me.headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_status"] == "approved"
    async with kb_factory() as session:
        review = (await session.execute(select(Review))).scalar_one()
        decision = (await session.execute(select(Decision))).scalar_one()
    assert str(review.id) == body["review_id"]
    assert (review.reviewer_id, review.decision, review.note) == (
        me.id,
        ReviewDecision.approve,
        "ok",
    )
    assert str(decision.id) == body["decision_id"]
    assert (decision.review_id, decision.extraction_id) == (review.id, extraction_id)
    assert decision.verification.value == "unverified"
    assert await _status(kb_factory, extraction_id) is RecordStatus.approved


async def test_edit_publishes_the_edited_fields(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {"outcome": ""})
    extraction_id = await _eid(kb_factory, record)
    edits = {
        "chamber": "10. HD",
        "outcome": "onama",
        "decision_date": "2019-04-01",
        "keywords": ["kıdem"],
        "text_completeness": "excerpt",
        "related_articles": [
            {"statute": 4857, "label": "İşK", "articles": ["17", "18"], "raw": ""}
        ],
    }
    response = await client.post(
        f"{BASE}/{extraction_id}", json={"action": "edit", "edits": edits}, headers=me.headers
    )
    assert response.status_code == 200
    async with kb_factory() as session:
        review = (await session.execute(select(Review))).scalar_one()
        decision = (await session.execute(select(Decision))).scalar_one()
    assert (review.decision, review.edits) == (ReviewDecision.edit, edits)
    assert (decision.chamber, decision.outcome, decision.keywords) == ("10. HD", "onama", ["kıdem"])
    assert (decision.decision_date.isoformat(), decision.text_completeness.value) == (  # type: ignore[union-attr]
        "2019-04-01",
        "excerpt",
    )
    assert decision.related_articles == edits["related_articles"]
    assert decision.esas_no == record.fields["esas_no"]  # untouched fields come from the extraction


@pytest.mark.parametrize(
    "body",
    [
        {"action": "edit", "edits": {"court": "mars"}},
        {"action": "edit", "edits": {"outcome": "bozulsun"}},
        {"action": "edit", "edits": {"decision_date": "12.03.2019"}},
        {"action": "edit", "edits": {"chamber": "10. HD", "unknown_key": 1}},
        {"action": "edit", "edits": {"full_text": "başka"}},
        {"action": "edit", "edits": {"editorial_summary": "başka"}},
        {"action": "edit", "edits": {"chamber": None}},
        {"action": "edit", "edits": {"esas_no": ""}},
        {"action": "edit", "edits": {"karar_no": ""}},
        {"action": "edit", "edits": {"decision_date": "2019-3-12"}},
        {"action": "edit", "edits": {"decision_date": "20190312"}},
        {"action": "edit", "edits": {"decision_date": "2019-03-12T10:00:00"}},
        {"action": "edit", "edits": {"decision_date": "2019-02-30"}},
        {"action": "edit", "edits": {"related_articles": [{"statute": "4857"}]}},
        {"action": "edit", "edits": {"related_articles": [{"kanun": 4857, "maddeler": [18]}]}},
        {"action": "edit", "edits": {"related_articles": [[4857, 18]]}},
        {"action": "approve", "edits": {"chamber": "10. HD"}},
        {"action": "approve", "edits": {}},
        {"action": "reject", "note": "n", "edits": {"chamber": "10. HD"}},
        {"action": "edit", "edits": {}},
        {"action": "edit"},
        {"action": "merge"},
    ],
)
async def test_invalid_edits_are_422_and_write_nothing(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, body: dict[str, Any]
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    response = await client.post(f"{BASE}/{extraction_id}", json=body, headers=me.headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (await _count(kb_factory, Review), await _count(kb_factory, Decision)) == (0, 0)
    assert await _status(kb_factory, extraction_id) is RecordStatus.analyzed


async def test_an_edit_that_cannot_be_published_is_422_and_writes_nothing(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {"court": "foreign", "court_level": ""})
    extraction_id = await _eid(kb_factory, record)  # no court_level: not publishable as it is
    response = await client.post(
        f"{BASE}/{extraction_id}", json={"action": "approve"}, headers=me.headers
    )
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "params": {"fields": []}}}
    assert (await _count(kb_factory, Review), await _count(kb_factory, Decision)) == (0, 0)
    response = await client.post(
        f"{BASE}/{extraction_id}",
        json={"action": "edit", "edits": {"court_level": "international"}},
        headers=me.headers,
    )
    assert response.status_code == 200


@pytest.mark.parametrize("note", [None, "", "   "])
async def test_reject_needs_a_note(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, note: str | None
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    response = await client.post(
        f"{BASE}/{extraction_id}", json={"action": "reject", "note": note}, headers=me.headers
    )
    assert response.status_code == 422
    assert response.json() == {"error": {"code": "validation_error", "params": {"fields": []}}}
    assert await _count(kb_factory, Review) == 0
    assert await _status(kb_factory, extraction_id) is RecordStatus.analyzed


async def test_reject_with_a_note_rejects_the_source_and_publishes_nothing(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    response = await client.post(
        f"{BASE}/{extraction_id}",
        json={"action": "reject", "note": "kopya dosya"},
        headers=me.headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["decision_id"], body["source_status"]) == (None, "rejected")
    async with kb_factory() as session:
        review = (await session.execute(select(Review))).scalar_one()
    assert str(review.id) == body["review_id"]
    assert (review.reviewer_id, review.decision, review.note) == (
        me.id,
        ReviewDecision.reject,
        "kopya dosya",
    )
    assert await _count(kb_factory, Decision) == 0
    assert await _status(kb_factory, extraction_id) is RecordStatus.rejected


# --- conflicts --------------------------------------------------------------------------------


@pytest.mark.parametrize("first", [{"action": "approve"}, {"action": "reject", "note": "n"}])
async def test_a_second_action_on_the_same_record_is_409(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, first: dict[str, Any]
) -> None:
    (record,) = await _seed(kb_factory, {})
    url = f"{BASE}/{await _eid(kb_factory, record)}"
    assert (await client.post(url, json=first, headers=me.headers)).status_code == 200
    for again in ({"action": "approve"}, {"action": "reject", "note": "n"}):
        response = await client.post(url, json=again, headers=me.headers)
        assert (response.status_code, response.json()["error"]["code"]) == (409, "review_conflict")
    assert await _count(kb_factory, Review) == 1


async def test_an_action_on_an_older_extraction_is_409(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    await load(kb_factory, [dataclasses.replace(record, parser_version="6")], LoadCounts())
    old, new = await _eid(kb_factory, record), await _eid(kb_factory, record, "6")
    response = await client.post(f"{BASE}/{old}", json={"action": "approve"}, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "review_conflict")
    assert await _count(kb_factory, Review) == 0
    assert await _status(kb_factory, old) is RecordStatus.analyzed
    response = await client.post(f"{BASE}/{new}", json={"action": "approve"}, headers=me.headers)
    assert response.status_code == 200


async def test_a_live_key_collision_is_409_with_the_conflicting_decision(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    # the same key with two dates: both low, both analyzed
    prepared = await _seed(
        kb_factory,
        {"decision_date": "2019-03-12", "esas_no": "2017/1", "karar_no": "2019/1"},
        {"decision_date": "2019-03-13", "esas_no": "2017/1", "karar_no": "2019/1"},
    )
    first, second = await _ids(kb_factory, prepared, 1, 2)
    won = await client.post(f"{BASE}/{first}", json={"action": "approve"}, headers=me.headers)
    assert won.status_code == 200
    lost = await client.post(f"{BASE}/{second}", json={"action": "approve"}, headers=me.headers)
    assert lost.status_code == 409
    assert lost.json() == {
        "error": {"code": "decision_conflict", "params": {"decision_id": won.json()["decision_id"]}}
    }
    assert (await _count(kb_factory, Review), await _count(kb_factory, Decision)) == (1, 1)
    assert await _status(kb_factory, second) is RecordStatus.analyzed


# --- bulk approval ----------------------------------------------------------------------------


def _bulk(count: int, **body: Any) -> dict[str, Any]:
    return {"band": "high", "expected_count": count, **body}


async def test_bulk_approval_takes_the_high_band_only(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    await _seed(kb_factory, *SPREAD)
    for band in ("medium", "low"):
        response = await client.post(
            f"{BASE}/bulk-approve", json={**_bulk(2), "band": band}, headers=me.headers
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "bulk_band_not_allowed"
    assert await _count(kb_factory, Decision) == 0


async def test_bulk_approval_refuses_a_count_that_is_not_the_one_on_screen(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    await _seed(kb_factory, *SPREAD)  # two highs
    for count in (1, 3):
        response = await client.post(f"{BASE}/bulk-approve", json=_bulk(count), headers=me.headers)
        assert response.status_code == 409
        assert response.json() == {
            "error": {"code": "bulk_count_changed", "params": {"total": 2, "expected": count}}
        }
    assert (await _count(kb_factory, Review), await _count(kb_factory, Decision)) == (0, 0)


async def test_bulk_approval_stops_at_the_limit_and_reports_what_remains(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, {}, {}, {}, {}, {}, MEDIUM, {"journal_issue": 4})
    # the filter leaves out record 7; the medium record 6 is not in the band
    filters = {"journal_issue": 3}
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(5, filters=filters, limit=2), headers=me.headers
    )
    assert response.status_code == 200
    assert response.json() == {
        "published": 2,
        "conflicts": [],
        "failed": [],
        "remaining": 3,
        "next_cursor": prepared[1].sha256,
    }
    assert await _count(kb_factory, Decision) == 2

    response = await client.post(
        f"{BASE}/bulk-approve",
        json=_bulk(3, filters=filters, cursor=prepared[1].sha256),
        headers=me.headers,
    )
    assert response.json() == {
        "published": 3,
        "conflicts": [],
        "failed": [],
        "remaining": 0,
        "next_cursor": None,
    }
    async with kb_factory() as session:
        reviewers = set((await session.execute(select(Review.reviewer_id))).scalars())
        approved = (
            await session.execute(
                select(func.count())
                .select_from(Source)
                .where(Source.status == RecordStatus.approved)
            )
        ).scalar_one()
    assert (reviewers, approved) == ({me.id}, 5)
    assert await _status(kb_factory, await _eid(kb_factory, prepared[5])) is RecordStatus.analyzed
    assert await _status(kb_factory, await _eid(kb_factory, prepared[6])) is RecordStatus.analyzed


async def test_bulk_limit_is_capped_at_100(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(0, limit=101), headers=me.headers
    )
    assert response.status_code == 422


async def test_a_conflict_in_bulk_approval_does_not_stop_the_others(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    new_decision: NewDecision,
) -> None:
    prepared = await _seed(kb_factory, {}, {}, {})
    async with kb_factory() as session:  # a live decision with the key of record 2
        await new_decision(session, esas_no="2017/2", karar_no="2019/2", chamber="9. HD")
        await session.commit()
    conflicting = await _eid(kb_factory, prepared[1])
    response = await client.post(f"{BASE}/bulk-approve", json=_bulk(3), headers=me.headers)
    assert response.status_code == 200
    assert response.json() == {
        "published": 2,
        "conflicts": [str(conflicting)],
        "failed": [],
        "remaining": 0,
        "next_cursor": None,
    }
    assert await _status(kb_factory, conflicting) is RecordStatus.analyzed
    assert await _count(kb_factory, Review) == 2
    assert await _count(kb_factory, Decision) == 3


async def test_repeated_bulk_calls_pass_a_standing_conflict_and_finish(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, new_decision: NewDecision
) -> None:
    prepared = await _seed(kb_factory, *[{}] * 6)
    async with kb_factory() as session:  # a live decision with the key of record 2
        await new_decision(session, esas_no="2017/2", karar_no="2019/2", chamber="9. HD")
        await session.commit()
    conflicting = str(await _eid(kb_factory, prepared[1]))

    published, conflicts, calls = 0, [], 0
    body = _bulk(6, limit=2)
    while True:
        calls += 1
        assert calls <= 3, "the loop does not make progress"
        response = await client.post(f"{BASE}/bulk-approve", json=body, headers=me.headers)
        assert response.status_code == 200
        result = response.json()
        published += result["published"]
        conflicts += result["conflicts"]
        if result["next_cursor"] is None:
            break
        body = _bulk(result["remaining"], limit=2, cursor=result["next_cursor"])
    assert (published, conflicts, calls) == (5, [conflicting], 3)
    assert result["remaining"] == 0
    assert await _status(kb_factory, uuid.UUID(conflicting)) is RecordStatus.analyzed


async def test_bulk_expected_count_counts_the_records_after_the_cursor(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    prepared = await _seed(kb_factory, {}, {}, {})
    cursor = prepared[0].sha256
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(3, cursor=cursor), headers=me.headers
    )
    assert response.status_code == 409  # 2 match after the cursor
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(2, cursor=cursor), headers=me.headers
    )
    assert response.json()["published"] == 2
    assert await _status(kb_factory, await _eid(kb_factory, prepared[0])) is RecordStatus.analyzed


async def test_a_bulk_cursor_is_a_sha256(client: httpx.AsyncClient, me: Login) -> None:
    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(0, cursor="abc"), headers=me.headers
    )
    assert response.status_code == 422


async def test_two_concurrent_actions_on_the_same_record_give_one_success_and_one_409(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    url = f"{BASE}/{await _eid(kb_factory, record)}"
    responses = await asyncio.gather(
        *[client.post(url, json={"action": "approve"}, headers=me.headers) for _ in range(2)]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (await _count(kb_factory, Review), await _count(kb_factory, Decision)) == (1, 1)


# --- access -----------------------------------------------------------------------------------


async def test_every_endpoint_needs_a_login(client: httpx.AsyncClient, kb_factory: Factory) -> None:
    some = uuid.uuid4()
    calls = [
        client.get(BASE),
        client.get(f"{BASE}/summary"),
        client.get(f"{BASE}/{some}"),
        client.post(f"{BASE}/{some}", json={"action": "approve"}),
        client.post(f"{BASE}/bulk-approve", json=_bulk(0)),
    ]
    responses = await asyncio.gather(*calls)
    assert [r.status_code for r in responses] == [401] * 5
    assert {r.json()["error"]["code"] for r in responses} == {"unauthorized"}


async def test_an_admin_passes_the_reviewer_check(
    client: httpx.AsyncClient, kb_factory: Factory
) -> None:
    admin = await _login_as(client, kb_factory, "orhan@x.test", UserRole.admin)
    assert (await client.get(BASE, headers=admin.headers)).status_code == 200


# --- original PDF -----------------------------------------------------------------------------

PDF_BYTES = b"%PDF-1.4 fixture"


@dataclass
class Archive:
    root: Path
    extraction_id: uuid.UUID
    url: str


@pytest.fixture
async def archive(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Archive:
    """One decision whose `ingest_file` points at a real PDF under a temporary archive root."""
    root = tmp_path / "drive"
    (root / "Yargi").mkdir(parents=True)
    (root / "Yargi" / "Kisi Adi.pdf").write_bytes(PDF_BYTES)
    monkeypatch.setattr(
        "app.review.get_settings", lambda: Settings(database_url="unused", archive_root=root)
    )
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    await _point_file(
        kb_factory, extraction_id, "Yargi/Kisi Adi.pdf", hashlib.sha256(PDF_BYTES).hexdigest()
    )
    return Archive(root, extraction_id, f"{BASE}/{extraction_id}/file")


async def _point_file(
    factory: Factory, extraction_id: uuid.UUID, path: str, sha256: str, detected_type: str = "pdf"
) -> None:
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE ingest_file SET path = :path, sha256 = :sha, detected_type = :type "
                "WHERE id = (SELECT file_id FROM extraction WHERE id = :id)"
            ),
            {"path": path, "sha": sha256, "type": detected_type, "id": extraction_id},
        )
        await session.commit()


async def test_the_original_pdf_is_served_inline_with_safe_headers(
    client: httpx.AsyncClient, me: Login, archive: Archive
) -> None:
    response = await client.get(archive.url, headers=me.headers)
    assert response.status_code == 200
    assert response.content == PDF_BYTES
    sha = hashlib.sha256(PDF_BYTES).hexdigest()
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == f'inline; filename="{sha}.pdf"'
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_the_detail_says_whether_the_pdf_can_be_shown(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, archive: Archive
) -> None:
    async def pdf() -> str:
        response = await client.get(f"{BASE}/{archive.extraction_id}", headers=me.headers)
        return str(response.json()["pdf"])

    assert await pdf() == "available"
    await _point_file(kb_factory, archive.extraction_id, "Yargi/missing.pdf", "0" * 64)
    assert await pdf() == "missing"
    await _point_file(kb_factory, archive.extraction_id, "../outside.pdf", "0" * 64)
    assert await pdf() == "missing"
    await _point_file(kb_factory, archive.extraction_id, "Yargi/Kisi Adi.pdf", "0" * 64, "docx")
    assert await pdf() == "not_previewable"


async def test_the_detail_pdf_is_missing_without_an_archive_root(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    archive: Archive,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.review.get_settings", lambda: Settings(database_url="unused"))
    response = await client.get(f"{BASE}/{archive.extraction_id}", headers=me.headers)
    assert response.json()["pdf"] == "missing"


async def test_the_pdf_of_an_unknown_extraction_is_404(
    client: httpx.AsyncClient, me: Login, archive: Archive
) -> None:
    response = await client.get(f"{BASE}/{uuid.uuid4()}/file", headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "extraction_not_found")


async def test_a_path_that_leaves_the_archive_root_is_404(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, archive: Archive
) -> None:
    outside = archive.root.parent / "outside.pdf"
    outside.write_bytes(PDF_BYTES)
    sha = hashlib.sha256(PDF_BYTES).hexdigest()
    (archive.root / "link.pdf").symlink_to(outside)
    for path in ("../outside.pdf", str(outside), "link.pdf", "Yargi/missing.pdf", "Yargi"):
        await _point_file(kb_factory, archive.extraction_id, path, sha)
        response = await client.get(archive.url, headers=me.headers)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "file_not_found")


async def test_a_file_that_does_not_match_its_sha256_is_not_served(
    client: httpx.AsyncClient,
    kb_factory: Factory,
    me: Login,
    archive: Archive,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _point_file(kb_factory, archive.extraction_id, "Yargi/Kisi Adi.pdf", "0" * 64)
    with caplog.at_level("WARNING", logger="app"):
        response = await client.get(archive.url, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "file_not_found")
    assert "sha256" in caplog.text


async def test_only_pdfs_are_previewable(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login, archive: Archive
) -> None:
    for detected_type in ("doc", "html"):
        await _point_file(
            kb_factory, archive.extraction_id, "Yargi/Kisi Adi.pdf", "0" * 64, detected_type
        )
        response = await client.get(archive.url, headers=me.headers)
        assert (response.status_code, response.json()["error"]["code"]) == (
            415,
            "file_not_previewable",
        )


async def test_without_an_archive_root_the_pdf_is_404(
    client: httpx.AsyncClient, me: Login, archive: Archive, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.review.get_settings", lambda: Settings(database_url="unused"))
    response = await client.get(archive.url, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "file_not_found")


async def test_the_pdf_needs_a_login(client: httpx.AsyncClient, archive: Archive) -> None:
    response = await client.get(archive.url)
    assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthorized")


# --- review.reviewer_id -> app_user.id --------------------------------------------------------


async def test_a_review_needs_an_existing_reviewer(kb_factory: Factory, reviewer: AppUser) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    async with kb_factory() as session:
        session.add(
            Review(
                extraction_id=extraction_id,
                reviewer_id=uuid.uuid4(),
                decision=ReviewDecision.reject,
            )
        )
        with pytest.raises(IntegrityError, match="fk_review_reviewer_id_app_user"):
            await session.commit()
    async with kb_factory() as session:
        session.add(
            Review(
                extraction_id=extraction_id, reviewer_id=reviewer.id, decision=ReviewDecision.reject
            )
        )
        await session.commit()


async def test_a_review_of_a_reviewer_without_a_user_row_still_shows_in_the_detail(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    # Reviews of the task-05 CLI may name a reviewer with no app_user row. The FK is NOT VALID
    # but still checks new rows, so the insert skips FK triggers (session_replication_role
    # needs the superuser of the test database).
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    ghost = uuid.uuid4()
    async with kb_factory() as session, session.begin():
        await session.execute(text("SET LOCAL session_replication_role = replica"))
        session.add(
            Review(extraction_id=extraction_id, reviewer_id=ghost, decision=ReviewDecision.reject)
        )
    body = (await client.get(f"{BASE}/{extraction_id}", headers=me.headers)).json()
    (review,) = body["reviews"]
    assert (review["reviewer_id"], review["reviewer_name"]) == (str(ghost), None)


# --- schemas ----------------------------------------------------------------------------------


def test_openapi_has_every_endpoint_with_a_typed_response() -> None:
    paths = app.openapi()["paths"]
    expected = {
        ("get", BASE),
        ("get", f"{BASE}/summary"),
        ("post", f"{BASE}/bulk-approve"),
        ("get", f"{BASE}/{{extraction_id}}"),
        ("post", f"{BASE}/{{extraction_id}}"),
    }
    for method, path in expected:
        schema = paths[path][method]["responses"]["200"]["content"]["application/json"]["schema"]
        assert "$ref" in schema, (method, path)


def _literal(model_field: str) -> set[Any]:
    annotation = DecisionEdits.model_fields[model_field].annotation
    (literal,) = [a for a in get_args(annotation) if get_origin(a) is Literal]
    return set(get_args(literal))


def test_the_edit_schema_mirrors_the_app_enums() -> None:
    assert set(DecisionEdits.model_fields) == {
        "court",
        "court_level",
        "chamber",
        "source_chamber",
        "bam_region",
        "decision_kind",
        "esas_no",
        "karar_no",
        "decision_date",
        "jurisdiction",
        "related_articles",
        "keywords",
        "outcome",
        "text_completeness",
    }
    assert _literal("court") == {c.value for c in Court}
    assert _literal("court_level") == {c.value for c in CourtLevel}
    assert _literal("jurisdiction") == {c.value for c in Jurisdiction}
    assert _literal("text_completeness") == {c.value for c in TextCompleteness}
    assert _literal("outcome") == OUTCOMES
    assert set(get_args(SourceStatus)) == {s.value for s in RecordStatus}


async def test_an_empty_archive_root_variable_starts_the_app_and_the_pdf_is_404(
    client: httpx.AsyncClient,
    me: Login,
    archive: Archive,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "unused")
    monkeypatch.setenv("ARCHIVE_ROOT", "")
    monkeypatch.setattr("app.review.get_settings", Settings)
    response = await client.get(archive.url, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "file_not_found")


async def test_a_file_over_the_size_cap_is_404_and_logged(
    client: httpx.AsyncClient,
    me: Login,
    archive: Archive,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    capped = Settings(
        database_url="unused", archive_root=archive.root, archive_max_file_bytes=len(PDF_BYTES) - 1
    )
    monkeypatch.setattr("app.review.get_settings", lambda: capped)
    with caplog.at_level("WARNING", logger="app"):
        response = await client.get(archive.url, headers=me.headers)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "file_not_found")
    assert "size cap" in caplog.text
