from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

CONNECT_TIMEOUT_SECONDS = 5


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url, pool_pre_ping=True, connect_args={"timeout": CONNECT_TIMEOUT_SECONDS}
    )


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
