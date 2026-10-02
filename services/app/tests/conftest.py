"""Fixtures shared by the database tests (skipped when DATABASE_URL is unset; CI sets it)."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from app.db import make_engine, make_session_factory

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    return Config(str(ALEMBIC_INI))


@pytest.fixture
def migrated(alembic_config: Config) -> None:
    # Sync on purpose: env.py runs its own event loop via asyncio.run().
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def kb_factory(
    database_url: str, migrated: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions for tests whose code commits: the KB tables are emptied before and after."""
    engine = make_engine(database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE source, ingest_job CASCADE"))

    await clean()
    yield make_session_factory(engine)
    await clean()
    await engine.dispose()
