import asyncio

from pgvector.sqlalchemy import Vector
from sqlalchemy.engine import Connection

import app.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from app.db import make_engine
from app.models.common import Base
from app.settings import get_settings

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    # Let reflection recognise pgvector columns so `alembic check` does not see them as unknown.
    connection.dialect.ischema_names["vector"] = Vector  # type: ignore[attr-defined]
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = make_engine(get_settings().database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
