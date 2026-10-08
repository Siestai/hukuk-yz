import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from sqlalchemy import text

from app.auth import router as auth_router
from app.db import make_engine
from app.errors import ERROR_RESPONSES
from app.errors import install as install_error_handlers
from app.logging_setup import configure_logging, request_id_var
from app.review import router as review_router
from app.settings import get_settings
from app.statutes import router as statutes_router
from hukuk_models import HealthResponse

logger = logging.getLogger("app")

READYZ_TIMEOUT_SECONDS = 3


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.engine = make_engine(settings.database_url)
    logger.info("app started (env=%s)", settings.env)
    # uvicorn reads this variable itself; here it is only checked.
    if settings.env != "dev" and not os.environ.get("FORWARDED_ALLOW_IPS", "").strip():
        logger.warning(
            "FORWARDED_ALLOW_IPS is empty: the per-IP login limit sees only the proxy address"
        )
    yield
    await app.state.engine.dispose()


app = FastAPI(title="hukuk-agent", lifespan=lifespan, responses=ERROR_RESPONSES)
install_error_handlers(app)
app.include_router(auth_router)
app.include_router(review_router)
app.include_router(statutes_router)


@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/healthz")
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/readyz")
async def readyz(request: Request, response: Response) -> HealthResponse:
    try:
        async with asyncio.timeout(READYZ_TIMEOUT_SECONDS):
            async with request.app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness check failed: %r", exc)
        response.status_code = 503
        return HealthResponse(status="unavailable")
    return HealthResponse(status="ok")
