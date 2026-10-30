"""`POST /run` (called by `app` only, with the service key) streams the `ChatEvent`s of one turn
of a thread as server-sent events; `/healthz` and `/readyz` for the orchestrator."""

import asyncio
import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import SecretStr

from agent.db import open_database
from agent.graph import build_graph
from agent.kb import HttpKbClient, KbClient, KbUnavailable
from agent.llm import Llm, Models
from agent.logging_setup import configure_logging
from agent.nodes import Deps, State
from agent.settings import Settings
from agent.trace import Trace, Tracing
from hukuk_models import ErrorBody, ErrorCode, ErrorResponse, HealthResponse
from hukuk_models.chat import (
    AnswerEvent,
    ChatEvent,
    Clarification,
    ClarificationEvent,
    DoneEvent,
    ErrorEvent,
    MessageRequest,
)

logger = logging.getLogger("agent")

READYZ_TIMEOUT_SECONDS = 3
Graph = CompiledStateGraph[State, None, State, State]


class _Unauthorized(Exception):
    pass


class RunRequest(MessageRequest):
    """A turn of the conversation `thread_id` (the app's turn chain). `text` is the question;
    `mode` is only the presentation the user has open and does not change the run."""

    thread_id: str


def sse(event: Any) -> bytes:
    data = ChatEvent(event).model_dump_json()
    return f"event: {event.type}\ndata: {data}\n\n".encode()


def _error(status: int, code: ErrorCode) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code))
    return JSONResponse(body.model_dump(mode="json"), status_code=status)


async def turn_events(graph: Graph, request: RunRequest, trace: Trace) -> AsyncIterator[Any]:
    """The events of one turn. An answer or a clarification ends the turn; `done` always does."""
    config: Any = {"configurable": {"thread_id": request.thread_id}}
    graph_input: Command[Any] | dict[str, Any]
    if request.text is not None:
        graph_input = {"question": request.text}
    else:
        answers = [a.model_dump(mode="json") for a in request.clarification_answers or []]
        graph_input = Command(resume={"answers": answers, "skip": request.skip})
    fields = {"trace_id": trace.trace_id, "thread_id": request.thread_id}
    try:
        stream: AsyncIterator[Any] = graph.astream(
            graph_input,  # type: ignore[arg-type]
            config,
            stream_mode=["custom", "updates"],
        )
        async for mode, chunk in stream:
            if mode == "custom":
                yield ChatEvent.model_validate(chunk).root
            elif "__interrupt__" in chunk:
                yield ClarificationEvent(
                    clarification=Clarification.model_validate(chunk["__interrupt__"][0].value)
                )
            elif "draft" in chunk:
                answer = chunk["draft"]["answer"]
                if answer is None:
                    yield ErrorEvent(code=ErrorCode.answer_not_verified)
                else:
                    yield AnswerEvent.model_validate({"answer": answer})
    except KbUnavailable:
        logger.error("knowledge base unavailable", extra={"fields": fields})
        yield ErrorEvent(code=ErrorCode.internal_error, params={"reason": "kb_unavailable"})
    except Exception as exc:
        # Provider exceptions may embed prompts or personal data. Log only their type.
        logger.error("run failed: %s", type(exc).__name__, extra={"fields": fields})
        yield ErrorEvent(code=ErrorCode.internal_error)
    logger.info(
        "run done",
        extra={
            "fields": {
                **fields,
                "input_tokens": trace.input_tokens,
                "output_tokens": trace.output_tokens,
                "cost": trace.cost,
                "seconds": round(trace.seconds, 3),
            }
        },
    )
    yield DoneEvent(trace_id=trace.trace_id)


async def run_events(graph: Graph, tracing: Tracing, request: RunRequest) -> AsyncIterator[Any]:
    with tracing.run(request.thread_id) as trace:
        async for event in turn_events(graph, request, trace):
            yield event


def create_app(
    settings: Settings,
    *,
    models: Models | None = None,
    kb: KbClient | None = None,
) -> FastAPI:
    """The app. A test passes fake models and a fake KB client; `main.py` leaves them out and the
    lifespan builds the real ones from `settings`."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        configure_logging(settings.log_level)
        tracing = Tracing.from_settings(settings)
        client = kb or HttpKbClient(
            settings.app_base_url, settings.kb_service_key, settings.kb_timeout_seconds
        )
        llm = Llm(models or Models(settings.agent_model_fast, settings.agent_model_strong))
        async with open_database(settings.database_url) as db:
            app.state.db = db
            app.state.tracing = tracing
            app.state.graph = build_graph(Deps(llm=llm, kb=client), app.state.db.saver)
            logger.info("agent started")
            yield
        if isinstance(client, HttpKbClient):
            await client.aclose()
        tracing.shutdown()

    app = FastAPI(title="hukuk-agent agent", lifespan=lifespan)
    key: SecretStr = settings.agent_service_key

    async def require_service_key(x_service_key: Annotated[str | None, Header()] = None) -> None:
        if x_service_key is None or not hmac.compare_digest(
            x_service_key.encode(), key.get_secret_value().encode()
        ):
            raise _Unauthorized

    @app.exception_handler(_Unauthorized)
    async def unauthorized(request: Request, exc: Exception) -> JSONResponse:
        return _error(401, ErrorCode.unauthorized)

    @app.post("/run", dependencies=[Depends(require_service_key)], response_model=None)
    async def run(body: RunRequest, request: Request) -> StreamingResponse | JSONResponse:
        graph: Graph = request.app.state.graph
        if body.text is None:
            snapshot = await graph.aget_state({"configurable": {"thread_id": body.thread_id}})
            if not any(task.interrupts for task in snapshot.tasks):
                return _error(409, ErrorCode.clarification_not_pending)
        stream = (sse(e) async for e in run_events(graph, request.app.state.tracing, body))
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(stream, media_type="text/event-stream", headers=headers)

    @app.get("/healthz")
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/readyz")
    async def readyz(request: Request, response: Response) -> HealthResponse:
        try:
            async with asyncio.timeout(READYZ_TIMEOUT_SECONDS):
                await request.app.state.db.ping()
        except Exception as exc:
            logger.warning("readiness check failed: %r", exc)
            response.status_code = 503
            return HealthResponse(status="unavailable")
        return HealthResponse(status="ok")

    return app
