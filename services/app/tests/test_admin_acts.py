"""Genelge API (handoff 2026-11-22, A3). The database tests are skipped when DATABASE_URL is
unset; CI sets it.

The corpus test at the end also needs a real `admin-acts.jsonl` (`hukuk-ingest admin-acts ...`);
CI has none and skips it. Run it with

    DATABASE_URL=... HUKUK_ADMIN_ACTS_JSONL=/tmp/admin-acts/admin-acts.jsonl \\
        uv run pytest services/app/tests/test_admin_acts.py -k real
"""

import os
import tomllib
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin_acts import normalize_ref, normalize_section_no, unreviewed_bands
from app.db import make_engine
from app.loaders import admin_acts as loader
from app.main import app
from app.models.common import Extraction, Review, ReviewDecision
from app.models.user import AppUser
from app.settings import Settings, get_settings
from tests.test_loaders_admin_acts import LINE, TEXT, TEXT_WITHOUT_1_2, act_record, load_acts

Factory = async_sessionmaker[AsyncSession]
KEY = "test-kb-key-for-handoff-a3"
Allow = Callable[..., None]


@pytest.mark.parametrize(
    ("raw", "ref"),
    [
        ("2020-8", "2020/8"),
        ("2020-08", "2020/8"),
        ("2020_8", "2020/8"),
        ("2018-38", "2018/38"),
        (" 2020/8 ", "2020/8"),
        ("genelge", "genelge"),  # not a ref: left to the lookup, which will not find it
    ],
)
def test_the_url_form_of_a_ref_is_normalized(raw: str, ref: str) -> None:
    assert normalize_ref(raw) == ref


@pytest.mark.parametrize(
    ("raw", "section_no"),
    [
        ("2.6.2.5", "2.6.2.5"),
        ("2.6.2.5.", "2.6.2.5"),
        ("2.6.2.5-", "2.6.2.5"),
        ("m.2.6.2.5", "2.6.2.5"),
        ("K2-B3-2.1.1", "K2-B3-2.1.1"),
        ("k2-b3-2.1.1", "K2-B3-2.1.1"),
        ("k4-b1", "K4-B1"),
        ("k1-1.1.1", "K1-1.1.1"),
        ("giris", "Giriş"),
        ("Giriş", "Giriş"),
    ],
)
def test_section_number_aliases_are_normalized(raw: str, section_no: str) -> None:
    assert normalize_section_no(raw) == section_no


@pytest.fixture
async def client(database_url: str, kb_factory: Factory) -> AsyncIterator[httpx.AsyncClient]:
    """A client that reads with the KB service key, as the agent does."""
    app.state.engine = make_engine(database_url)
    app.dependency_overrides[get_settings] = lambda: Settings(kb_service_key=SecretStr(KEY))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://test",
            headers={"X-Service-Key": KEY},
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        await app.state.engine.dispose()


@pytest.fixture
def allow() -> Allow:
    """`allow("high", "medium")`: sets `KB_TEST_SOURCE_BANDS` (default: empty, nothing readable)."""

    def set_bands(*bands: str) -> None:
        app.dependency_overrides[get_settings] = lambda: Settings(
            kb_service_key=SecretStr(KEY), kb_test_source_bands=bands
        )

    return set_bands


async def _get(
    client: httpx.AsyncClient, section: str, as_of: str, ref: str = "2020-8"
) -> httpx.Response:
    return await client.get(f"/admin-acts/{ref}/sections/{section}", params={"as_of": as_of})


async def test_nothing_is_readable_while_the_setting_is_empty(
    client: httpx.AsyncClient, kb_factory: Factory
) -> None:
    await load_acts(kb_factory)

    for section in ("1", "1.2", "1.4"):
        response = await _get(client, section, "2024-01-01")
        assert response.status_code == 404, section
        assert response.json() == {"error": {"code": "not_found", "params": {"ref": "2020/8"}}}


async def test_found_returns_the_text_with_its_review_status_and_band(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")
    async with kb_factory() as session:
        extraction = (
            await session.execute(
                select(Extraction).where(Extraction.fields["section_no"].as_string() == "1")
            )
        ).scalar_one()

    response = await _get(client, "1", "2024-01-01")

    assert response.status_code == 200
    assert response.json() == {
        "status": "found",
        "ref": "2020/8",
        "section_no": "1",
        "citation": "2020/8 m.1",
        "title": "SGK Genelgesi 2020/8 · İdari Para Cezası Genelgesi",
        "version": {
            "text": f"1- GENEL AÇIKLAMALAR\nİdari para cezaları açıklanmıştır.\n{LINE}",
            "heading": "GENEL AÇIKLAMALAR",
            "valid_from": "2020-04-01",
            "valid_to": None,
            "change_kind": "original",
            "amendments": [],
        },
        "children": ["1.1", "1.2", "1.4"],
        "latest_snapshot_date": "2026-04-09",
        "stale": False,
        "review_status": "analyzed",
        "band": "high",
        "warnings": ["valid_from_assumed_issue_date"],
        "source_id": str(extraction.source_id),
        "extraction_id": str(extraction.id),
    }


async def test_an_amended_section_is_found_from_its_note_on_and_a_gap_before(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")

    found = (await _get(client, "1.2", "2021-09-17")).json()
    gap = (await _get(client, "1.2", "2021-09-16")).json()
    before = (await _get(client, "1.2", "2020-03-31")).json()

    assert (found["status"], found["band"], found["review_status"]) == (
        "found",
        "medium",
        "analyzed",
    )
    assert "on gün içinde verilir" in found["version"]["text"]
    assert found["version"]["amendments"] == [
        {"kind": "amended", "date": "2021-09-17", "ref": "2021/32"}
    ]
    assert found["warnings"] == ["amended_in_place"]
    assert gap["status"] == "gap"
    assert gap["gap"] == {"from": "2020-04-01", "to": "2021-09-17", "reason": "amended_in_place"}
    assert "version" not in gap  # a gap carries no text
    assert (gap["band"], gap["review_status"]) == ("medium", "analyzed")
    assert before["status"] == "not_in_force"
    assert "version" not in before and "gap" not in before


async def test_dates_before_the_genelge_and_after_the_file_are_marked(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high")

    before = (await _get(client, "1", "2020-03-31")).json()
    stale = (await _get(client, "1", "2026-04-10")).json()

    assert (before["status"], before["stale"]) == ("not_in_force", False)
    assert "version" not in before
    assert (stale["status"], stale["stale"]) == ("found", True)


async def test_a_repealed_section_is_not_in_force(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("medium")

    repealed = (await _get(client, "1.1", "2026-04-09")).json()

    assert (repealed["status"], repealed["reason"]) == ("not_in_force", "repealed")
    assert repealed["version"]["change_kind"] == "repealed"
    assert (await _get(client, "1.1", "2026-04-08")).json()["status"] == "gap"


async def test_a_band_outside_the_gate_and_low_are_never_returned(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    unknown = {"status": "unknown_section", "reason": "not_published"}

    allow("high")
    assert (await _get(client, "1", "2024-01-01")).json()["status"] == "found"
    assert (await _get(client, "1.2", "2024-01-01")).json() == unknown  # medium
    assert (await _get(client, "1.4", "2024-01-01")).json() == unknown  # low

    allow("high", "medium")
    assert (await _get(client, "1.2", "2024-01-01")).json()["status"] == "found"
    assert (await _get(client, "1.4", "2024-01-01")).json() == unknown

    # the setting refuses `low`; even a gate that named it would not open the band
    with pytest.raises(ValidationError):
        Settings(kb_test_source_bands=("low",))
    app.dependency_overrides[unreviewed_bands] = lambda: frozenset({"low"})
    assert (await _get(client, "1.4", "2024-01-01")).status_code == 404
    assert (await client.get("/admin-acts/2020-8/sections")).status_code == 404


async def test_a_rejected_section_is_never_returned(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow, reviewer: AppUser
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")
    async with kb_factory() as session:
        extraction_id = (
            await session.execute(
                select(Extraction.id).where(Extraction.fields["section_no"].as_string() == "2")
            )
        ).scalar_one()
        session.add(
            Review(
                extraction_id=extraction_id,
                reviewer_id=reviewer.id,
                decision=ReviewDecision.reject,
            )
        )
        await session.commit()

    response = await _get(client, "2", "2024-01-01")

    assert response.json() == {"status": "unknown_section", "reason": "not_published"}
    assert (await _get(client, "1", "2024-01-01")).json()["status"] == "found"


async def test_the_list_names_the_readable_sections_in_document_order(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow, reviewer: AppUser
) -> None:
    await load_acts(kb_factory)
    closed = await client.get("/admin-acts/2020-8/sections")
    assert closed.status_code == 404  # the gate names no band
    assert closed.json() == {"error": {"code": "not_found", "params": {"ref": "2020/8"}}}
    async with kb_factory() as session:
        rows = await session.execute(
            select(Extraction.fields["section_no"].as_string(), Extraction.id)
        )
        ids: dict[str, uuid.UUID] = {section_no: eid for section_no, eid in rows.all()}
        session.add(
            Review(extraction_id=ids["2"], reviewer_id=reviewer.id, decision=ReviewDecision.reject)
        )
        await session.commit()

    allow("high", "medium")
    body = (await client.get("/admin-acts/2020-08/sections")).json()
    allow("high")
    high_only = (await client.get("/admin-acts/2020-8/sections")).json()

    assert (body["ref"], body["title"]) == (
        "2020/8",
        "SGK Genelgesi 2020/8 · İdari Para Cezası Genelgesi",
    )
    # 1.4 is low and 2 is rejected: neither is listed
    assert [(s["section_no"], s["band"], s["review_status"]) for s in body["sections"]] == [
        ("1", "high", "analyzed"),
        ("1.1", "medium", "analyzed"),
        ("1.2", "medium", "analyzed"),
    ]
    assert body["sections"][2] == {
        "section_no": "1.2",
        "heading": "Bildirim süresi",
        "citation": "2020/8 m.1.2",
        "children": [],
        "review_status": "analyzed",
        "band": "medium",
        "extraction_id": str(ids["1.2"]),
    }
    assert [s["section_no"] for s in high_only["sections"]] == ["1"]
    assert (await client.get("/admin-acts/2019-99/sections")).status_code == 404


async def test_a_section_the_newest_load_no_longer_has_is_gone(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")
    assert (await _get(client, "1.2", "2024-01-01")).json()["status"] == "found"

    await load_acts(kb_factory, act_record(TEXT_WITHOUT_1_2, sha256="b9" * 32))

    assert (await _get(client, "1.2", "2024-01-01")).json() == {
        "status": "unknown_section",
        "reason": "not_published",
    }
    listed = (await client.get("/admin-acts/2020-8/sections")).json()["sections"]
    assert [s["section_no"] for s in listed] == ["1", "1.1", "2"]
    assert (await _get(client, "1", "2024-01-01")).json()["status"] == "found"


async def test_a_section_added_by_a_note_is_not_in_force_before_it(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    added = TEXT.replace(
        "2-DİĞER HUSUSLAR\nBu genelgeye",
        "1.5- Yeni bölüm (Ek, 07/02/2025 tarihli ve 2025/4 sayılı Genelge)\nSonradan eklendi.\n"
        "2-DİĞER HUSUSLAR\nBu genelgeye",
    )
    await load_acts(kb_factory, act_record(added))
    allow("high", "medium")

    before = (await _get(client, "1.5", "2025-02-06")).json()
    after = (await _get(client, "1.5", "2025-02-07")).json()

    assert before["status"] == "not_in_force"  # it did not exist: not a gap in a known text
    assert "version" not in before and "gap" not in before
    assert (after["status"], after["version"]["change_kind"]) == ("found", "added")
    assert after["band"] == "medium"


async def test_aliases_of_ref_and_section_reach_the_same_section(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")

    for ref, section in (("2020-8", "1.2"), ("2020-08", "m.1.2"), ("2020_8", "1.2.")):
        body = (await _get(client, section, "2024-01-01", ref=ref)).json()
        assert (body["status"], body["citation"]) == ("found", "2020/8 m.1.2"), (ref, section)


async def test_errors_are_codes(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high", "medium")

    unknown_act = await _get(client, "1", "2024-01-01", ref="2019-99")
    assert unknown_act.status_code == 404
    assert unknown_act.json() == {"error": {"code": "not_found", "params": {"ref": "2019/99"}}}
    unknown_section = await _get(client, "9.9", "2024-01-01")
    assert unknown_section.status_code == 200
    assert unknown_section.json() == {"status": "unknown_section", "reason": "not_published"}
    for bad in ("2024-13-01", "20240101", "yesterday", ""):
        response = await _get(client, "1", bad)
        assert response.status_code == 422, bad
        assert response.json() == {"error": {"code": "invalid_date", "params": {"field": "as_of"}}}
    missing = await client.get("/admin-acts/2020-8/sections/1")
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "validation_error")


async def test_the_api_asks_for_the_service_key_or_a_login(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    await load_acts(kb_factory)
    allow("high")

    for headers in ({"X-Service-Key": "wrong"}, {"X-Service-Key": ""}):
        response = await client.get(
            "/admin-acts/2020-8/sections/1", params={"as_of": "2024-01-01"}, headers=headers
        )
        assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthorized")


# --- the real genelges ---------------------------------------------------------------------------

ADMIN_ACTS_JSONL = os.environ.get("HUKUK_ADMIN_ACTS_JSONL")
GOLDEN = Path(__file__).parents[3] / "packages/ingest/tests/fixtures/admin_acts/golden.toml"


@pytest.mark.skipif(not ADMIN_ACTS_JSONL, reason="HUKUK_ADMIN_ACTS_JSONL not set")
async def test_the_real_genelges_through_the_database_and_the_api(
    client: httpx.AsyncClient, kb_factory: Factory, allow: Allow
) -> None:
    """The golden sections of the ingest tests, but through load -> HTTP, and the künye of the
    handoff ("2020/8 m.2.6.2.5")."""
    records, errors = loader.read_records(Path(str(ADMIN_ACTS_JSONL)))
    assert errors == []
    await load_acts(kb_factory, *records)
    allow("high", "medium")

    for act in tomllib.loads(GOLDEN.read_text(encoding="utf-8"))["act"]:
        for section in act["section"]:
            body = (
                await _get(client, section["no"], "2024-01-01", ref=act["ref"].replace("/", "-"))
            ).json()
            assert body["status"] == "found", (act["ref"], section["no"])
            assert body["version"]["text"] == section["text"]
            assert body["version"]["valid_from"] == act["date"]
            assert body["review_status"] == "analyzed"
    listed = (await client.get("/admin-acts/2020-8/sections")).json()["sections"]
    assert len(listed) == 177 and listed[0]["section_no"] == "1"
    kunye = (await _get(client, "2.6.2.5", "2024-01-01")).json()
    # medium: three "≤" signs are lost in its text layer (`lost_glyph`)
    assert (kunye["status"], kunye["citation"], kunye["band"]) == (
        "found",
        "2020/8 m.2.6.2.5",
        "medium",
    )
    assert kunye["warnings"] == ["lost_glyph", "valid_from_assumed_issue_date"]
    # added with its parent on 21/05/2020 (the note on the heading of K4-B12-11)
    added = "K4-B12-11.1"
    assert (await _get(client, added, "2020-05-20", ref="2018-38")).json()["status"] == (
        "not_in_force"
    )
    assert (await _get(client, added, "2020-05-21", ref="2018-38")).json()["status"] == "found"
    assert kunye["version"]["text"].startswith(
        "2.6.2.5- Mahkeme kararı, veya denetim ve kontrol ile görevlendirilmiş\n"
        "memurlarca yapılan tespitler ya da resmi kurum ve kuruluşlardan alınan yazılar\n"
    )
