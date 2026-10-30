"""The Postgres of the graph checkpoints: the `agent` schema of the database `app` uses. The
agent writes nothing else there (docs/architecture.md §2, rule 1)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

SCHEMA = "agent"


def psycopg_url(database_url: str) -> str:
    """The same database as a libpq URL: `app` names it for SQLAlchemy (postgresql+asyncpg://)."""
    scheme, sep, rest = database_url.partition("://")
    return scheme.split("+")[0] + sep + rest


@dataclass(frozen=True)
class Database:
    pool: AsyncConnectionPool
    saver: AsyncPostgresSaver

    async def ping(self) -> None:
        async with self.pool.connection() as conn:
            await conn.execute("SELECT 1")


@asynccontextmanager
async def open_database(database_url: str) -> AsyncIterator[Database]:
    url = psycopg_url(database_url)
    async with await AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    pool = AsyncConnectionPool(
        url,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-c search_path={SCHEMA}",
        },
        open=False,
    )
    async with pool:
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        yield Database(pool, saver)
