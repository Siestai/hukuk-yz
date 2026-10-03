"""Fixtures shared by the database tests (skipped when DATABASE_URL is unset; CI sets it)."""

import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from app.db import make_engine, make_session_factory
from app.models.common import (
    Court,
    CourtLevel,
    RecordStatus,
    Source,
    SourceCategory,
    SourceRank,
    TextCompleteness,
)
from app.models.decision import Decision
from app.models.user import AppUser, UserRole

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
    """Sessions for tests whose code commits: the KB tables and the users are emptied before and
    after."""
    engine = make_engine(database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE source, ingest_job, app_user, login_attempt CASCADE")
            )

    await clean()
    yield make_session_factory(engine)
    await clean()
    await engine.dispose()


@pytest.fixture
async def reviewer(kb_factory: async_sessionmaker[AsyncSession]) -> AppUser:
    """A reviewer user (committed; removed with the rest by `kb_factory`). Its password hash is
    a placeholder: tests that log in create their own users."""
    async with kb_factory() as session:
        user = AppUser(
            email="reviewer@x.test",
            display_name="Reviewer",
            role=UserRole.reviewer,
            password_hash="x",
        )
        session.add(user)
        await session.commit()
    return user


@pytest.fixture
async def users_factory(
    database_url: str, migrated: None
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions for the auth tests: app_user (and with it user_session) and login_attempt are
    emptied around them."""
    engine = make_engine(database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            await connection.execute(text("TRUNCATE app_user, login_attempt CASCADE"))

    await clean()
    yield make_session_factory(engine)
    await clean()
    await engine.dispose()


NewDecision = Callable[..., Awaitable[uuid.UUID]]


@pytest.fixture
def new_decision() -> NewDecision:
    """`await new_decision(session, **overrides)`: an approved, unverified Yargıtay 9. HD
    decision (editorial source) with a random esas number, flushed but not committed."""

    async def add(session: AsyncSession, **overrides: Any) -> uuid.UUID:
        source = Source(
            category=SourceCategory.decision,
            title="t",
            source_rank=SourceRank.editorial,
            status=RecordStatus.approved,
        )
        session.add(source)
        await session.flush()
        fields: dict[str, Any] = {
            "court": Court.yargitay,
            "court_level": CourtLevel.daire,
            "chamber": "9. HD",
            "esas_no": f"2017/{uuid.uuid4().int % 10**6}",
            "karar_no": "2020/1",
            "decision_date": date(2020, 12, 9),
            "text_completeness": TextCompleteness.full,
            **overrides,
        }
        decision = Decision(source_id=source.id, **fields)
        session.add(decision)
        await session.flush()
        return decision.id

    return add
