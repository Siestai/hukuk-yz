"""Database chat API and validated agent SSE bridge (task 18)."""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

import anyio
import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import CurrentUser, Db, require_role
from app.chat import EVENT_STREAM, EventStreamResponse, _now, _sse
from app.errors import ApiError
from app.models.chat import ChatConversation, ChatFeedback, ChatTurn
from app.models.user import AppUser, UserRole
from app.settings import Settings, get_settings
from hukuk_models import ErrorCode
from hukuk_models.chat import (
    ChatEvent,
    Conversation,
    ConversationDetail,
    ConversationList,
    DoneEvent,
    ErrorEvent,
    Feedback,
    FeedbackExport,
    FeedbackIn,
    MessageRequest,
    RunUsage,
    Turn,
)

router = APIRouter(prefix="/chat", tags=["chat"])


async def pinned_db(request: Request) -> AsyncIterator[AsyncSession]:
    # A bounded, separate connection budget keeps stream locks out of the KB/auth pool.
    # NullPool makes every lock connection disposable, including cancellation cleanup.
    if not hasattr(request.app.state, "chat_connections"):
        request.app.state.chat_connections = asyncio.Semaphore(4)
    slots = request.app.state.chat_connections
    if slots.locked():
        raise ApiError(503, ErrorCode.chat_unavailable)
    await slots.acquire()
    engine = create_async_engine(
        request.app.state.engine.url.render_as_string(hide_password=False), poolclass=NullPool
    )
    try:
        async with engine.connect() as connection:
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                try:
                    yield session
                finally:
                    with anyio.CancelScope(shield=True):
                        await session.rollback()
                        await connection.execute(text("SELECT pg_advisory_unlock_all()"))
                        await connection.commit()
    finally:
        with anyio.CancelScope(shield=True):
            await engine.dispose()
        slots.release()


PinnedDb = Annotated[AsyncSession, Depends(pinned_db)]
Config = Annotated[Settings, Depends(get_settings)]


def record(row: ChatConversation) -> Conversation:
    return Conversation(
        id=row.id,
        durable_delivery=True,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def owned(db: AsyncSession, id: uuid.UUID, user: AppUser) -> ChatConversation:
    row = await db.get(ChatConversation, id)
    if row is None or (row.user_id != user.id and user.role != UserRole.admin):
        raise ApiError(404, ErrorCode.not_found)
    return row


@router.post("/conversations", status_code=201)
async def create_conversation(user: CurrentUser, db: Db, settings: Config) -> Conversation:
    if settings.chat_backend != "agent":
        raise ApiError(503, ErrorCode.chat_unavailable)
    now = _now()
    row = ChatConversation(user_id=user.id, title="", created_at=now, updated_at=now)
    db.add(row)
    await db.commit()
    return record(row)


@router.get("/conversations")
async def list_conversations(user: CurrentUser, db: Db) -> ConversationList:
    query = select(ChatConversation).order_by(ChatConversation.updated_at.desc())
    if user.role != UserRole.admin:
        query = query.where(ChatConversation.user_id == user.id)
    return ConversationList(items=[record(r) for r in (await db.scalars(query)).all()])


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: Db
) -> ConversationDetail:
    row = await owned(db, conversation_id, user)
    turns = await db.scalars(
        select(ChatTurn)
        .where(ChatTurn.conversation_id == row.id)
        .order_by(ChatTurn.created_at, ChatTurn.id)
    )
    delivery = row.delivery
    completed = bool(delivery and delivery["status"] == "completed")
    terminal_error = None
    if delivery and completed:
        terminal_error = next(
            (
                ErrorEvent.model_validate(e)
                for e in reversed(delivery.get("events", []))
                if e["type"] == "error"
            ),
            None,
        )
    return ConversationDetail(
        **record(row).model_dump(),
        turns=[Turn.model_validate(t.payload) for t in turns],
        pending_request=delivery["body"] if delivery and not completed else None,
        terminal_error=terminal_error,
    )


def save_turn(
    db: Any,
    conversation_id: uuid.UUID,
    turn: Turn,
    mode: str,
    latency_ms: int | None = None,
    usage: RunUsage | None = None,
) -> None:
    db.add(
        ChatTurn(
            id=turn.id,
            conversation_id=conversation_id,
            role=turn.role,
            payload=turn.model_dump(mode="json"),
            mode=mode,
            trace_id=turn.trace_id,
            model=", ".join(usage.models) if usage else None,
            tokens={"input": usage.input_tokens, "output": usage.output_tokens} if usage else None,
            cost=usage.cost if usage else None,
            latency_ms=latency_ms,
            created_at=turn.created_at,
        )
    )


async def bridge(
    db: Any, conv: ChatConversation, body: MessageRequest, settings: Settings
) -> AsyncIterator[bytes]:
    conversation_id = conv.id
    started = time.monotonic()
    fields: dict[str, Any] = {}
    failed = False
    events: list[dict[str, Any]] = []
    done = False
    try:
        assert settings.agent_service_key is not None
        async with httpx.AsyncClient(timeout=settings.agent_timeout_seconds) as client:
            async with client.stream(
                "POST",
                settings.agent_base_url + "/run",
                headers={"X-Service-Key": settings.agent_service_key.get_secret_value()},
                json={**body.model_dump(mode="json"), "thread_id": str(conv.id)},
            ) as response:
                response.raise_for_status()
                data: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data.append(line[5:].lstrip())
                    elif line == "" and data:
                        event = ChatEvent.model_validate_json("\n".join(data)).root
                        data.clear()
                        if event.type == "error":
                            failed = True
                        elif event.type in ("facts", "answer", "clarification"):
                            fields[event.type] = getattr(event, event.type)
                        elif event.type == "done":
                            if not failed and ("answer" in fields or "clarification" in fields):
                                turn = Turn(
                                    id=uuid.uuid4(),
                                    role="assistant",
                                    created_at=_now(),
                                    trace_id=event.trace_id,
                                    **fields,
                                )
                                save_turn(
                                    db,
                                    conv.id,
                                    turn,
                                    body.mode,
                                    int((time.monotonic() - started) * 1000),
                                    usage=event.usage,
                                )
                                if turn.facts:
                                    conv.title = turn.facts.title
                                conv.updated_at = turn.created_at
                                event = DoneEvent(
                                    turn_id=turn.id, trace_id=event.trace_id, usage=event.usage
                                )
                            elif not failed:
                                raise ValueError("agent ended without a result")
                            else:
                                event = DoneEvent(trace_id=event.trace_id, usage=event.usage)
                            events.append(ChatEvent(event).model_dump(mode="json"))
                            conv.delivery = {
                                **(conv.delivery or {}),
                                "status": "completed",
                                "events": events,
                            }
                            await db.commit()
                            done = True
                            yield _sse(event)
                            return
                        events.append(ChatEvent(event).model_dump(mode="json"))
                        yield _sse(event)
        if not done:
            raise ValueError("agent stream ended without done")
    except Exception as exc:
        logging.getLogger("app").error("chat delivery failed: %s", type(exc).__name__)
        await db.rollback()
        yield _sse(ErrorEvent(code=ErrorCode.chat_unavailable))
        yield _sse(DoneEvent())
    finally:
        # Session advisory lock spans commits and streaming, preventing overlapping graph resumes.
        await db.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:key, 18))"),
            {"key": str(conversation_id)},
        )
        await db.commit()


class DeliveryResponse(EventStreamResponse):
    """Own delivery until completion, before FastAPI closes its DB dependency."""

    def __init__(self, db: Any, conv: ChatConversation, body: MessageRequest, settings: Settings):
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.delivery = (db, conv, body, settings)
        super().__init__(
            self.events(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    async def events(self) -> AsyncIterator[bytes]:
        while (event := await self.queue.get()) is not None:
            yield event

    async def produce(self) -> None:
        with anyio.CancelScope(shield=True):
            try:
                async for event in bridge(*self.delivery):
                    self.queue.put_nowait(event)
            finally:
                self.queue.put_nowait(None)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        async with anyio.create_task_group() as group:
            group.start_soon(self.produce)
            await super().__call__(scope, receive, send)


async def replay_events(events: list[dict[str, Any]]) -> AsyncIterator[bytes]:
    for event in events:
        yield _sse(ChatEvent.model_validate(event).root)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=EventStreamResponse,
    responses=EVENT_STREAM,
)
async def post_message(
    conversation_id: uuid.UUID,
    body: MessageRequest,
    user: CurrentUser,
    db: PinnedDb,
    settings: Config,
) -> EventStreamResponse:
    conv = await owned(db, conversation_id, user)
    if settings.chat_backend != "agent" or settings.agent_service_key is None:
        raise ApiError(503, ErrorCode.chat_unavailable)
    # Pin the connection while the session-level lock is held (commits must not return it to pool).
    connection = await db.connection()
    locked = await connection.scalar(
        text("SELECT pg_try_advisory_lock(hashtextextended(:key, 18))"),
        {"key": str(conversation_id)},
    )
    if not locked:
        raise ApiError(409, ErrorCode.clarification_not_pending)
    try:
        delivery = conv.delivery
        # An explicit delivery id can only replay the identical request, never a new input.
        if delivery and (
            str(body.request_id) == delivery["body"]["request_id"]
            or (
                body.request_id is None
                and delivery["status"] != "completed"
                and body.model_dump(mode="json", exclude={"request_id"})
                == {k: v for k, v in delivery["body"].items() if k != "request_id"}
            )
        ):
            saved = MessageRequest.model_validate(delivery["body"])
            if body.model_dump(exclude={"request_id"}) != saved.model_dump(exclude={"request_id"}):
                raise ApiError(409, ErrorCode.clarification_not_pending)
            if delivery["status"] == "completed":
                return EventStreamResponse(replay_events(delivery["events"]))
            return DeliveryResponse(db, conv, saved, settings)
        if body.request_id is not None and await db.get(ChatTurn, body.request_id) is not None:
            # An older consumed delivery cannot become the input of a newer interrupt.
            raise ApiError(409, ErrorCode.clarification_not_pending)
        if delivery and delivery["status"] != "completed" and body.text is None:
            raise ApiError(409, ErrorCode.clarification_not_pending)
        if body.text is None:
            last = await db.scalar(
                select(ChatTurn)
                .where(ChatTurn.conversation_id == conv.id)
                .order_by(ChatTurn.created_at.desc())
                .limit(1)
            )
            pending = Turn.model_validate(last.payload).clarification if last else None
            if pending is None:
                raise ApiError(409, ErrorCode.clarification_not_pending)
            if {a.question_id for a in body.clarification_answers or []} - {
                q.id for q in pending.questions
            }:
                raise ApiError(422, ErrorCode.validation_error)
        # Serialize quota reservations across every conversation of this user, in PostgreSQL.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 19))"),
            {"key": str(conv.user_id)},
        )
        if body.text is not None:
            count = await db.scalar(
                select(func.count())
                .select_from(ChatTurn)
                .join(ChatConversation)
                .where(
                    ChatConversation.user_id == conv.user_id,
                    ChatTurn.role == "user",
                    ChatTurn.payload["text"].astext.is_not(None),
                    ChatTurn.created_at
                    >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0),
                )
            )
            if (count or 0) >= settings.chat_daily_limit:
                raise ApiError(429, ErrorCode.chat_daily_limit)
        body = body.model_copy(update={"request_id": body.request_id or uuid.uuid4()})
        conv.delivery = {"body": body.model_dump(mode="json"), "status": "pending"}
        turn = Turn(
            id=body.request_id,
            role="user",
            created_at=_now(),
            text=body.text,
            clarification_answers=body.clarification_answers,
            skipped=body.skip,
        )
        save_turn(db, conv.id, turn, body.mode)
        conv.updated_at = turn.created_at
        await db.commit()
    except BaseException:
        await db.rollback()
        await db.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:key, 18))"),
            {"key": str(conversation_id)},
        )
        await db.commit()
        raise
    return DeliveryResponse(db, conv, body, settings)


@router.post("/turns/{turn_id}/feedback", status_code=201)
async def post_feedback(
    turn_id: uuid.UUID, body: FeedbackIn, user: CurrentUser, db: Db
) -> Feedback:
    row = await db.get(ChatTurn, turn_id)
    if row is None or row.role != "assistant":
        raise ApiError(404, ErrorCode.not_found)
    await owned(db, row.conversation_id, user)
    turn = Turn.model_validate(row.payload)
    if body.point_index is not None and (
        turn.answer is None or body.point_index >= len(turn.answer.points)
    ):
        raise ApiError(422, ErrorCode.validation_error)
    feedback = ChatFeedback(
        id=uuid.uuid4(), user_id=user.id, turn_id=turn_id, created_at=_now(), **body.model_dump()
    )
    db.add(feedback)
    await db.commit()
    return Feedback(
        id=feedback.id, turn_id=turn_id, created_at=feedback.created_at, **body.model_dump()
    )


@router.get("/feedback", dependencies=[Depends(require_role("admin"))])
async def export_feedback(db: Db, since: datetime | None = None) -> list[FeedbackExport]:
    query = select(ChatFeedback).order_by(ChatFeedback.created_at, ChatFeedback.id)
    if since is not None:
        since = since.replace(tzinfo=UTC) if since.tzinfo is None else since
        query = query.where(ChatFeedback.created_at >= since)
    return [
        FeedbackExport.model_validate(r, from_attributes=True)
        for r in (await db.scalars(query)).all()
    ]
