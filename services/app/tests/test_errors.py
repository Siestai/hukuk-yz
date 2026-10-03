"""The common error body (task 10a): codes only, the same shape for every failure."""

from typing import Self

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, model_validator

from app.errors import ApiError, install
from app.main import app
from hukuk_models import ErrorCode


class Payload(BaseModel):
    name: str
    nested: dict[str, int]


class Whole(BaseModel):
    @model_validator(mode="after")
    def refuse(self) -> Self:
        raise ValueError("no")


def _probe() -> FastAPI:
    probe = FastAPI()
    install(probe)

    @probe.post("/payload")
    async def payload(body: Payload) -> None: ...

    @probe.post("/whole-body")
    async def whole_body(body: Whole) -> None: ...

    @probe.get("/limited")
    async def limited() -> None:
        raise ApiError(429, ErrorCode.too_many_attempts, {"retry_after": 7}, {"Retry-After": "7"})

    return probe


async def _call(target: FastAPI, method: str, url: str, **kwargs: object) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=target), base_url="http://test"
    ) as client:
        return await client.request(method, url, **kwargs)  # type: ignore[arg-type]


async def test_an_api_error_has_status_code_params_and_headers() -> None:
    response = await _call(_probe(), "GET", "/limited")
    assert response.status_code == 429
    assert response.json() == {"error": {"code": "too_many_attempts", "params": {"retry_after": 7}}}
    assert response.headers["retry-after"] == "7"


async def test_a_validation_failure_lists_the_fields_without_prose() -> None:
    response = await _call(_probe(), "POST", "/payload", json={"nested": {"a": "x"}})
    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "params": {"fields": ["name", "nested.a"]}}
    }


async def test_a_rule_over_the_whole_body_names_no_field() -> None:
    response = await _call(_probe(), "POST", "/whole-body", json={})
    assert response.json() == {"error": {"code": "validation_error", "params": {"fields": []}}}


async def test_unknown_routes_and_methods_use_the_same_body() -> None:
    missing = await _call(app, "GET", "/no-such-route")
    assert (missing.status_code, missing.json()) == (
        404,
        {"error": {"code": "not_found", "params": {}}},
    )
    wrong_method = await _call(app, "POST", "/healthz")
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error"]["code"] == "method_not_allowed"


def test_openapi_carries_the_error_code_enum_and_body_schema() -> None:
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    ref = "#/components/schemas/"
    assert schemas["ErrorCode"]["enum"] == [code.value for code in ErrorCode]
    assert schemas["ErrorResponse"]["properties"]["error"] == {"$ref": ref + "ErrorBody"}
    assert schemas["ErrorBody"]["properties"]["code"] == {"$ref": ref + "ErrorCode"}
    responses = spec["paths"]["/auth/login"]["post"]["responses"]
    assert responses["429"]["content"]["application/json"]["schema"] == {
        "$ref": ref + "ErrorResponse"
    }
