"""Chat API and its fixture backend (task 15). The database tests are skipped when DATABASE_URL
is unset; CI sets it."""

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import chat
from app.auth import hash_password
from app.chat import ChatStore, load_scenarios, open_store
from app.db import make_engine
from app.main import app
from app.models.user import AppUser, UserRole
from app.settings import Settings
from hukuk_models.chat import Answer, AnswerEvent, ChatEvent, DoneEvent, ErrorEvent

PASSWORD = "correct horse battery"
FIXTURES = Path(__file__).parents[3] / "eval" / "fixtures"
Factory = async_sessionmaker[AsyncSession]


def scenario(case_id: str) -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        (FIXTURES / f"{case_id}.scenario.json").read_text(encoding="utf-8")
    )
    return raw


def parse_sse(body: str) -> list[ChatEvent]:
    events = []
    for block in body.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        event = ChatEvent.model_validate_json(data.removeprefix("data: "))
        assert name == f"event: {event.root.type}"
        events.append(event)
    return events


async def login(
    client: httpx.AsyncClient, factory: Factory, email: str, role: UserRole
) -> dict[str, str]:
    async with factory() as session:
        session.add(
            AppUser(
                email=email, display_name=email, role=role, password_hash=hash_password(PASSWORD)
            )
        )
        await session.commit()
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
async def client(database_url: str, users_factory: Factory) -> AsyncIterator[httpx.AsyncClient]:
    app.state.engine = make_engine(database_url)
    app.state.chat_store = ChatStore(load_scenarios(FIXTURES))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as c:
            yield c
    finally:
        app.state.chat_store = None
        await app.state.engine.dispose()


@pytest.fixture
async def user(client: httpx.AsyncClient, users_factory: Factory) -> dict[str, str]:
    return await login(client, users_factory, "u@x.test", UserRole.user)


async def new_conversation(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/chat/conversations", headers=headers)
    assert response.status_code == 201
    return str(response.json()["id"])


async def send(
    client: httpx.AsyncClient, headers: dict[str, str], conversation: str, body: dict[str, Any]
) -> httpx.Response:
    return await client.post(
        f"/chat/conversations/{conversation}/messages", json=body, headers=headers
    )


def answer_of(events: list[ChatEvent]) -> Answer:
    return next(e.root.answer for e in events if isinstance(e.root, AnswerEvent))


def types(events: list[ChatEvent]) -> list[str]:
    return [e.root.type for e in events]


@pytest.mark.parametrize("case_id", ["SB-001", "SB-016", "SB-026"])
async def test_complete_flow(client: httpx.AsyncClient, user: dict[str, str], case_id: str) -> None:
    raw = scenario(case_id)
    conversation = await new_conversation(client, user)

    first = await send(client, user, conversation, {"text": raw["questions"][0]})
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(first.text)
    assert types(events)[0] == "step"
    assert types(events)[-2:] == ["clarification", "done"]
    assert isinstance(events[-1].root, DoneEvent) and events[-1].root.turn_id is not None

    answers = [
        {"question_id": qid, "value": value} for qid, value in raw["complete_answers"].items()
    ]
    second = await send(client, user, conversation, {"clarification_answers": answers})
    events = parse_sse(second.text)
    assert types(events)[-2:] == ["answer", "done"]
    answer = answer_of(events)
    expected = Answer.model_validate_json((FIXTURES / raw["on_complete"]).read_text("utf-8"))
    assert answer == expected

    detail = (await client.get(f"/chat/conversations/{conversation}", headers=user)).json()
    assert [t["role"] for t in detail["turns"]] == ["user", "assistant", "user", "assistant"]
    assert detail["title"] == raw["facts"]["title"]
    listed = (await client.get("/chat/conversations", headers=user)).json()["items"]
    assert [c["id"] for c in listed] == [conversation]


@pytest.mark.parametrize("case_id", ["SB-001", "SB-016", "SB-026"])
async def test_skip_and_unknown_give_the_skipped_answer(
    client: httpx.AsyncClient, user: dict[str, str], case_id: str
) -> None:
    raw = scenario(case_id)
    expected = Answer.model_validate_json((FIXTURES / raw["on_skip"]).read_text("utf-8"))
    for body in (
        {"skip": True},
        {"clarification_answers": [{"question_id": "q1", "unknown": True}]},
    ):
        conversation = await new_conversation(client, user)
        await send(client, user, conversation, {"text": raw["questions"][0]})
        events = parse_sse((await send(client, user, conversation, body)).text)
        answer = answer_of(events)
        assert answer == expected


async def test_message_errors(client: httpx.AsyncClient, user: dict[str, str]) -> None:
    conversation = await new_conversation(client, user)
    response = await send(client, user, conversation, {"text": "Başka bir soru"})
    assert (response.status_code, response.json()["error"]["code"]) == (404, "chat_no_fixture")
    response = await send(client, user, conversation, {"skip": True})
    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "clarification_not_pending",
    )
    assert (await send(client, user, conversation, {})).status_code == 422
    unknown = "00000000-0000-4000-8000-000000000000"
    assert (await send(client, user, unknown, {"text": "x"})).status_code == 404

    await send(client, user, conversation, {"text": scenario("SB-001")["questions"][0]})
    bad = {"clarification_answers": [{"question_id": "nope", "value": "1"}]}
    assert (await send(client, user, conversation, bad)).status_code == 422


async def test_feedback(client: httpx.AsyncClient, user: dict[str, str]) -> None:
    conversation = await new_conversation(client, user)
    raw = scenario("SB-016")
    await send(client, user, conversation, {"text": raw["questions"][0]})
    answers = [{"question_id": q, "value": v} for q, v in raw["complete_answers"].items()]
    events = parse_sse(
        (await send(client, user, conversation, {"clarification_answers": answers})).text
    )
    done = events[-1].root
    assert isinstance(done, DoneEvent)
    turn_id = done.turn_id
    url = f"/chat/turns/{turn_id}/feedback"

    ok = await client.post(
        url, headers=user, json={"rating": "down", "point_index": 0, "kind": "wrong_source"}
    )
    assert ok.status_code == 201
    assert ok.json()["turn_id"] == str(turn_id)
    assert (
        await client.post(url, headers=user, json={"point_index": 99, "rating": "up"})
    ).status_code == 422
    assert (await client.post(url, headers=user, json={})).status_code == 422
    missing = "/chat/turns/00000000-0000-4000-8000-000000000000/feedback"
    assert (await client.post(missing, headers=user, json={"rating": "up"})).status_code == 404


async def test_conversations_are_private(
    client: httpx.AsyncClient, user: dict[str, str], users_factory: Factory
) -> None:
    other = await login(client, users_factory, "o@x.test", UserRole.reviewer)
    conversation = await new_conversation(client, user)
    assert (
        await client.get(f"/chat/conversations/{conversation}", headers=other)
    ).status_code == 404
    assert (await client.get("/chat/conversations", headers=other)).json() == {"items": []}


async def test_roles(
    client: httpx.AsyncClient, user: dict[str, str], users_factory: Factory
) -> None:
    # `user` reaches /chat/* and nothing of the dashboard (the published statute text of
    # /statutes is open to every login: the basis viewer needs it).
    assert (await client.get("/chat/conversations", headers=user)).status_code == 200
    for path in ("/review/decisions", "/review/statutes", "/files"):
        response = await client.get(path, headers=user)
        assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden"), path
    for role in (UserRole.reviewer, UserRole.admin):
        headers = await login(client, users_factory, f"{role.value}@x.test", role)
        assert (await client.get("/chat/conversations", headers=headers)).status_code == 200
    assert (await client.get("/chat/conversations")).status_code == 401


async def test_backend_none_is_unavailable(
    client: httpx.AsyncClient, user: dict[str, str], database_url: str
) -> None:
    assert open_store(Settings(database_url=database_url, chat_backend="none")) is None
    app.state.chat_store = None
    response = await client.get("/chat/conversations", headers=user)
    assert (response.status_code, response.json()["error"]["code"]) == (503, "chat_unavailable")


def test_a_missing_or_empty_fixture_folder_stops_the_start(tmp_path: Path) -> None:
    for folder in (tmp_path, tmp_path / "missing"):
        settings = Settings(database_url="postgresql+asyncpg://x/x", chat_backend="fixture")
        settings.chat_fixtures_dir = folder
        with pytest.raises(RuntimeError, match="no chat fixtures"):
            open_store(settings)


async def test_a_failure_inside_the_stream_is_an_error_event_then_done(
    client: httpx.AsyncClient, user: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real = chat._add_turn

    def broken(conv: Any, **fields: Any) -> Any:
        if fields["role"] == "assistant":
            raise RuntimeError("boom")
        return real(conv, **fields)

    monkeypatch.setattr(chat, "_add_turn", broken)
    conversation = await new_conversation(client, user)
    # The user turn is stored before the stream starts, so the failure comes with a 200 stream.
    response = await client.post(
        f"/chat/conversations/{conversation}/messages",
        json={"text": scenario("SB-001")["questions"][0]},
        headers=user,
    )
    assert response.status_code == 200
    events = parse_sse(response.text)
    assert types(events)[-2:] == ["error", "done"]
    error, done = events[-2].root, events[-1].root
    assert isinstance(error, ErrorEvent) and error.code == "internal_error"
    assert isinstance(done, DoneEvent) and done.turn_id is None
