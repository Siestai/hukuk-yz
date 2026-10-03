"""Auth endpoints and dependencies (task 08). Skipped when DATABASE_URL is unset; CI sets it."""

import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
import pytest
from argon2 import PasswordHasher
from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import auth
from app.auth import hash_password, require_role
from app.auth import router as auth_router
from app.db import make_engine
from app.main import app
from app.models.user import AppUser, UserRole, UserSession

PASSWORD = "correct horse battery"
SessionFactory = async_sessionmaker[AsyncSession]


@asynccontextmanager
async def _client(target: FastAPI, database_url: str) -> AsyncIterator[httpx.AsyncClient]:
    target.state.engine = make_engine(database_url)
    try:
        # https, so that the Secure session cookie is sent back by the client's cookie jar
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=target), base_url="https://test"
        ) as client:
            yield client
    finally:
        await target.state.engine.dispose()


@pytest.fixture
async def client(
    database_url: str, users_factory: SessionFactory
) -> AsyncIterator[httpx.AsyncClient]:
    async with _client(app, database_url) as c:
        yield c


@pytest.fixture
async def admin_only_client(
    database_url: str, users_factory: SessionFactory
) -> AsyncIterator[httpx.AsyncClient]:
    guarded = FastAPI()
    guarded.include_router(auth_router)

    @guarded.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    async def admin_only() -> dict[str, bool]:
        return {"ok": True}

    async with _client(guarded, database_url) as c:
        yield c


async def _add_user(
    factory: SessionFactory,
    email: str = "orhan@x.test",
    role: UserRole = UserRole.admin,
    is_active: bool = True,
    password_hash: str | None = None,
) -> uuid.UUID:
    async with factory() as session:
        user = AppUser(
            email=email,
            display_name="Orhan",
            role=role,
            password_hash=password_hash or hash_password(PASSWORD),
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _login(client: httpx.AsyncClient, email: str = "orhan@x.test") -> str:
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["token"]
    return token


JSON = {"content-type": "application/json"}


async def test_login_sets_cookie_and_me_works_with_cookie_and_bearer(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    response = await client.post(
        "/auth/login", json={"email": "orhan@x.test", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "orhan@x.test"
    assert body["user"]["role"] == "admin"
    cookie = response.headers["set-cookie"]
    assert f"hukuk_session={body['token']}" in cookie
    for flag in ("HttpOnly", "SameSite=lax", "Path=/", "Secure"):
        assert flag in cookie

    by_cookie = await client.get("/auth/me")
    assert by_cookie.status_code == 200
    assert by_cookie.json()["email"] == "orhan@x.test"
    assert set(by_cookie.json()) == {"id", "email", "display_name", "role"}

    client.cookies.clear()
    by_bearer = await client.get("/auth/me", headers={"authorization": f"Bearer {body['token']}"})
    assert by_bearer.status_code == 200
    assert by_bearer.json() == by_cookie.json()

    async with users_factory() as session:
        last_login = (await session.execute(select(AppUser.last_login_at))).scalar_one()
    assert last_login is not None


async def test_wrong_password_unknown_email_and_inactive_user_get_the_same_401(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    await _add_user(users_factory, email="pasif@x.test", is_active=False)
    attempts = [
        ("orhan@x.test", "wrong password!!"),
        ("nobody@x.test", PASSWORD),
        ("pasif@x.test", PASSWORD),
    ]
    responses = [
        await client.post("/auth/login", json={"email": e, "password": p}) for e, p in attempts
    ]
    assert {r.status_code for r in responses} == {401}
    assert len({r.text for r in responses}) == 1
    assert all("set-cookie" not in r.headers for r in responses)


async def test_expired_session_is_401(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    async with users_factory() as session:
        await session.execute(
            text("UPDATE user_session SET expires_at = :t"),
            {"t": datetime.now(UTC) - timedelta(seconds=1)},
        )
        await session.commit()
    response = await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_revoked_session_is_401(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    async with users_factory() as session:
        await session.execute(text("UPDATE user_session SET revoked_at = now()"))
        await session.commit()
    response = await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_logout_revokes_the_session_and_clears_the_cookie(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    response = await client.post("/auth/logout", headers=JSON)
    assert response.status_code == 204
    assert "hukuk_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]

    again = await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    assert again.status_code == 401
    async with users_factory() as session:
        revoked_at = (await session.execute(select(UserSession.revoked_at))).scalar_one()
    assert revoked_at is not None


async def test_deactivated_user_loses_access(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    async with users_factory() as session:
        await session.execute(text("UPDATE app_user SET is_active = false"))
        await session.commit()
    response = await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_me_without_a_token_is_401(client: httpx.AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401


async def test_require_role_admin_rejects_a_reviewer_with_403(
    admin_only_client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory, email="admin@x.test", role=UserRole.admin)
    await _add_user(users_factory, email="baran@x.test", role=UserRole.reviewer)

    reviewer = await _login(admin_only_client, "baran@x.test")
    response = await admin_only_client.get(
        "/admin-only", headers={"authorization": f"Bearer {reviewer}"}
    )
    assert response.status_code == 403

    admin = await _login(admin_only_client, "admin@x.test")
    response = await admin_only_client.get(
        "/admin-only", headers={"authorization": f"Bearer {admin}"}
    )
    assert response.status_code == 200


async def test_cookie_post_without_json_content_type_is_415_but_bearer_is_exempt(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)

    by_cookie = await client.post(
        "/auth/logout", content="x", headers={"content-type": "text/plain"}
    )
    assert by_cookie.status_code == 415

    client.cookies.clear()
    by_bearer = await client.post(
        "/auth/logout",
        content="x",
        headers={"content-type": "text/plain", "authorization": f"Bearer {token}"},
    )
    assert by_bearer.status_code != 415
    assert by_bearer.status_code == 204


async def test_database_holds_neither_the_token_nor_the_password(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    async with users_factory() as session:
        stored = (await session.execute(select(UserSession.token_hash))).scalar_one()
        password_hash = (await session.execute(select(AppUser.password_hash))).scalar_one()
    assert stored != token
    assert stored == hashlib.sha256(token.encode()).hexdigest()
    assert PASSWORD not in password_hash
    assert password_hash.startswith("$argon2id$")


async def test_login_normalizes_the_email_case(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    response = await client.post(
        "/auth/login", json={"email": " ORHAN@x.test ", "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_login_upgrades_an_outdated_hash(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    await _add_user(users_factory, password_hash=weak)
    await _login(client)
    async with users_factory() as session:
        stored = (await session.execute(select(AppUser.password_hash))).scalar_one()
    assert stored != weak
    assert not PasswordHasher().check_needs_rehash(stored)


async def test_a_malformed_stored_hash_is_the_same_401_as_a_wrong_password(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory, password_hash="not an argon2 hash")
    wrong = await client.post(
        "/auth/login", json={"email": "nobody@x.test", "password": "wrong password!!"}
    )
    broken = await client.post("/auth/login", json={"email": "orhan@x.test", "password": PASSWORD})
    assert broken.status_code == 401
    assert broken.text == wrong.text
    assert "set-cookie" not in broken.headers


async def test_an_unknown_email_is_verified_against_the_dummy_hash(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    verified: list[str] = []

    # PasswordHasher has __slots__, so the module's hasher is replaced by a spying subclass.
    class SpyHasher(PasswordHasher):
        def verify(self, hash: str | bytes, password: str | bytes) -> Literal[True]:
            verified.append(str(hash))
            return super().verify(hash, password)

    monkeypatch.setattr(auth, "_hasher", SpyHasher())
    response = await client.post(
        "/auth/login", json={"email": "nobody@x.test", "password": PASSWORD}
    )
    assert response.status_code == 401
    assert verified == [auth._DUMMY_HASH]


async def test_bearer_wins_over_the_cookie_without_fallback(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)  # the cookie jar now holds a valid session cookie

    valid_bearer = await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    assert valid_bearer.status_code == 200

    client.cookies.clear()
    client.cookies.set("hukuk_session", "not a session", domain="test")
    assert (
        await client.get("/auth/me", headers={"authorization": f"Bearer {token}"})
    ).status_code == 200

    client.cookies.clear()
    client.cookies.set("hukuk_session", token, domain="test")
    invalid_bearer = await client.get("/auth/me", headers={"authorization": "Bearer nope"})
    assert invalid_bearer.status_code == 401


async def test_last_seen_is_written_only_when_older_than_the_interval(
    client: httpx.AsyncClient, users_factory: SessionFactory
) -> None:
    await _add_user(users_factory)
    token = await _login(client)
    headers = {"authorization": f"Bearer {token}"}

    async def last_seen() -> datetime | None:
        async with users_factory() as session:
            return (await session.execute(select(UserSession.last_seen_at))).scalar_one()

    assert await last_seen() is None
    await client.get("/auth/me", headers=headers)
    first = await last_seen()
    assert first is not None
    await client.get("/auth/me", headers=headers)
    assert await last_seen() == first

    stale = first - auth.LAST_SEEN_INTERVAL - timedelta(seconds=1)
    async with users_factory() as session:
        await session.execute(text("UPDATE user_session SET last_seen_at = :t"), {"t": stale})
        await session.commit()
    await client.get("/auth/me", headers=headers)
    refreshed = await last_seen()
    assert refreshed is not None
    assert refreshed > stale
