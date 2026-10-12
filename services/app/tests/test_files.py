"""Files API (task 12a). The database tests are skipped when DATABASE_URL is unset; CI sets it."""

import asyncio
import hashlib
import re
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import hash_password
from app.db import make_engine
from app.files.api import _lock_content
from app.files.store import LocalFileStore
from app.main import app
from app.models.common import (
    DocumentType,
    Extraction,
    FileDeletion,
    IngestFile,
    IngestJob,
    IngestKind,
    ReviewStatus,
    ScanStatus,
)
from app.models.user import AppUser, UserRole
from app.settings import Settings

PASSWORD = "correct horse battery"
Factory = async_sessionmaker[AsyncSession]
MAX_BYTES = 100_000


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
    client.cookies.clear()
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
def store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "store"
    monkeypatch.setattr(
        "app.files.api.get_settings",
        lambda: Settings(database_url="unused", file_store_root=root, file_max_bytes=MAX_BYTES),
    )
    return root


async def scanned(factory: Factory, *ids: str) -> None:
    """Mark files as scanned: the worker is done with them, so they may be deleted."""
    async with factory() as session:
        for fid in ids:
            file = await session.get(IngestFile, uuid.UUID(fid))
            assert file is not None
            file.scan_status = ScanStatus.done
        await session.commit()


@pytest.fixture
async def me(client: httpx.AsyncClient, kb_factory: Factory) -> Login:
    return await _login_as(client, kb_factory, "baran@x.test", UserRole.reviewer)


@pytest.fixture
async def boss(client: httpx.AsyncClient, kb_factory: Factory) -> Login:
    return await _login_as(client, kb_factory, "orhan@x.test", UserRole.admin)


async def upload(
    client: httpx.AsyncClient,
    login: Login,
    data: bytes,
    name: str = "genelge.pdf",
    path: str = "/files",
    **fields: str,
) -> httpx.Response:
    form = fields if "bare" in fields else {"doc_type": "genelge", **fields}
    form.pop("bare", None)
    return await client.post(
        path, headers=login.headers, data=form, files={"file": (name, data, "application/pdf")}
    )


@pytest.fixture
def pdf(make_pdf: Callable[..., bytes]) -> Callable[..., bytes]:
    """A distinct small PDF per number."""

    def build(n: int = 0) -> bytes:
        return make_pdf(f"belge numara {n} " * 30)

    return build


async def test_an_upload_is_stored_by_hash_and_queued(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    data = pdf(1)
    response = await upload(
        client, me, data, doc_date="2020-12-09", official_ref="2020/39", note="not"
    )
    assert response.status_code == 201, response.text
    body = response.json()
    digest = hashlib.sha256(data).hexdigest()
    assert body["sha256"] == digest
    assert body["size"] == len(data)
    assert body["scan_status"] == "queued"
    assert body["detected_type"] == "pdf"
    assert body["original_name"] == "genelge.pdf"
    assert (body["doc_type"], body["doc_date"], body["official_ref"]) == (
        "genelge",
        "2020-12-09",
        "2020/39",
    )
    assert body["uploaded_by_id"] == str(me.id)
    assert body["uploaded_by_name"] == "baran@x.test"
    key = f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    assert (store_root / key).read_bytes() == data
    async with kb_factory() as session:
        file = (await session.execute(select(IngestFile))).scalar_one()
        job = await session.get(IngestJob, file.job_id)
    assert file.storage_key == key
    assert job is not None
    assert (job.kind, job.created_by) == (IngestKind.upload, me.id)


async def test_the_same_file_again_is_409_with_the_existing_id(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    first = (await upload(client, me, pdf(2))).json()
    again = await upload(client, me, pdf(2), name="baska-ad.pdf")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "duplicate_file"
    assert again.json()["error"]["params"] == {"file_id": first["id"], "archived": False}


async def test_a_duplicate_of_an_archived_file_says_so(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    first = (await upload(client, me, pdf(3))).json()
    assert (await client.post(f"/files/{first['id']}/archive", headers=boss.headers)).is_success
    again = await upload(client, me, pdf(3))
    assert again.status_code == 409
    assert again.json()["error"]["params"] == {"file_id": first["id"], "archived": True}
    back = await client.post(f"/files/{first['id']}/unarchive", headers=boss.headers)
    assert back.json()["archived_at"] is None


async def test_a_file_over_the_limit_is_413(
    client: httpx.AsyncClient, me: Login, store_root: Path, make_pdf: Callable[..., bytes]
) -> None:
    big = make_pdf() + b"\n%" + b"x" * (MAX_BYTES + 10)
    response = await upload(client, me, big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert response.json()["error"]["params"] == {"max_bytes": MAX_BYTES}
    assert not any(store_root.rglob("*")) or not [p for p in store_root.rglob("*") if p.is_file()]


async def test_a_chunked_upload_over_the_limit_is_413_without_content_length(
    client: httpx.AsyncClient, me: Login, store_root: Path
) -> None:
    boundary = "xBOUNDARYx"
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="doc_type"\r\n\r\ngenelge\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        'filename="big.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
    ).encode()
    sent = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal sent
        yield head
        for _ in range(64):  # 4 MB, far over FILE_MAX_BYTES plus the form overhead
            sent += 1
            yield b"%PDF-1.4 " + b"x" * 65_000
        yield f"\r\n--{boundary}--\r\n".encode()

    request = client.build_request(
        "POST",
        "/files",
        headers={**me.headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        content=body(),
    )
    assert "content-length" not in request.headers
    response = await client.send(request)
    assert response.status_code == 413
    assert response.json()["error"] == {
        "code": "file_too_large",
        "params": {"max_bytes": MAX_BYTES},
    }
    assert not [p for p in store_root.rglob("*") if p.is_file()]


async def test_a_pdf_name_with_other_content_is_415(
    client: httpx.AsyncClient, me: Login, store_root: Path, scan_png: bytes
) -> None:
    response = await upload(client, me, scan_png, name="karar.pdf")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"
    other = await upload(client, me, b"MZ\x90\x00 not a document", name="x.exe")
    assert other.status_code == 415


async def test_bad_uploads_are_400_or_422(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    empty = await upload(client, me, b"")
    assert (empty.status_code, empty.json()["error"]["code"]) == (400, "invalid_file")
    no_file = await client.post("/files", headers=me.headers, files={"doc_type": (None, "genelge")})
    assert (no_file.status_code, no_file.json()["error"]["code"]) == (400, "invalid_file")
    bad_type = await upload(client, me, pdf(4), doc_type="sozlesme")
    assert bad_type.status_code == 422
    not_form = await client.post("/files", headers=me.headers, json={})
    assert not_form.status_code == 415


async def test_a_cookie_session_uploads_only_with_the_script_header(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    pdf: Callable[..., bytes],
) -> None:
    """The browser authenticates by cookie: a multipart POST is refused (CSRF) unless it carries
    `X-Requested-With`, which a cross-site form cannot add."""
    login = await client.post("/auth/login", json={"email": "baran@x.test", "password": PASSWORD})
    assert login.status_code == 200  # the cookie is in the client's jar now
    form = {"doc_type": "genelge"}
    files = {"file": ("a.pdf", pdf(9), "application/pdf")}
    refused = await client.post("/files", data=form, files=files)
    assert (refused.status_code, refused.json()["error"]["code"]) == (415, "unsupported_media_type")
    allowed = await client.post(
        "/files", data=form, files=files, headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert allowed.status_code == 201
    # the exemption is for the upload routes only: other routes and methods stay JSON-only
    other = await client.post(
        f"/files/{allowed.json()['id']}/rescan",
        files=files,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert (other.status_code, other.json()["error"]["code"]) == (415, "unsupported_media_type")


async def test_the_name_is_metadata_only(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    response = await upload(client, me, pdf(5), name="../../etc/passwd.pdf")
    assert response.status_code == 201
    assert response.json()["original_name"] == "passwd.pdf"
    assert not (store_root.parent / "etc").exists()
    assert all(p.resolve().is_relative_to(store_root.resolve()) for p in store_root.rglob("*"))


async def test_a_new_version_supersedes_and_the_list_shows_one_row(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    first = (await upload(client, me, pdf(6), official_ref="2020/39", note="eski")).json()
    second = await upload(client, me, pdf(7), path=f"/files/{first['id']}/versions")
    assert second.status_code == 201, second.text
    new = second.json()
    assert new["supersedes_id"] == first["id"]
    # empty fields are copied from the previous version
    assert (new["doc_type"], new["official_ref"], new["note"]) == ("genelge", "2020/39", "eski")
    listing = (await client.get("/files", headers=me.headers)).json()
    assert [(i["id"], i["version_count"]) for i in listing["items"]] == [(new["id"], 2)]
    detail = (await client.get(f"/files/{first['id']}", headers=me.headers)).json()
    assert [v["id"] for v in detail["versions"]] == [first["id"], new["id"]]
    assert detail["id"] == first["id"]
    # the chain does not branch, and an old record keeps its place
    again = await upload(client, me, pdf(8), path=f"/files/{first['id']}/versions")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "file_version_conflict")
    missing = await upload(client, me, pdf(9), path=f"/files/{uuid.uuid4()}/versions")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "file_not_found")


async def test_the_list_filters_and_pages(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    ids = []
    for n, (doc_type, name) in enumerate(
        [("kanun", "ışçı.pdf"), ("genelge", "b.pdf"), ("genelge", "c_d.pdf")]
    ):
        ids.append(
            (await upload(client, me, pdf(20 + n), name=name, doc_type=doc_type)).json()["id"]
        )

    async def get(**params: str | int) -> httpx.Response:
        return await client.get("/files", headers=me.headers, params=params)

    assert [i["id"] for i in (await get(doc_type="genelge")).json()["items"]] == ids[:0:-1]
    assert [i["id"] for i in (await get(q="ışç")).json()["items"]] == [ids[0]]
    assert [i["id"] for i in (await get(q="c_d")).json()["items"]] == [ids[2]]
    assert (await get(q="%")).json()["items"] == []
    assert len((await get(scan_status="queued")).json()["items"]) == 3
    assert (await get(scan_status="done")).json()["items"] == []
    page1 = (await get(limit=2)).json()
    assert [i["id"] for i in page1["items"]] == ids[:0:-1]
    # the cursor survives a URL that is not percent-encoded
    assert re.fullmatch(r"[A-Za-z0-9_=-]+", page1["next_cursor"])
    raw = await client.get(f"/files?limit=2&cursor={page1['next_cursor']}", headers=me.headers)
    assert [i["id"] for i in raw.json()["items"]] == [ids[0]]
    page2 = (await get(limit=2, cursor=page1["next_cursor"])).json()
    assert [i["id"] for i in page2["items"]] == [ids[0]]
    assert page2["next_cursor"] is None
    assert (await get(cursor="bozuk")).status_code == 422
    await client.post(f"/files/{ids[1]}/archive", headers=boss.headers)
    assert ids[1] not in [i["id"] for i in (await get()).json()["items"]]
    assert [i["id"] for i in (await get(archived="true")).json()["items"]] == [ids[1]]


async def test_content_and_text_are_served_with_safe_headers(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    data = pdf(30)
    uploaded = (await upload(client, me, data, name="Genelge özel 2020.pdf")).json()
    response = await client.get(f"/files/{uploaded['id']}/content", headers=me.headers)
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('inline; filename="Genelge _')
    assert "filename*=UTF-8''Genelge%20%C3%B6zel%202020.pdf" in disposition
    # no text before the scan
    assert (
        await client.get(f"/files/{uploaded['id']}/text", headers=me.headers)
    ).status_code == 404
    text = "çıkarılan metin"
    store = LocalFileStore(store_root)
    async with kb_factory() as session:
        file = await session.get(IngestFile, uuid.UUID(uploaded["id"]))
        assert file is not None
        file.scan_result = {
            "text_key": store.put_text(file.sha256, text),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        await session.commit()
    served = await client.get(f"/files/{uploaded['id']}/text", headers=me.headers)
    assert served.status_code == 200
    assert served.text == text
    assert served.headers["content-type"].startswith("text/plain")


async def test_content_is_refused_when_the_stored_bytes_do_not_match_the_hash(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    uploaded = (await upload(client, me, pdf(31))).json()
    digest = uploaded["sha256"]
    (store_root / "sha256" / digest[:2] / digest[2:4] / digest).write_bytes(b"%PDF-tampered")
    response = await client.get(f"/files/{uploaded['id']}/content", headers=me.headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "file_not_found"
    assert b"tampered" not in response.content


async def test_archive_and_rescan_are_admin_only(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    uploaded = (await upload(client, me, pdf(32))).json()
    fid = uploaded["id"]
    for action in ("archive", "unarchive", "rescan"):
        denied = await client.post(f"/files/{fid}/{action}", headers=me.headers)
        assert (denied.status_code, denied.json()["error"]["code"]) == (403, "forbidden"), action
    archived = await client.post(f"/files/{fid}/archive", headers=boss.headers)
    assert archived.json()["archived_at"] is not None
    rescanned = await client.post(f"/files/{fid}/rescan", headers=boss.headers)
    assert rescanned.json()["scan_status"] == "queued"
    assert (
        await client.post(f"/files/{uuid.uuid4()}/archive", headers=boss.headers)
    ).status_code == 404


async def test_a_rescan_clears_the_old_outcome_and_a_running_file_is_refused(
    client: httpx.AsyncClient,
    me: Login,
    boss: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    fid = (await upload(client, me, pdf(33))).json()["id"]
    text_key = LocalFileStore(store_root).put_text("a" * 64, "eski metin")

    async def set_scan(status: ScanStatus, result: dict[str, Any] | None) -> None:
        async with kb_factory() as session:
            file = await session.get(IngestFile, uuid.UUID(fid))
            assert file is not None
            file.scan_status, file.scan_result = status, result
            await session.commit()

    text_sha = hashlib.sha256(b"eski metin").hexdigest()
    await set_scan(ScanStatus.done, {"text_key": text_key, "text_sha256": text_sha})
    assert (await client.get(f"/files/{fid}/text", headers=me.headers)).status_code == 200
    rescanned = await client.post(f"/files/{fid}/rescan", headers=boss.headers)
    assert (rescanned.status_code, rescanned.json()["scan_status"]) == (200, "queued")
    assert rescanned.json()["scan_result"] is None
    gone = await client.get(f"/files/{fid}/text", headers=me.headers)
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "file_not_found")
    # already queued: nothing changes
    assert (await client.post(f"/files/{fid}/rescan", headers=boss.headers)).status_code == 200
    # the path an imported file had in the archive outlives a rescan (task 12c)
    await set_scan(ScanStatus.done, {"import_path": "Mevzuat/Genelge/G.pdf", "pages": 3})
    kept = await client.post(f"/files/{fid}/rescan", headers=boss.headers)
    assert kept.json()["scan_result"] == {"import_path": "Mevzuat/Genelge/G.pdf"}
    await set_scan(ScanStatus.running, {"claim": "x", "attempts": 1})
    busy = await client.post(f"/files/{fid}/rescan", headers=boss.headers)
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "scan_in_progress")
    detail = (await client.get(f"/files/{fid}", headers=me.headers)).json()
    assert detail["scan_status"] == "running"


async def test_an_admin_may_upload_and_nothing_is_open_without_a_login(
    client: httpx.AsyncClient, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    assert (await upload(client, boss, pdf(40))).status_code == 201
    fid = uuid.uuid4()
    nobody = Login(fid, {})
    calls = [
        client.get("/files"),
        client.get(f"/files/{fid}"),
        client.get(f"/files/{fid}/content"),
        client.get(f"/files/{fid}/text"),
        upload(client, nobody, pdf(41)),
        upload(client, nobody, pdf(41), path=f"/files/{fid}/versions"),
        client.post(f"/files/{fid}/archive"),
        client.post(f"/files/{fid}/unarchive"),
        client.post(f"/files/{fid}/rescan"),
    ]
    for call in calls:
        response = await call
        assert response.status_code == 401, response.request.url


async def test_without_a_file_store_root_the_endpoints_are_503(
    client: httpx.AsyncClient, me: Login, monkeypatch: pytest.MonkeyPatch, pdf: Callable[..., bytes]
) -> None:
    monkeypatch.setattr("app.files.api.get_settings", lambda: Settings(database_url="unused"))
    response = await upload(client, me, pdf(50))
    assert (response.status_code, response.json()["error"]["code"]) == (
        503,
        "file_store_unavailable",
    )
    fid = uuid.uuid4()
    assert (await client.get(f"/files/{fid}/content", headers=me.headers)).status_code == 503
    assert (await client.get(f"/files/{fid}/text", headers=me.headers)).status_code == 503


async def test_a_loader_row_has_no_content(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, kb_factory: Factory
) -> None:
    async with kb_factory() as session:
        job = IngestJob(kind=IngestKind.upload)
        session.add(job)
        await session.flush()
        row = IngestFile(
            job_id=job.id,
            path="Yargi/1.pdf",
            sha256="1" * 64,
            size=3,
            detected_type="pdf",
            review_status=ReviewStatus.approved,
        )
        session.add(row)
        await session.commit()
        assert row.scan_status is ScanStatus.done
        row_id = row.id
    detail = (await client.get(f"/files/{row_id}", headers=me.headers)).json()
    assert (detail["original_name"], detail["uploaded_by_name"]) == (None, None)
    assert (await client.get(f"/files/{row_id}/content", headers=me.headers)).status_code == 404
    assert (await client.post(f"/files/{row_id}/rescan", headers=boss.headers)).status_code == 404


async def test_concurrent_identical_uploads_make_one_record(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    import asyncio

    data = pdf(60)
    responses = await asyncio.gather(*(upload(client, me, data) for _ in range(4)))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409]
    async with kb_factory() as session:
        count: Any = (
            await session.execute(select(func.count()).select_from(IngestFile))
        ).scalar_one()
    assert count == 1


# --- review: upload without fields, approval, deletion (task 13a) ---------------------------------


async def approve(
    client: httpx.AsyncClient, login: Login, file_id: str, **body: Any
) -> httpx.Response:
    return await client.post(
        f"/files/{file_id}/approve", headers=login.headers, json={"doc_type": "genelge", **body}
    )


async def bare_upload(
    client: httpx.AsyncClient, login: Login, data: bytes, name: str = "belge.pdf"
) -> dict[str, Any]:
    response = await upload(client, login, data, name=name, bare="1")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_an_upload_with_nothing_but_the_file_is_pending_and_has_no_type(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    body = await bare_upload(client, me, pdf(70))
    assert (body["review_status"], body["doc_type"], body["doc_date"]) == ("pending", None, None)
    assert (body["suggestions"], body["matches"], body["approved_by_id"]) == (None, None, None)
    assert body["title"] is None and body["approved_at"] is None


async def test_what_the_user_typed_is_a_suggestion_of_the_source_user(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    body = (
        await upload(client, me, pdf(71), doc_type="kanun", doc_date="2026-10-01", note="n")
    ).json()
    assert body["review_status"] == "pending"
    assert body["suggestions"] == {
        "doc_type": {"value": "kanun", "source": "user", "evidence": None},
        "doc_date": {"value": "2026-10-01", "source": "user", "evidence": None},
    }


async def test_approving_writes_the_final_fields_and_who_approved(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    fid = (await bare_upload(client, me, pdf(72)))["id"]
    response = await approve(
        client,
        me,  # the uploader approves their own file
        fid,
        doc_type="yonetmelik",
        doc_date="2024-05-01",
        official_ref=" RG 29983 ",
        title="Alt İşverenlik Yönetmeliği",
        origin_url="https://example.test/y",
        note="",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["review_status"], body["approved_by_id"]) == ("approved", str(me.id))
    assert body["approved_at"] is not None
    assert (body["doc_type"], body["doc_date"], body["official_ref"], body["title"]) == (
        "yonetmelik",
        "2024-05-01",
        "RG 29983",
        "Alt İşverenlik Yönetmeliği",
    )
    assert (body["origin_url"], body["note"]) == ("https://example.test/y", None)
    again = await approve(client, boss, fid)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "file_not_pending")


async def test_an_approval_needs_a_valid_type_and_a_login(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    fid = (await bare_upload(client, me, pdf(73)))["id"]
    url = f"/files/{fid}/approve"
    assert (await client.post(url, headers=me.headers, json={})).status_code == 422
    for body in (
        {"doc_type": "sozlesme"},
        {"doc_type": None},
        {"doc_type": "kanun", "doc_date": "x"},
    ):
        assert (await client.post(url, headers=me.headers, json=body)).status_code == 422
    assert (await client.post(url, json={"doc_type": "kanun"})).status_code == 401
    assert (await approve(client, me, str(uuid.uuid4()))).status_code == 404
    detail = (await client.get(f"/files/{fid}", headers=me.headers)).json()
    assert detail["review_status"] == "pending"


async def test_an_approval_can_link_the_file_as_the_next_version(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    old = (await bare_upload(client, me, pdf(74), "eski.pdf"))["id"]
    assert (await approve(client, me, old)).status_code == 200
    new = (await bare_upload(client, me, pdf(75), "yeni.pdf"))["id"]
    linked = await approve(client, me, new, supersedes_id=old)
    assert (linked.status_code, linked.json()["supersedes_id"]) == (200, old)
    listing = (await client.get("/files", headers=me.headers)).json()
    assert [(i["id"], i["version_count"]) for i in listing["items"]] == [(new, 2)]


async def test_the_version_rules_hold_at_approval(
    client: httpx.AsyncClient, me: Login, boss: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    a = (await bare_upload(client, me, pdf(76)))["id"]
    b = (await bare_upload(client, me, pdf(77)))["id"]
    c = (await bare_upload(client, me, pdf(78)))["id"]
    assert (await approve(client, me, a)).status_code == 200
    assert (await approve(client, me, b, supersedes_id=a)).status_code == 200
    # the chain does not branch
    branch = await approve(client, me, c, supersedes_id=a)
    assert (branch.status_code, branch.json()["error"]["code"]) == (409, "file_version_conflict")
    # an archived file gets no next version
    assert (await client.post(f"/files/{b}/archive", headers=boss.headers)).status_code == 200
    archived = await approve(client, me, c, supersedes_id=b)
    assert (archived.status_code, archived.json()["error"]["code"]) == (
        409,
        "file_version_conflict",
    )
    # nor does a file link to itself, or to a file that does not exist
    own = await approve(client, me, c, supersedes_id=c)
    assert own.json()["error"]["code"] == "file_version_conflict"
    assert (await approve(client, me, c, supersedes_id=str(uuid.uuid4()))).status_code == 404
    # the failed attempts changed nothing
    assert (await client.get(f"/files/{c}", headers=me.headers)).json()[
        "review_status"
    ] == "pending"


async def test_an_approval_cannot_close_a_loop_of_versions(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    first = (await bare_upload(client, me, pdf(79)))["id"]
    version = (await upload(client, me, pdf(80), path=f"/files/{first}/versions", bare="1")).json()[
        "id"
    ]
    # `first` is pending and has a next version; linking it behind that version is a loop
    loop = await approve(client, me, first, supersedes_id=version)
    assert (loop.status_code, loop.json()["error"]["code"]) == (409, "file_version_conflict")


async def test_a_version_upload_keeps_its_link_unless_the_approval_says_otherwise(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    first = (await bare_upload(client, me, pdf(81)))["id"]
    assert (await approve(client, me, first)).status_code == 200
    second = (await upload(client, me, pdf(82), path=f"/files/{first}/versions")).json()
    assert second["review_status"] == "pending"
    kept = await approve(client, me, second["id"])
    assert kept.json()["supersedes_id"] == first
    third = (await upload(client, me, pdf(83), path=f"/files/{second['id']}/versions")).json()
    apart = await approve(client, me, third["id"], supersedes_id=None)
    assert apart.json()["supersedes_id"] is None


async def test_only_an_admin_takes_an_approval_back_and_not_while_a_newer_version_exists(
    client: httpx.AsyncClient,
    me: Login,
    boss: Login,
    store_root: Path,
    pdf: Callable[..., bytes],
    kb_factory: Factory,
) -> None:
    fid = (await bare_upload(client, me, pdf(84)))["id"]
    pending = await client.post(f"/files/{fid}/unapprove", headers=boss.headers)
    assert (pending.status_code, pending.json()["error"]["code"]) == (409, "file_not_approved")
    assert (await approve(client, me, fid)).status_code == 200
    denied = await client.post(f"/files/{fid}/unapprove", headers=me.headers)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "forbidden")
    newer = (await upload(client, me, pdf(85), path=f"/files/{fid}/versions")).json()["id"]
    blocked = await client.post(f"/files/{fid}/unapprove", headers=boss.headers)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "file_has_newer_version")
    await scanned(kb_factory, newer)
    assert (await client.delete(f"/files/{newer}", headers=me.headers)).status_code == 204
    back = await client.post(f"/files/{fid}/unapprove", headers=boss.headers)
    assert back.status_code == 200, back.text
    assert (back.json()["review_status"], back.json()["approved_by_id"]) == ("pending", None)
    assert back.json()["approved_at"] is None
    assert back.json()["doc_type"] == "genelge"  # the fields stay for the next approval


async def test_the_list_filters_by_review_status(
    client: httpx.AsyncClient, me: Login, store_root: Path, pdf: Callable[..., bytes]
) -> None:
    done = (await bare_upload(client, me, pdf(86)))["id"]
    waiting = (await bare_upload(client, me, pdf(87)))["id"]
    await approve(client, me, done)

    async def ids(query: str) -> set[str]:
        response = await client.get(f"/files{query}", headers=me.headers)
        return {i["id"] for i in response.json()["items"]}

    assert await ids("") == {done, waiting}
    assert await ids("?review_status=pending") == {waiting}
    assert await ids("?review_status=approved") == {done}
    assert (await client.get("/files?review_status=x", headers=me.headers)).status_code == 422


async def test_a_pending_file_is_deleted_with_its_blob_text_job_and_a_trace(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    data = pdf(88)
    body = await bare_upload(client, me, data, "silinecek.pdf")
    fid, digest = body["id"], body["sha256"]
    store = LocalFileStore(store_root)
    text = store.put_text(digest, "metin")
    async with kb_factory() as session:
        file = await session.get(IngestFile, uuid.UUID(fid))
        assert file is not None
        job_id = file.job_id
        file.doc_type = DocumentType.karar
        await session.commit()
    await scanned(kb_factory, fid)
    response = await client.delete(f"/files/{fid}", headers=me.headers)
    assert response.status_code == 204
    assert (await client.get(f"/files/{fid}", headers=me.headers)).status_code == 404
    assert not (store_root / f"sha256/{digest[:2]}/{digest[2:4]}/{digest}").exists()
    assert not store.exists(text)
    async with kb_factory() as session:
        assert await session.get(IngestJob, job_id) is None
        trace = (await session.execute(select(FileDeletion))).scalar_one()
    assert (trace.file_id, trace.sha256, trace.original_name) == (
        uuid.UUID(fid),
        digest,
        "silinecek.pdf",
    )
    assert (trace.doc_type, trace.review_status, trace.deleted_by) == (
        DocumentType.karar,
        ReviewStatus.pending,
        me.id,
    )
    assert trace.deleted_at is not None
    assert trace.snapshot["id"] == fid
    assert trace.snapshot["review_status"] == "pending"
    assert trace.snapshot["scan_status"] == "done"
    assert trace.snapshot["uploaded_by"] == str(me.id)
    assert (await client.delete(f"/files/{fid}", headers=me.headers)).status_code == 404


async def test_an_approved_file_is_deleted_only_after_its_approval_is_taken_back(
    client: httpx.AsyncClient,
    me: Login,
    boss: Login,
    store_root: Path,
    pdf: Callable[..., bytes],
    kb_factory: Factory,
) -> None:
    fid = (await bare_upload(client, me, pdf(89)))["id"]
    await approve(client, me, fid)
    refused = await client.delete(f"/files/{fid}", headers=boss.headers)
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "file_approved")
    await scanned(kb_factory, fid)
    await client.post(f"/files/{fid}/unapprove", headers=boss.headers)
    assert (await client.delete(f"/files/{fid}", headers=boss.headers)).status_code == 204


async def test_a_reviewer_deletes_only_their_own_files_and_an_admin_any(
    client: httpx.AsyncClient,
    me: Login,
    boss: Login,
    kb_factory: Factory,
    store_root: Path,
    pdf: Callable[..., bytes],
) -> None:
    other = await _login_as(client, kb_factory, "ibrahim@x.test", UserRole.reviewer)
    mine = (await bare_upload(client, me, pdf(90)))["id"]
    denied = await client.delete(f"/files/{mine}", headers=other.headers)
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "forbidden")
    assert (await client.get(f"/files/{mine}", headers=me.headers)).status_code == 200
    await scanned(kb_factory, mine)
    assert (await client.delete(f"/files/{mine}", headers=boss.headers)).status_code == 204
    assert (await client.delete(f"/files/{uuid.uuid4()}", headers=boss.headers)).status_code == 404
    assert (await client.delete(f"/files/{mine}")).status_code == 401


async def test_a_file_with_a_next_version_or_with_extractions_is_not_deleted(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    first = (await bare_upload(client, me, pdf(91)))["id"]
    second = (await upload(client, me, pdf(92), path=f"/files/{first}/versions")).json()["id"]
    await scanned(kb_factory, first, second)
    blocked = await client.delete(f"/files/{first}", headers=me.headers)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "file_has_newer_version")
    async with kb_factory() as session:
        session.add(
            Extraction(file_id=uuid.UUID(second), parser_name="decisions", parser_version="1")
        )
        await session.commit()
    processed = await client.delete(f"/files/{second}", headers=me.headers)
    assert (processed.status_code, processed.json()["error"]["code"]) == (409, "file_processed")
    for fid in (first, second):
        assert (await client.get(f"/files/{fid}", headers=me.headers)).status_code == 200


async def test_deleting_the_newest_version_makes_the_older_one_the_head_again(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    pdf: Callable[..., bytes],
    kb_factory: Factory,
) -> None:
    first = (await bare_upload(client, me, pdf(93)))["id"]
    second = (await upload(client, me, pdf(94), path=f"/files/{first}/versions")).json()["id"]
    await scanned(kb_factory, second)
    assert (await client.delete(f"/files/{second}", headers=me.headers)).status_code == 204
    listing = (await client.get("/files", headers=me.headers)).json()
    assert [(i["id"], i["version_count"]) for i in listing["items"]] == [(first, 1)]
    again = await upload(client, me, pdf(95), path=f"/files/{first}/versions")
    assert again.status_code == 201  # the chain can grow again


async def test_the_blob_stays_when_another_row_uses_the_content(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    body = await bare_upload(client, me, pdf(96))
    digest = body["sha256"]
    async with kb_factory() as session:
        job = IngestJob(kind=IngestKind.upload)
        session.add(job)
        await session.flush()
        # a row of the archive loaders with the same content and no stored file of its own
        session.add(
            IngestFile(
                job_id=job.id,
                path="Yargi/1.pdf",
                sha256=digest,
                size=3,
                review_status=ReviewStatus.approved,
            )
        )
        await session.commit()
    await scanned(kb_factory, body["id"])
    store = LocalFileStore(store_root)
    key = f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    assert (await client.delete(f"/files/{body['id']}", headers=me.headers)).status_code == 204
    assert store.exists(key)


async def test_a_file_that_is_queued_or_running_is_not_deleted(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    fid = (await bare_upload(client, me, pdf(97)))["id"]
    for status in (ScanStatus.queued, ScanStatus.running):
        async with kb_factory() as session:
            file = await session.get(IngestFile, uuid.UUID(fid))
            assert file is not None
            file.scan_status = status
            await session.commit()
        refused = await client.delete(f"/files/{fid}", headers=me.headers)
        assert (refused.status_code, refused.json()["error"]["code"]) == (409, "scan_in_progress")
    await scanned(kb_factory, fid)
    assert (await client.delete(f"/files/{fid}", headers=me.headers)).status_code == 204


async def test_an_upload_of_the_same_bytes_in_flight_keeps_the_blob_of_a_deleted_file(
    client: httpx.AsyncClient,
    me: Login,
    store_root: Path,
    kb_factory: Factory,
    pdf: Callable[..., bytes],
) -> None:
    body = await bare_upload(client, me, pdf(98))
    digest = body["sha256"]
    await scanned(kb_factory, body["id"])
    key = f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    async with kb_factory() as session:
        # an upload of the same bytes that holds the content lock and has not committed its row
        await _lock_content(session, digest)
        deleting = asyncio.create_task(client.delete(f"/files/{body['id']}", headers=me.headers))
        await asyncio.sleep(0.5)
        assert not deleting.done()  # the delete waits for the lock before it removes the blob
        job = IngestJob(kind=IngestKind.upload)
        session.add(job)
        await session.flush()
        session.add(
            IngestFile(
                job_id=job.id,
                path="x.pdf",
                sha256=digest,
                size=3,
                review_status=ReviewStatus.approved,
            )
        )
        await session.commit()
    assert (await deleting).status_code == 204
    assert LocalFileStore(store_root).exists(key)
