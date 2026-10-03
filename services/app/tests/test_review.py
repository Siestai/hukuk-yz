"""Review API (task 09). The database tests are skipped when DATABASE_URL is unset; CI sets it."""

import asyncio
import dataclasses
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args, get_origin

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
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


async def test_an_unknown_extraction_is_404(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    url = f"{BASE}/{uuid.uuid4()}"
    assert (await client.get(url, headers=me.headers)).status_code == 404
    response = await client.post(url, json={"action": "approve"}, headers=me.headers)
    assert response.status_code == 404


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
        assert (await client.post(url, json=again, headers=me.headers)).status_code == 409
    assert await _count(kb_factory, Review) == 1


async def test_an_action_on_an_older_extraction_is_409(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    (record,) = await _seed(kb_factory, {})
    await load(kb_factory, [dataclasses.replace(record, parser_version="6")], LoadCounts())
    old, new = await _eid(kb_factory, record), await _eid(kb_factory, record, "6")
    response = await client.post(f"{BASE}/{old}", json={"action": "approve"}, headers=me.headers)
    assert response.status_code == 409
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
    assert lost.json()["detail"]["decision_id"] == won.json()["decision_id"]
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
    assert await _count(kb_factory, Decision) == 0


async def test_bulk_approval_refuses_a_count_that_is_not_the_one_on_screen(
    client: httpx.AsyncClient, kb_factory: Factory, me: Login
) -> None:
    await _seed(kb_factory, *SPREAD)  # two highs
    for count in (1, 3):
        response = await client.post(f"{BASE}/bulk-approve", json=_bulk(count), headers=me.headers)
        assert response.status_code == 409
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
    assert response.json() == {"published": 2, "conflicts": [], "failed": [], "remaining": 3}
    assert await _count(kb_factory, Decision) == 2

    response = await client.post(
        f"{BASE}/bulk-approve", json=_bulk(3, filters=filters), headers=me.headers
    )
    assert response.json() == {"published": 3, "conflicts": [], "failed": [], "remaining": 0}
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
        "remaining": 1,
    }
    assert await _status(kb_factory, conflicting) is RecordStatus.analyzed
    assert await _count(kb_factory, Review) == 2
    assert await _count(kb_factory, Decision) == 3


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
    assert [r.status_code for r in await asyncio.gather(*calls)] == [401] * 5


async def test_an_admin_passes_the_reviewer_check(
    client: httpx.AsyncClient, kb_factory: Factory
) -> None:
    admin = await _login_as(client, kb_factory, "orhan@x.test", UserRole.admin)
    assert (await client.get(BASE, headers=admin.headers)).status_code == 200


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


async def test_the_reviewer_fk_migration_runs_over_legacy_reviews(
    kb_factory: Factory, alembic_config: Config
) -> None:
    (record,) = await _seed(kb_factory, {})
    extraction_id = await _eid(kb_factory, record)
    await asyncio.to_thread(command.downgrade, alembic_config, "0005")
    try:
        async with (
            kb_factory() as session
        ):  # what the task 05 CLI wrote: a reviewer that is no user
            await session.execute(
                text(
                    "INSERT INTO review (extraction_id, reviewer_id, decision) "
                    "VALUES (:e, :r, 'approve')"
                ),
                {"e": extraction_id, "r": uuid.uuid4()},
            )
            await session.commit()
    finally:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
    assert await _count(kb_factory, Review) == 1
    async with kb_factory() as session:
        validated = (
            await session.execute(
                text(
                    "SELECT convalidated FROM pg_constraint "
                    "WHERE conname = 'fk_review_reviewer_id_app_user'"
                )
            )
        ).scalar_one()
    assert validated is False


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
