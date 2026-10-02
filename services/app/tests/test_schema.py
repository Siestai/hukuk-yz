"""Schema tests against a real Postgres (skipped when DATABASE_URL is unset; CI sets it)."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from alembic import command
from app.db import make_engine
from app.models.common import Base

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"
HALF_VECTOR = "[" + ",".join(["0.5"] * 1024) + "]"


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
async def conn(database_url: str, migrated: None) -> AsyncIterator[AsyncConnection]:
    engine = make_engine(database_url)
    async with engine.connect() as connection:
        yield connection
        await connection.rollback()  # every test leaves the database untouched
    await engine.dispose()


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        return {row[0] for row in rows}


def _tables(url: str) -> set[str]:
    async def run() -> set[str]:
        engine = make_engine(url)
        try:
            return await _table_names(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_downgrade_upgrade(alembic_config: Config, database_url: str) -> None:
    expected = set(Base.metadata.tables)

    command.upgrade(alembic_config, "head")
    assert expected <= _tables(database_url)

    command.downgrade(alembic_config, "base")
    assert not expected & _tables(database_url)

    command.upgrade(alembic_config, "head")
    assert expected <= _tables(database_url)


def test_alembic_check_has_no_drift(alembic_config: Config, migrated: None) -> None:
    command.check(alembic_config)  # raises CommandError when models and migration differ


def _uuid(value: object) -> uuid.UUID:
    assert isinstance(value, uuid.UUID)
    return value


async def _source(conn: AsyncConnection, category: str = "statute") -> uuid.UUID:
    result = await conn.execute(
        text(
            f"INSERT INTO source (category, title, source_rank) "
            f"VALUES ('{category}', 't', 'official_primary') RETURNING id"
        )
    )
    return _uuid(result.scalar_one())


async def _article(conn: AsyncConnection, source_id: uuid.UUID) -> uuid.UUID:
    statute = (
        await conn.execute(
            text(
                "INSERT INTO statute (source_id, number, kind, full_title) "
                "VALUES (:s, '4857', 'kanun', 'İş Kanunu') RETURNING id"
            ),
            {"s": source_id},
        )
    ).scalar_one()
    article = await conn.execute(
        text(
            "INSERT INTO statute_article (statute_id, article_no, ordinal) "
            "VALUES (:st, '18', 18) RETURNING id"
        ),
        {"st": statute},
    )
    return _uuid(article.scalar_one())


async def _version(
    conn: AsyncConnection,
    source_id: uuid.UUID,
    article_id: uuid.UUID,
    valid_from: date,
    valid_to: date | None,
    superseded: bool = False,
) -> None:
    await conn.execute(
        text(
            "INSERT INTO statute_article_version "
            "(article_id, text, valid_from, valid_to, change_kind, source_id, superseded_at) "
            "VALUES (:a, 'x', :f, :t, 'original', :s, "
            "CASE WHEN :sup THEN now() END)"
        ),
        {"a": article_id, "f": valid_from, "t": valid_to, "s": source_id, "sup": superseded},
    )


async def test_overlapping_live_versions_are_rejected(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    await _version(conn, source_id, article_id, date(2019, 1, 1), date(2020, 1, 1))

    with pytest.raises(IntegrityError):
        async with conn.begin_nested():
            await _version(conn, source_id, article_id, date(2019, 6, 1), None)


async def test_adjacent_and_superseded_versions_are_allowed(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    await _version(conn, source_id, article_id, date(2019, 1, 1), date(2020, 1, 1))
    # valid_to is exclusive: the next version may start on that very day
    await _version(conn, source_id, article_id, date(2020, 1, 1), None)
    # superseded history may overlap anything
    await _version(conn, source_id, article_id, date(2019, 6, 1), None, superseded=True)


async def test_valid_range_check(conn: AsyncConnection) -> None:
    source_id = await _source(conn)
    article_id = await _article(conn, source_id)
    with pytest.raises(IntegrityError):
        async with conn.begin_nested():
            await _version(conn, source_id, article_id, date(2020, 1, 1), date(2019, 1, 1))


async def _decision(
    conn: AsyncConnection, source_id: uuid.UUID, superseded: bool = False
) -> uuid.UUID:
    result = await conn.execute(
        text(
            "INSERT INTO decision (court, court_level, chamber, esas_no, karar_no, "
            "text_completeness, full_text, source_id, superseded_at) "
            "VALUES ('yargitay', 'daire', '9. HD', '2017/16188', '2018/1234', 'full', "
            "'Kıdem tazminatı davası', :s, CASE WHEN :sup THEN now() END) RETURNING id"
        ),
        {"s": source_id, "sup": superseded},
    )
    return _uuid(result.scalar_one())


async def test_decision_unique_partial(conn: AsyncConnection) -> None:
    source_id = await _source(conn, "decision")
    first = await _decision(conn, source_id)

    with pytest.raises(IntegrityError):
        async with conn.begin_nested():
            await _decision(conn, source_id)

    # once the first record is superseded, the same E/K may be recorded again
    await conn.execute(
        text("UPDATE decision SET superseded_at = now() WHERE id = :i"), {"i": first}
    )
    await _decision(conn, source_id)
    # and superseded rows never collide with each other
    await _decision(conn, source_id, superseded=True)
    await _decision(conn, source_id, superseded=True)


async def test_decision_defaults_and_tsv_trigger(conn: AsyncConnection) -> None:
    source_id = await _source(conn, "decision")
    decision_id = await _decision(conn, source_id)
    row = (
        await conn.execute(
            text(
                "SELECT verification, tsv @@ plainto_tsquery('turkish', unaccent('Tazminati')) "
                "FROM decision WHERE id = :i"
            ),
            {"i": decision_id},
        )
    ).one()
    assert row[0] == "unverified"
    assert row[1] is True


async def test_chunk_embedding_roundtrip(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            "INSERT INTO chunk (category, parent_kind, parent_id, kind, license, ordinal, "
            "char_start, char_end, text, embedding, embedding_model) "
            "VALUES ('decision', 'decision', gen_random_uuid(), 'body', 'public', 0, 0, 5, "
            "'hello', CAST(:e AS vector), 'test-model')"
        ),
        {"e": HALF_VECTOR},
    )
    row = (
        await conn.execute(
            text("SELECT vector_dims(embedding), tsv IS NOT NULL FROM chunk WHERE text = 'hello'")
        )
    ).one()
    assert row[0] == 1024
    assert row[1] is True
