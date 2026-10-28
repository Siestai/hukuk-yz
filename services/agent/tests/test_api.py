"""`POST /run`: the service key, the server-sent events of a turn, `/healthz` and `/readyz`."""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from agent_fakes import FakeKb, Script, require_database_url, scripted
from pydantic import SecretStr
from test_graph import unique_thread

from agent.api import create_app
from agent.llm import Models
from agent.settings import Settings
from hukuk_models import ErrorCode

KEY = {"X-Service-Key": "agent-key"}
QUESTION = "5 ay kıdeme sahip bir işçi. İşe iade davası açabilir mi gerekçesi ile birlikte açıkla"


@pytest.fixture
def database_url() -> str:
    return require_database_url()


@pytest.fixture
async def client(database_url: str) -> AsyncIterator[httpx.AsyncClient]:
    model = scripted(Script())
    app = create_app(
        Settings(
            database_url=database_url,
            agent_service_key=SecretStr("agent-key"),
            kb_service_key=SecretStr("kb-key"),
        ),
        models=Models(model, model),
        kb=FakeKb(),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agent.test") as c:
            yield c


def events(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    parsed = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n")
        parsed.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


async def test_run_needs_the_service_key(client: httpx.AsyncClient) -> None:
    body = {"thread_id": "t", "text": QUESTION}

    missing = await client.post("/run", json=body)
    wrong = await client.post("/run", json=body, headers={"X-Service-Key": "other"})

    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == {"error": {"code": ErrorCode.unauthorized, "params": {}}}


async def test_a_turn_streams_steps_facts_and_the_clarification_then_the_answer(
    client: httpx.AsyncClient,
) -> None:
    thread = unique_thread()
    first = await client.post("/run", headers=KEY, json={"thread_id": thread, "text": QUESTION})

    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in events(first)]
    assert names == ["step", "facts", "step", "clarification", "done"]
    assert events(first)[0][1]["label"] == "Olay kaydediliyor"
    questions = events(first)[3][1]["clarification"]["questions"]
    assert len(questions) == 5

    answers = [{"question_id": q["id"], "unknown": True} for q in questions]
    answers[2] = {"question_id": "q3", "value": "2026-10-03"}
    second = await client.post(
        "/run", headers=KEY, json={"thread_id": thread, "clarification_answers": answers}
    )

    kinds = [name for name, _ in events(second)]
    assert kinds[-2:] == ["answer", "done"]
    answer = events(second)[-2][1]["answer"]
    assert answer["status"] == "conditional"
    assert answer["disclaimer"] == "Hukuki görüş değildir."
    assert len(events(second)[-1][1]["trace_id"]) == 32


async def test_skip_gives_a_conditional_answer(client: httpx.AsyncClient) -> None:
    thread = unique_thread()
    await client.post("/run", headers=KEY, json={"thread_id": thread, "text": QUESTION})

    skipped = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})

    assert events(skipped)[-2][1]["answer"]["status"] == "conditional"


async def test_answers_with_no_open_question_are_a_conflict(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/run", headers=KEY, json={"thread_id": unique_thread(), "skip": True}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == ErrorCode.clarification_not_pending


async def test_a_request_must_carry_one_of_text_answers_or_skip(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/run", headers=KEY, json={"thread_id": "t"})

    assert response.status_code == 422


async def test_health_and_readiness(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json() == {"status": "ok"}
