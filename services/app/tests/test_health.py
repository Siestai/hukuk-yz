import os
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text

from app.db import make_engine
from app.main import app

UNREACHABLE_URL = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/none"


async def _client(database_url: str) -> AsyncIterator[httpx.AsyncClient]:
    app.state.engine = make_engine(database_url)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await app.state.engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(UNREACHABLE_URL):
        yield c


@pytest.fixture
async def db_client() -> AsyncIterator[httpx.AsyncClient]:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    engine = make_engine(url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("database unreachable")
    finally:
        await engine.dispose()
    async for c in _client(url):
        yield c


async def test_healthz(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


async def test_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={"x-request-id": "abc"})
    assert response.headers["x-request-id"] == "abc"


async def test_readyz_503_when_db_down(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 503


async def test_readyz_ok_with_db(db_client: httpx.AsyncClient) -> None:
    response = await db_client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
