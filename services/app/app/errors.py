"""One error body for the whole API: `{"error": {"code": ..., "params": {...}}}` (task 10a).

The API returns codes, not prose; the UI translates them. Routes raise `ApiError`; the handlers
below also turn request-validation failures and the framework's own 404 / 405 into the same
body.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from hukuk_models import ErrorBody, ErrorCode, ErrorResponse

logger = logging.getLogger("app")

# Documented on every route so that the OpenAPI schema carries `ErrorResponse` and `ErrorCode`.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 405, 409, 415, 422, 429, 500)
}

_FRAMEWORK_CODES = {404: ErrorCode.not_found, 405: ErrorCode.method_not_allowed}


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: ErrorCode,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.params = params or {}
        self.headers = headers


def _response(
    status: int, code: ErrorCode, params: dict[str, Any], headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, params=params))
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return _response(exc.status, exc.code, exc.params, exc.headers)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # "body.edits.court" -> "edits.court": the part of the request is not the UI's concern. A
    # rule over the whole body (a model validator) has no field and adds none.
    # Numeric parts (list indexes, the byte offset of malformed JSON) are not field names.
    names = (
        [str(p) for p in e["loc"][1:] if not isinstance(p, int)]
        for e in exc.errors()
        if e["type"] != "json_invalid"
    )
    fields = sorted({".".join(parts) for parts in names if parts})
    return _response(422, ErrorCode.validation_error, {"fields": fields})


async def _framework_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    # No route raises HTTPException itself: these come from the framework (404, 405, ...).
    code = _FRAMEWORK_CODES.get(exc.status_code, ErrorCode.http_error)
    headers = dict(exc.headers) if exc.headers else None
    return _response(exc.status_code, code, {}, headers)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _response(500, ErrorCode.internal_error, {})


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _framework_error)
    app.add_exception_handler(Exception, _unhandled_error)
