"""The journal scan API (task 20). The database tests are skipped when DATABASE_URL is unset; CI
sets it."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.db import make_engine
from app.main import app
from app.models.common import IngestJob, IngestKind, IngestStatus
from app.models.journal import JournalScan
from app.models.user import AppUser, UserRole

PASSWORD = "correct horse battery"
BASE = "/journal-scans"
Factory = async_sessionmaker[AsyncSession]
NOW = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)

REPORT: dict[str, Any] = {
    "issues": [
        {
            "issue_no": 91,
            "site_count": 70,
            "pdf_links": 70,
            "downloaded": 68,
            "duplicates": 1,
            "queued": 68,
            "duplicate_candidates": 2,
            "errors": [{"url": "https://yargi.calismatoplum.org/x/", "reason": "pdf_link_missing"}],
        }
    ],
    "failure": None,
    "archive_max": 90,
    "warnings": [],
}


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


async def login(client: httpx.AsyncClient, factory: Factory, role: UserRole) -> dict[str, str]:
    async with factory() as session:
        session.add(
            AppUser(
                email=f"{role.value}@x.test",
                display_name=role.value,
                role=role,
                password_hash=hash_password(PASSWORD),
            )
        )
        await session.commit()
    response = await client.post(
        "/auth/login", json={"email": f"{role.value}@x.test", "password": PASSWORD}
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
async def me(client: httpx.AsyncClient, kb_factory: Factory) -> dict[str, str]:
    return await login(client, kb_factory, UserRole.reviewer)


async def add_scan(factory: Factory, days_ago: int, **values: Any) -> uuid.UUID:
    started = NOW - timedelta(days=days_ago)
    async with factory() as session:
        job = IngestJob(kind=IngestKind.crawl, status=IngestStatus.completed)
        session.add(job)
        await session.flush()
        scan = JournalScan(
            **{
                "job_id": job.id,
                "trigger": "schedule",
                "started_at": started,
                "finished_at": started + timedelta(minutes=3),
                "status": "completed",
                **values,
            }
        )
        session.add(scan)
        await session.commit()
        return scan.id


async def test_the_list_is_paged_newest_first(
    client: httpx.AsyncClient, kb_factory: Factory, me: dict[str, str]
) -> None:
    ids = [await add_scan(kb_factory, days_ago=d, discovered=d) for d in (21, 7, 14)]
    body = (await client.get(BASE, params={"limit": 2}, headers=me)).json()
    assert body["total"] == 3
    assert [i["id"] for i in body["items"]] == [str(ids[1]), str(ids[2])]
    assert "report" not in body["items"][0]
    rest = (await client.get(BASE, params={"limit": 2, "offset": 2}, headers=me)).json()
    assert [i["id"] for i in rest["items"]] == [str(ids[0])]


async def test_the_detail_carries_the_report(
    client: httpx.AsyncClient, kb_factory: Factory, me: dict[str, str]
) -> None:
    scan_id = await add_scan(
        kb_factory,
        days_ago=0,
        status="completed_with_errors",
        new_issues=[91],
        discovered=70,
        downloaded=68,
        duplicates=1,
        queued=68,
        errors=1,
        report=REPORT,
    )
    body = (await client.get(f"{BASE}/{scan_id}", headers=me)).json()
    assert (body["status"], body["new_issues"], body["trigger"]) == (
        "completed_with_errors",
        [91],
        "schedule",
    )
    assert (body["discovered"], body["downloaded"], body["queued"], body["errors"]) == (
        70,
        68,
        68,
        1,
    )
    assert body["report"] == REPORT
    missing = await client.get(f"{BASE}/{uuid.uuid4()}", headers=me)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "not_found")


async def test_the_summary_is_numbers_of_the_latest_finished_scan(
    client: httpx.AsyncClient, kb_factory: Factory, me: dict[str, str]
) -> None:
    assert (await client.get(f"{BASE}/latest/summary", headers=me)).status_code == 404
    await add_scan(kb_factory, days_ago=7, new_issues=[90], queued=40, report=REPORT)
    await add_scan(
        kb_factory,
        days_ago=0,
        status="completed_with_errors",
        new_issues=[91],
        queued=68,
        duplicates=1,
        errors=1,
        report=REPORT,
    )
    await add_scan(kb_factory, days_ago=-1, status="running")  # not finished: not the latest
    body = (await client.get(f"{BASE}/latest/summary", headers=me)).json()
    assert body == {
        "status": "completed_with_errors",
        "finished_at": (NOW + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
        "issues": [91],
        "queued": 68,
        "duplicates": 1,
        "duplicate_candidates": 2,
        "errors": 1,
    }


async def test_only_reviewers_and_admins_read_the_scans(
    client: httpx.AsyncClient, kb_factory: Factory
) -> None:
    scan_id = await add_scan(kb_factory, days_ago=0)
    urls = [BASE, f"{BASE}/{scan_id}", f"{BASE}/latest/summary"]
    for url in urls:
        assert (await client.get(url)).status_code == 401
    plain = await login(client, kb_factory, UserRole.user)
    for url in urls:
        assert (await client.get(url, headers=plain)).status_code == 403
    admin = await login(client, kb_factory, UserRole.admin)
    for url in urls:
        assert (await client.get(url, headers=admin)).status_code == 200
