"""Persistent chat ownership, quota, feedback and the validated SSE bridge."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import current_user
from app.chat import _sse
from app.chat_api import router
from app.db import make_engine
from app.errors import install
from app.models.chat import ChatFeedback, ChatTurn
from app.models.user import AppUser, UserRole
from app.settings import Settings, get_settings
from hukuk_models.chat import (
    CaseFacts,
    Clarification,
    ClarificationEvent,
    ClarificationQuestion,
    DoneEvent,
    QuestionInput,
    Turn,
)

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture
async def stack(
    database_url: str, users_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[httpx.AsyncClient, AppUser, AppUser, Settings, FastAPI]]:
    settings = Settings(
        database_url=database_url,
        chat_backend="agent",
        agent_service_key=SecretStr("test-service-key-18"),
        chat_daily_limit=2,
    )
    app = FastAPI()
    install(app)
    app.include_router(router)
    app.state.engine = make_engine(database_url)
    async with users_factory() as db:
        user = AppUser(
            email="owner@example.test", display_name="Owner", role=UserRole.user, password_hash="x"
        )
        other = AppUser(
            email="other@example.test", display_name="Other", role=UserRole.user, password_hash="x"
        )
        db.add_all([user, other])
        await db.commit()
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[get_settings] = lambda: settings
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, user, other, settings, app
    await app.state.engine.dispose()


async def test_ownership_admin_feedback_and_restart(stack: Any, users_factory: Factory) -> None:
    client, user, other, settings, app = stack
    response = await client.post("/chat/conversations")
    assert response.status_code == 201
    id = response.json()["id"]
    now = datetime.now(UTC)
    turn = Turn(
        id=uuid.uuid4(),
        role="assistant",
        created_at=now,
        facts=CaseFacts(title="Test", facts=[]),
        trace_id="trace-18",
    )
    async with users_factory() as db:
        db.add(
            ChatTurn(
                id=turn.id,
                conversation_id=uuid.UUID(id),
                role="assistant",
                mode="short",
                payload=turn.model_dump(mode="json"),
                trace_id="trace-18",
                created_at=now,
            )
        )
        await db.commit()
    feedback = await client.post(
        f"/chat/turns/{turn.id}/feedback", json={"rating": "down", "correction": "Test"}
    )
    assert feedback.status_code == 201
    assert (await client.get("/chat/feedback")).status_code == 403
    app.dependency_overrides[current_user] = lambda: other
    assert (await client.get(f"/chat/conversations/{id}")).status_code == 404
    assert (await client.get("/chat/conversations")).json() == {"items": []}
    assert (
        await client.post(f"/chat/conversations/{id}/messages", json={"text": "q"})
    ).status_code == 404
    assert (
        await client.post(f"/chat/turns/{turn.id}/feedback", json={"rating": "up"})
    ).status_code == 404
    other.role = UserRole.admin
    assert (await client.get(f"/chat/conversations/{id}")).status_code == 200
    exported = (await client.get("/chat/feedback?since=2020-01-01T00:00:00Z")).json()
    assert exported[0]["id"] == feedback.json()["id"]
    await app.state.engine.dispose()
    app.state.engine = make_engine(settings.database_url)
    detail = (await client.get(f"/chat/conversations/{id}")).json()
    assert detail["turns"][0]["id"] == str(turn.id)
    async with users_factory() as db:
        assert await db.scalar(select(func.count()).select_from(ChatFeedback)) == 1


async def test_quota_serializes_concurrent_reservations(
    stack: Any, users_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:

    client, user, other, settings, app = stack
    settings.chat_daily_limit = 1
    ids = [(await client.post("/chat/conversations")).json()["id"] for _ in range(2)]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(503))
        ),
    )
    results = await asyncio.gather(
        *(
            client.post(f"/chat/conversations/{id}/messages", json={"text": "question"})
            for id in ids
        )
    )
    assert sorted(r.status_code for r in results) == [200, 429]
    rejected = next(r for r in results if r.status_code == 429)
    assert rejected.json()["error"]["code"] == "chat_daily_limit"
    streamed = next(r for r in results if r.status_code == 200)
    assert '"type":"error"' in streamed.text
    assert '"turn_id":null' in streamed.text
    async with users_factory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(ChatTurn).where(ChatTurn.role == "user")
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(ChatTurn).where(ChatTurn.role == "assistant")
            )
            == 0
        )


async def test_bridge_saves_only_terminal_valid_results(
    stack: Any, users_factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:

    client, user, other, settings, app = stack
    id = (await client.post("/chat/conversations")).json()["id"]
    clarification = Clarification(
        questions=[
            ClarificationQuestion(
                id="q", fact_key="date", text="Tarih?", why="Test", input=QuestionInput(kind="date")
            )
        ],
        index=1,
        total=1,
    )
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=_sse(ClarificationEvent(clarification=clarification))
            + _sse(DoneEvent(trace_id="trace-test")),
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle)),
    )
    response = await client.post(f"/chat/conversations/{id}/messages", json={"text": "Question"})
    assert response.status_code == 200
    assert seen[0].headers["x-service-key"] == "test-service-key-18"
    detail = (await client.get(f"/chat/conversations/{id}")).json()
    assert [t["role"] for t in detail["turns"]] == ["user", "assistant"]
    assert detail["turns"][-1]["trace_id"] == "trace-test"
    assert detail["turns"][-1]["id"] in response.text
    settings.chat_daily_limit = 1
    skipped = await client.post(f"/chat/conversations/{id}/messages", json={"skip": True})
    assert skipped.status_code == 200
    assert (
        await client.post(
            f"/chat/conversations/{id}/messages",
            json={"clarification_answers": [{"question_id": "wrong", "unknown": True}]},
        )
    ).status_code == 422


async def test_concurrent_same_conversation_is_rejected_and_lock_is_released(
    stack: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, user, other, settings, app = stack
    id = (await client.post("/chat/conversations")).json()["id"]
    entered, release = asyncio.Event(), asyncio.Event()

    async def handle(request: httpx.Request) -> httpx.Response:
        entered.set()
        await release.wait()
        return httpx.Response(503)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle))
    )
    first = asyncio.create_task(
        client.post(f"/chat/conversations/{id}/messages", json={"text": "First"})
    )
    await asyncio.wait_for(entered.wait(), timeout=10)
    second = await client.post(f"/chat/conversations/{id}/messages", json={"text": "Second"})
    assert second.status_code == 409
    release.set()
    assert (await first).status_code == 200
    # A new request can acquire the lock after the first upstream failure.
    third = await client.post(f"/chat/conversations/{id}/messages", json={"text": "Third"})
    assert third.status_code == 200


@pytest.mark.parametrize(
    "wire", [b"", b"data: not-json\n\n", b'event: done\ndata: {"type":"done"}\n\n']
)
async def test_missing_or_invalid_agent_result_is_an_honest_error(
    stack: Any,
    users_factory: Factory,
    monkeypatch: pytest.MonkeyPatch,
    wire: bytes,
) -> None:
    client, user, other, settings, app = stack
    id = (await client.post("/chat/conversations")).json()["id"]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=wire))
        ),
    )
    response = await client.post(f"/chat/conversations/{id}/messages", json={"text": "Question"})
    assert '"type":"error"' in response.text
    assert '"turn_id":null' in response.text
    detail = (await client.get(f"/chat/conversations/{id}")).json()
    assert [t["role"] for t in detail["turns"]] == ["user"]


async def test_daily_quota_excludes_previous_utc_day(
    stack: Any,
    users_factory: Factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import timedelta

    client, user, other, settings, app = stack
    settings.chat_daily_limit = 1
    id = (await client.post("/chat/conversations")).json()["id"]
    yesterday = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
        seconds=1
    )
    old = Turn(id=uuid.uuid4(), role="user", text="Yesterday", created_at=yesterday)
    async with users_factory() as db:
        db.add(
            ChatTurn(
                id=old.id,
                conversation_id=uuid.UUID(id),
                role="user",
                payload=old.model_dump(mode="json"),
                mode="short",
                created_at=yesterday,
            )
        )
        await db.commit()
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(503))
        ),
    )
    assert (
        await client.post(f"/chat/conversations/{id}/messages", json={"text": "Today"})
    ).status_code == 200
    assert (
        await client.post(f"/chat/conversations/{id}/messages", json={"text": "Again"})
    ).status_code == 429
