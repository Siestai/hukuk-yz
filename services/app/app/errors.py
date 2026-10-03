"""One error body for the whole API: `{"error": {"code": ..., "params": {...}}}` (task 10a).

The API returns codes, not prose; the UI translates them. Routes raise `ApiError`; the handlers
below also turn request-validation failures and the framework's own 404 / 405 into the same
body.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from hukuk_models import ErrorBody, ErrorCode, ErrorResponse

# Documented on every route so that the OpenAPI schema carries `ErrorResponse` and `ErrorCode`.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 415, 422, 429)
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
    fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors() if e["loc"][1:]})
    return _response(422, ErrorCode.validation_error, {"fields": fields})


async def _framework_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    # Only 404 and 405 come from the framework: no route raises HTTPException itself.
    return _response(exc.status_code, _FRAMEWORK_CODES[exc.status_code], {})


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _framework_error)
