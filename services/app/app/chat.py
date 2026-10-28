"""Chat API (task 15): the contract of `hukuk_models.chat`, answered from hand-made cases.

`CHAT_BACKEND=fixture` plays the scenarios of `eval/fixtures` (question -> understood case ->
clarification -> answer); the state is in memory and goes with the process. `none` (the default)
answers 503. The real agent and the persistent tables come in tasks 17 and 18.

Every role may use `/chat/*`; a conversation belongs to the user who made it (another user's
conversation is a 404).

Errors: before the stream starts (unknown conversation, no fixture, nothing pending, bad answers)
the response is an HTTP error with the JSON body of `app/errors.py`. Once the stream has started
the status is 200 and a failure is an `error` event followed by `done` (without a turn id).
(OpenAPI lists the error bodies under `text/event-stream` too: FastAPI gives every response of a
route the route's media type. They are JSON on the wire.)
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth import CurrentUser
from app.errors import ApiError
from app.settings import Settings, get_settings
from hukuk_models import ErrorCode
from hukuk_models.chat import (
    Answer,
    AnswerEvent,
    CaseFacts,
    ChatEvent,
    Clarification,
    ClarificationEvent,
    Conversation,
    ConversationDetail,
    ConversationList,
    DoneEvent,
    ErrorEvent,
    FactsEvent,
    Feedback,
    FeedbackIn,
    MessageRequest,
    StepEvent,
    Turn,
)

logger = logging.getLogger("app")
router = APIRouter(prefix="/chat", tags=["chat"])

DEFAULT_FIXTURES = Path(__file__).parents[3] / "eval" / "fixtures"


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


EVENT_STREAM: dict[int | str, dict[str, Any]] = {
    200: {"model": ChatEvent, "description": "A stream of ChatEvent"}
}


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class Scenario:
    case_id: str
    questions: tuple[str, ...]
    facts: CaseFacts
    clarification: Clarification
    facts_complete: CaseFacts
    on_skip: Answer
    on_complete: Answer


def load_scenarios(directory: Path) -> list[Scenario]:
    def answer(name: str) -> Answer:
        return Answer.model_validate_json((directory / name).read_text(encoding="utf-8"))

    paths = sorted(directory.glob("*.scenario.json"))
    if not paths:
        raise RuntimeError(f"no chat fixtures (*.scenario.json) in {directory}")
    scenarios = []
    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        scenarios.append(
            Scenario(
                case_id=raw["case_id"],
                questions=tuple(_key(q) for q in raw["questions"]),
                facts=CaseFacts.model_validate(raw["facts"]),
                clarification=Clarification.model_validate(raw["clarification"]),
                facts_complete=CaseFacts.model_validate(raw["facts_complete"]),
                on_skip=answer(raw["on_skip"]),
                on_complete=answer(raw["on_complete"]),
            )
        )
    return scenarios


@dataclass
class _Conversation:
    owner: uuid.UUID
    record: Conversation
    turns: list[Turn] = field(default_factory=list)
    scenario: Scenario | None = None


class ChatStore:
    """The conversations and feedback of one process (the fixture backend has no database)."""

    def __init__(self, scenarios: list[Scenario]) -> None:
        self.scenarios = scenarios
        self.conversations: dict[uuid.UUID, _Conversation] = {}
        self.feedback: list[Feedback] = []

    def find_scenario(self, text: str) -> Scenario | None:
        wanted = _key(text)
        return next((s for s in self.scenarios if wanted in s.questions), None)

    def get(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> _Conversation:
        found = self.conversations.get(conversation_id)
        if found is None or found.owner != user_id:
            raise ApiError(404, ErrorCode.not_found)
        return found


def open_store(settings: Settings) -> ChatStore | None:
    """The store of the configured backend, loaded at startup so that a missing fixture folder
    stops the app instead of answering every question with `chat_no_fixture`."""
    if settings.chat_backend != "fixture":
        return None
    return ChatStore(load_scenarios(settings.chat_fixtures_dir or DEFAULT_FIXTURES))


def get_store(request: Request) -> ChatStore:
    store: ChatStore | None = request.app.state.chat_store
    if store is None:
        raise ApiError(503, ErrorCode.chat_unavailable)
    return store


Store = Annotated[ChatStore, Depends(get_store)]


def _now() -> datetime:
    return datetime.now(UTC)


def _detail(conv: _Conversation) -> ConversationDetail:
    return ConversationDetail(**conv.record.model_dump(), turns=conv.turns)


@router.post("/conversations", status_code=201)
async def create_conversation(user: CurrentUser, store: Store) -> Conversation:
    now = _now()
    record = Conversation(id=uuid.uuid4(), title="", created_at=now, updated_at=now)
    store.conversations[record.id] = _Conversation(owner=user.id, record=record)
    return record


@router.get("/conversations")
async def list_conversations(user: CurrentUser, store: Store) -> ConversationList:
    mine = [c.record for c in store.conversations.values() if c.owner == user.id]
    return ConversationList(items=sorted(mine, key=lambda c: c.updated_at, reverse=True))


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, store: Store
) -> ConversationDetail:
    return _detail(store.get(conversation_id, user.id))


def _sse(event: Any) -> bytes:
    chat_event = ChatEvent(event)
    data = chat_event.model_dump_json(exclude_none=False)
    return f"event: {event.type}\ndata: {data}\n\n".encode()


def _add_turn(conv: _Conversation, **fields: Any) -> Turn:
    turn = Turn(id=uuid.uuid4(), created_at=_now(), **fields)
    conv.turns.append(turn)
    conv.record = conv.record.model_copy(update={"updated_at": turn.created_at})
    return turn


def _pending(conv: _Conversation) -> Clarification | None:
    last = conv.turns[-1] if conv.turns else None
    return last.clarification if last and last.role == "assistant" else None


async def _events(
    conv: _Conversation, body: MessageRequest, scenario: Scenario, delay: float
) -> AsyncIterator[bytes]:
    """The events of one assistant turn. The user turn is stored by the caller, before the
    stream starts, so that a dropped connection keeps what the user sent."""

    async def pause() -> None:
        if delay:
            await asyncio.sleep(delay)

    trace_id = uuid.uuid4().hex
    yield _sse(StepEvent(node="understand", label="Soru okunuyor"))
    await pause()
    if body.text is not None:
        facts, clarification, answer = scenario.facts, scenario.clarification, None
        yield _sse(FactsEvent(facts=facts))
        await pause()
        yield _sse(StepEvent(node="clarify", label="Eksik bilgiler belirleniyor"))
        await pause()
        yield _sse(ClarificationEvent(clarification=clarification))
        conv.record = conv.record.model_copy(update={"title": facts.title})
    else:
        completed = body.clarification_answers is not None and not any(
            a.unknown for a in body.clarification_answers
        )
        facts = scenario.facts_complete if completed else scenario.facts
        clarification, answer = None, scenario.on_complete if completed else scenario.on_skip
        yield _sse(FactsEvent(facts=facts))
        await pause()
        for node, label in (("retrieve", "Kaynaklar okunuyor"), ("compose", "Cevap hazırlanıyor")):
            yield _sse(StepEvent(node=node, label=label))
            await pause()
        yield _sse(AnswerEvent(answer=answer))
    turn = _add_turn(
        conv, role="assistant", facts=facts, clarification=clarification, answer=answer,
        trace_id=trace_id,
    )  # fmt: skip
    yield _sse(DoneEvent(turn_id=turn.id, trace_id=trace_id))


async def _play(
    conv: _Conversation, body: MessageRequest, scenario: Scenario, delay: float
) -> AsyncIterator[bytes]:
    try:
        async for chunk in _events(conv, body, scenario, delay):
            yield chunk
    except Exception:
        logger.exception("chat stream failed")
        yield _sse(ErrorEvent(code=ErrorCode.internal_error))
        yield _sse(DoneEvent())


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=EventStreamResponse,
    responses=EVENT_STREAM,
)
async def post_message(
    conversation_id: uuid.UUID,
    body: MessageRequest,
    user: CurrentUser,
    store: Store,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    conv = store.get(conversation_id, user.id)
    if body.text is not None:
        scenario = store.find_scenario(body.text)
        if scenario is None:
            raise ApiError(404, ErrorCode.chat_no_fixture)
        conv.scenario = scenario
        _add_turn(conv, role="user", text=body.text)
    else:
        pending = _pending(conv)
        if pending is None or conv.scenario is None:
            raise ApiError(409, ErrorCode.clarification_not_pending)
        known = {q.id for q in pending.questions}
        given = body.clarification_answers or []
        if {a.question_id for a in given} - known:
            raise ApiError(422, ErrorCode.validation_error, {"fields": ["clarification_answers"]})
        _add_turn(
            conv, role="user", clarification_answers=body.clarification_answers, skipped=body.skip
        )
    assert conv.scenario is not None
    stream = _play(conv, body, conv.scenario, settings.chat_fixture_step_delay_seconds)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return EventStreamResponse(stream, headers=headers)


@router.post("/turns/{turn_id}/feedback", status_code=201)
async def post_feedback(
    turn_id: uuid.UUID, body: FeedbackIn, user: CurrentUser, store: Store
) -> Feedback:
    turn = next(
        (
            t
            for c in store.conversations.values()
            if c.owner == user.id
            for t in c.turns
            if t.id == turn_id and t.role == "assistant"
        ),
        None,
    )
    if turn is None:
        raise ApiError(404, ErrorCode.not_found)
    if body.point_index is not None and (
        turn.answer is None or body.point_index >= len(turn.answer.points)
    ):
        raise ApiError(422, ErrorCode.validation_error, {"fields": ["point_index"]})
    feedback = Feedback(**body.model_dump(), id=uuid.uuid4(), turn_id=turn_id, created_at=_now())
    store.feedback.append(feedback)
    return feedback
