"""The checkpoints live in Postgres, in the `agent` schema: a thread that stopped at the
clarification goes on in a new process."""

from datetime import date

import pytest
from agent_fakes import (
    FakeKb,
    Script,
    answer_all,
    ask,
    only,
    require_database_url,
    scripted,
    turn,
    unique_thread,
)

from agent.db import open_database, psycopg_url
from agent.graph import build_graph
from agent.llm import Llm, Models
from agent.nodes import Deps
from hukuk_models.chat import AnswerEvent, ClarificationEvent


def test_the_sqlalchemy_url_becomes_a_libpq_url() -> None:
    assert psycopg_url("postgresql+asyncpg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"
    assert psycopg_url("postgresql://u@/d?host=/tmp") == "postgresql://u@/d?host=/tmp"


@pytest.fixture
def database_url() -> str:
    return require_database_url()


def deps() -> Deps:
    model = scripted(Script())
    return Deps(llm=Llm(Models(model, model)), kb=FakeKb(), today=lambda: date(2026, 10, 28))


async def test_a_thread_resumes_after_a_restart(database_url: str) -> None:
    thread = unique_thread()
    async with open_database(database_url) as db:
        first = await turn(build_graph(deps(), db.saver), ask(thread))
        assert only(first, ClarificationEvent).clarification.total == 5

    async with open_database(database_url) as db:
        await db.ping()
        second = await turn(build_graph(deps(), db.saver), answer_all(thread))
        assert only(second, AnswerEvent).answer.applied_law_date == date(2026, 10, 3)
        async with db.pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT count(*) AS n FROM information_schema.tables "
                "WHERE table_schema = 'agent' AND table_name LIKE 'checkpoint%'"
            )
            row = await cursor.fetchone()
        assert row is not None and row["n"] >= 3  # type: ignore[call-overload]
