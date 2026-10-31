"""Persistent chat ownership, quota, feedback and the validated SSE bridge."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast

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


@pytest.mark.parametrize(
    "reply",
    [{"skip": True}, {"clarification_answers": [{"question_id": "q", "value": "2026-10-03"}]}],
)
async def test_failed_resume_retries_same_delivery_after_reload_at_full_quota(
    stack: Any, users_factory: Factory, monkeypatch: pytest.MonkeyPatch, reply: dict[str, Any]
) -> None:
    import json

    client, user, other, settings, app = stack
    settings.chat_daily_limit = 1
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
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 2:
            return httpx.Response(503)
        return httpx.Response(
            200, content=_sse(ClarificationEvent(clarification=clarification)) + _sse(DoneEvent())
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle))
    )
    await client.post(f"/chat/conversations/{id}/messages", json={"text": "Question"})
    first = await client.post(f"/chat/conversations/{id}/messages", json=reply)
    assert '"type":"error"' in first.text
    detail = (await client.get(f"/chat/conversations/{id}")).json()
    pending = detail.get("pending_request") or {**reply, "request_id": str(uuid.uuid4())}
    retried = await client.post(f"/chat/conversations/{id}/messages", json=pending)
    assert retried.status_code == 200
    assert detail["pending_request"] == pending
    assert {k: pending[k] for k in reply} == {
        k: ([{**a, "unknown": False} for a in v] if k == "clarification_answers" else v)
        for k, v in reply.items()
    }
    assert '"type":"error"' not in retried.text
    assert requests[1] == requests[2]
    async with users_factory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(ChatTurn).where(ChatTurn.role == "user")
            )
            == 2
        )
    # Re-delivery of the completed request returns its saved assistant, without graph execution.
    replay = await client.post(f"/chat/conversations/{id}/messages", json=pending)
    assert replay.status_code == 200
    assert len(requests) == 3
    assert replay.text == retried.text
    assert (await client.get(f"/chat/conversations/{id}")).json()["pending_request"] is None
    settings.chat_daily_limit = 2
    await client.post(f"/chat/conversations/{id}/messages", json={"text": "New question"})
    stale = await client.post(f"/chat/conversations/{id}/messages", json=pending)
    assert stale.status_code == 409
    assert len(requests) == 4


async def test_real_auth_small_pool_parallel_kb_and_tcp_disconnect(
    database_url: str,
    statutes_published: dict[str, uuid.UUID],
    kb_factory: Factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib
    from contextlib import asynccontextmanager
    from datetime import timedelta
    from pathlib import Path

    import uvicorn

    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "agent" / "tests"))
    from agent_fakes import QUESTION, Script, scripted
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from agent.api import create_app as create_agent
    from agent.llm import Models
    from agent.settings import Settings as AgentSettings
    from app.auth import router as auth_router
    from app.models.user import UserSession
    from app.search import router as search_router
    from app.statutes import router as statutes_router

    settings = Settings(
        database_url=database_url,
        chat_backend="agent",
        agent_base_url="http://127.0.0.1:8182",
        agent_service_key=SecretStr("tcp-agent-service-key-18"),
        kb_service_key=SecretStr("tcp-kb-service-key-18"),
        agent_timeout_seconds=8,
        chat_daily_limit=2,
    )
    target = FastAPI()
    install(target)
    for r in (router, auth_router, search_router, statutes_router):
        target.include_router(r)
    target.dependency_overrides[get_settings] = lambda: settings
    target.state.engine = create_async_engine(
        database_url, pool_size=1, max_overflow=0, pool_timeout=0.5
    )
    token = "tcp-real-session"
    async with kb_factory() as db:
        user = AppUser(
            email="tcp@example.test", display_name="TCP", role=UserRole.user, password_hash="x"
        )
        db.add(user)
        await db.flush()
        db.add(
            UserSession(
                user_id=user.id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                last_seen_at=datetime.now(UTC),
            )
        )
        await db.commit()
    callbacks = []
    block, entered, release = False, asyncio.Event(), asyncio.Event()

    @target.middleware("http")
    async def observe(request: Any, call_next: Any) -> Any:
        if request.url.path.startswith(("/statutes/", "/kb/search")):
            callbacks.append(request.url.path)
            if block:
                entered.set()
                await release.wait()
        return await call_next(request)

    model = scripted(Script())
    agent = create_agent(
        AgentSettings(
            database_url=database_url,
            app_base_url="http://127.0.0.1:8181",
            agent_service_key=SecretStr("tcp-agent-service-key-18"),
            kb_service_key=SecretStr("tcp-kb-service-key-18"),
        ),
        models=Models(model, model),
    )

    @asynccontextmanager
    async def live(app: FastAPI, port: int) -> AsyncIterator[None]:
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        task = asyncio.create_task(server.serve())
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
            yield
        finally:
            release.set()
            server.should_exit = True
            await asyncio.wait_for(task, 15)

    try:
        async with (
            live(target, 8181),
            live(agent, 8182),
            httpx.AsyncClient(
                base_url="http://127.0.0.1:8181",
                headers={"Authorization": "Bearer " + token},
                timeout=15,
            ) as client,
        ):
            ids = [(await client.post("/chat/conversations")).json()["id"] for _ in range(2)]
            initial = await asyncio.gather(
                *(
                    client.post(f"/chat/conversations/{id}/messages", json={"text": QUESTION})
                    for id in ids
                )
            )
            assert all(
                '"type":"clarification"' in r.text and '"type":"error"' not in r.text
                for r in initial
            )
            # Authentication SELECTs and stream locks must leave the sole KB connection free.
            assert target.state.engine.pool.checkedout() == 0
            answers = await asyncio.gather(
                *(
                    client.post(f"/chat/conversations/{id}/messages", json={"skip": True})
                    for id in ids
                )
            )
            assert all('"code":"answer_not_verified"' in r.text for r in answers)
            assert all(
                '"code":"chat_unavailable"' not in r.text
                and '"code":"internal_error"' not in r.text
                for r in answers
            )
            assert any(p.startswith("/statutes/") for p in callbacks)
            assert "/kb/search" in callbacks
            exhausted = (await client.post("/chat/conversations")).json()["id"]
            assert (
                await client.post(
                    f"/chat/conversations/{exhausted}/messages", json={"text": QUESTION}
                )
            ).status_code == 429
            settings.chat_daily_limit = 50
            # Close an actual socket after facts; wait for durable clarification delivery.
            id = (await client.post("/chat/conversations")).json()["id"]
            async with client.stream(
                "POST", f"/chat/conversations/{id}/messages", json={"text": QUESTION}
            ) as response:
                async for line in response.aiter_lines():
                    if '"type":"facts"' in line:
                        break

            async def completed() -> dict[str, Any]:
                async with asyncio.timeout(10):
                    while True:
                        detail = (await client.get(f"/chat/conversations/{id}")).json()
                        if detail["pending_request"] is None:
                            return cast(dict[str, Any], detail)
                        await asyncio.sleep(0.02)

            assert (await completed())["turns"][-1]["clarification"]
            # Also disconnect exactly after the clarification event, before terminal done.
            clarification_id = (await client.post("/chat/conversations")).json()["id"]
            async with client.stream(
                "POST", f"/chat/conversations/{clarification_id}/messages", json={"text": QUESTION}
            ) as response:
                async for line in response.aiter_lines():
                    if '"type":"clarification"' in line:
                        break
            original_id, id = id, clarification_id
            assert (await completed())["turns"][-1]["clarification"]
            id = original_id
            # Consume the interrupt, disconnect after facts while the actual KB HTTP call waits.
            block = True
            reply = {"clarification_answers": [{"question_id": "q1", "unknown": True}]}
            async with client.stream(
                "POST", f"/chat/conversations/{id}/messages", json=reply
            ) as response:
                async for line in response.aiter_lines():
                    if '"type":"facts"' in line:
                        break
            await asyncio.wait_for(entered.wait(), 10)
            overlap = await client.post(f"/chat/conversations/{id}/messages", json={"skip": True})
            assert overlap.status_code == 409
            direct_overlap = await client.post(
                "http://127.0.0.1:8182/run",
                headers={"X-Service-Key": "tcp-agent-service-key-18"},
                json={"thread_id": id, "skip": True},
            )
            assert direct_overlap.status_code == 503
            release.set()
            from app.models.chat import ChatConversation

            async with asyncio.timeout(10):
                while True:
                    async with kb_factory() as db:
                        row = await db.get(ChatConversation, uuid.UUID(id))
                        assert row is not None and row.delivery is not None
                        if row.delivery["status"] == "completed":
                            break
                    await asyncio.sleep(0.02)
            # A terminal gate error is a completed request and replays its honest error,
            # never another graph execution. Its identity also survives reload.
            retry_body = (await client.get(f"/chat/conversations/{id}")).json()["pending_request"]
            replay = await client.post(f"/chat/conversations/{id}/messages", json=retry_body)
            assert '"code":"answer_not_verified"' in replay.text
            async with target.state.engine.connect() as conn:
                async with asyncio.timeout(10):
                    while True:
                        app_free = await conn.scalar(
                            text("SELECT pg_try_advisory_lock(hashtextextended(:key, 18))"),
                            {"key": id},
                        )
                        agent_free = await conn.scalar(
                            text("SELECT pg_try_advisory_lock(hashtextextended(:key, 20))"),
                            {"key": id},
                        )
                        await conn.execute(text("SELECT pg_advisory_unlock_all()"))
                        await conn.commit()
                        if app_free and agent_free and target.state.chat_connections._value == 4:
                            break
                        await asyncio.sleep(0.01)
                assert app_free and agent_free
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM pg_locks WHERE locktype='advisory' "
                            "AND database=(SELECT oid FROM pg_database "
                            "WHERE datname=current_database())"
                        )
                    )
                    == 0
                )
            assert target.state.engine.pool.checkedout() == 0
    finally:
        release.set()
        await target.state.engine.dispose()


async def test_stream_admission_is_bounded_and_slots_return(
    stack: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user, other, settings, app = stack
    settings.chat_daily_limit = 10
    ids = [(await client.post("/chat/conversations")).json()["id"] for _ in range(5)]
    count = 0
    entered, release = asyncio.Event(), asyncio.Event()

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count == 4:
            entered.set()
        await release.wait()
        return httpx.Response(503)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handle))
    )
    tasks = [
        asyncio.create_task(client.post(f"/chat/conversations/{id}/messages", json={"text": "q"}))
        for id in ids[:4]
    ]
    try:
        await asyncio.wait_for(entered.wait(), 10)
        assert (
            await client.post(f"/chat/conversations/{ids[4]}/messages", json={"text": "q"})
        ).status_code == 503
        assert count == 4
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert (
        await client.post(f"/chat/conversations/{ids[4]}/messages", json={"text": "q"})
    ).status_code == 200
