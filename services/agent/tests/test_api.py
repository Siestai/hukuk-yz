"""`POST /run`: the service key, the server-sent events of a turn, `/healthz` and `/readyz`."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from agent_fakes import (
    QUESTION,
    FailingKb,
    FakeKb,
    Script,
    require_database_url,
    row,
    scripted,
    unique_thread,
)
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from agent.api import create_app
from agent.kb import KbClient, KbUnavailable
from agent.llm import Models
from agent.settings import Settings
from hukuk_models import ErrorCode

KEY = {"X-Service-Key": "agent-service-key-for-tests"}


@pytest.fixture(params=["memory", "postgres"])
def database_url(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    if request.param == "postgres":
        return require_database_url()

    async def ping() -> None:
        pass

    @asynccontextmanager
    async def memory_database(url: str) -> AsyncIterator[SimpleNamespace]:
        yield SimpleNamespace(saver=InMemorySaver(), ping=ping)

    monkeypatch.setattr("agent.api.open_database", memory_database)
    return "memory"


@asynccontextmanager
async def serve(
    database_url: str, script: Script | None = None, kb: KbClient | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    model = scripted(script or Script())
    app = create_app(
        Settings(
            database_url=database_url,
            agent_service_key=SecretStr("agent-service-key-for-tests"),
            kb_service_key=SecretStr("kb-key"),
        ),
        models=Models(model, model),
        kb=kb or FakeKb(),
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agent.test") as c:
            yield c


@pytest.fixture
async def client(database_url: str) -> AsyncIterator[httpx.AsyncClient]:
    async with serve(database_url) as c:
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


async def test_a_run_that_failed_leaves_nothing_to_answer(database_url: str) -> None:
    thread = unique_thread()
    async with serve(database_url, kb=FailingKb(KbUnavailable("down"))) as client:
        failed = await client.post(
            "/run", headers=KEY, json={"thread_id": thread, "text": QUESTION}
        )
        skipped = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})

    assert [name for name, _ in events(failed)] == ["step", "error", "done"]
    assert skipped.status_code == 409


@pytest.mark.parametrize(
    ("error", "params"),
    [(KbUnavailable("down"), {"reason": "kb_unavailable"}), (RuntimeError("boom"), {})],
)
async def test_a_failure_ends_the_stream_with_an_error_event_and_done(
    database_url: str, error: Exception, params: dict[str, str]
) -> None:
    async with serve(database_url, kb=FailingKb(error)) as client:
        response = await client.post(
            "/run", headers=KEY, json={"thread_id": unique_thread(), "text": QUESTION}
        )

    *_, (name, body), (last, done) = events(response)
    assert (name, body["code"], body["params"]) == ("error", ErrorCode.internal_error, params)
    assert last == "done" and len(done["trace_id"]) == 32


async def test_a_turn_with_no_verified_row_ends_with_its_own_error_code(
    database_url: str,
) -> None:
    script = Script(holding={"rows": [row("statute:4857:m18", "Kanunda hiç yazmayan ifade")]})
    thread = unique_thread()
    async with serve(database_url, script) as client:
        await client.post("/run", headers=KEY, json={"thread_id": thread, "text": QUESTION})
        response = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})

    names = [name for name, _ in events(response)]
    assert names[-2:] == ["error", "done"] and "answer" not in names
    assert events(response)[-2][1]["code"] == ErrorCode.answer_not_verified


async def test_a_request_must_carry_one_of_text_answers_or_skip(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/run", headers=KEY, json={"thread_id": "t"})

    assert response.status_code == 422


async def test_health_and_readiness(client: httpx.AsyncClient) -> None:
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json() == {"status": "ok"}


async def test_model_failure_after_clarification_has_error_done_and_cannot_resume(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.llm import Llm

    original = Llm.run

    async def fail_holding(
        self: Llm, tier: Any, output_type: Any, instructions: str, prompt: str
    ) -> Any:
        if output_type.__name__ == "HoldingDraft":
            raise RuntimeError("model unavailable")
        return await original(self, tier, output_type, instructions, prompt)

    monkeypatch.setattr(Llm, "run", fail_holding)
    thread = unique_thread()
    async with serve(database_url) as client:
        await client.post("/run", headers=KEY, json={"thread_id": thread, "text": QUESTION})
        response = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})
        retry = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})
    assert [n for n, _ in events(response)][-2:] == ["error", "done"]
    assert events(response)[-2][1]["code"] == ErrorCode.internal_error
    assert len(events(response)[-1][1]["trace_id"]) == 32
    assert retry.status_code == 409


async def test_provider_exception_payload_is_not_logged(
    database_url: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import logging

    from agent.logging_setup import JsonFormatter

    monkeypatch.setattr("agent.api.configure_logging", lambda level: None)
    caplog.set_level(logging.INFO)
    private = "PRIVATE_QUESTION_SENTINEL"
    async with serve(database_url, kb=FailingKb(RuntimeError(private))) as client:
        response = await client.post(
            "/run", headers=KEY, json={"thread_id": unique_thread(), "text": private}
        )
    assert events(response)[-2][1]["code"] == ErrorCode.internal_error
    assert private not in "\n".join(JsonFormatter().format(r) for r in caplog.records)


@pytest.mark.parametrize("error", [KbUnavailable("down"), RuntimeError("down")])
async def test_retrieve_failure_after_resume_cannot_be_resumed_again(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    kb = FakeKb()
    thread = unique_thread()
    async with serve(database_url, kb=kb) as client:
        first = await client.post("/run", headers=KEY, json={"thread_id": thread, "text": QUESTION})
        assert events(first)[-2][0] == "clarification"
        monkeypatch.setattr(kb, "search", FailingKb(error).search)
        failed = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})
        retry = await client.post("/run", headers=KEY, json={"thread_id": thread, "skip": True})
    kinds = [name for name, _ in events(failed)]
    assert kinds[-2:] == ["error", "done"] and "answer" not in kinds
    assert any(body.get("node") == "retrieve" for _, body in events(failed))
    assert events(failed)[-2][1]["code"] == ErrorCode.internal_error
    assert events(failed)[-2][1]["params"] == (
        {"reason": "kb_unavailable"} if isinstance(error, KbUnavailable) else {}
    )
    assert len(events(failed)[-1][1]["trace_id"]) == 32
    assert retry.status_code == 409
