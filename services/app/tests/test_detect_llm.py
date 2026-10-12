"""The Anthropic Messages API as a `Detector` (task 13a). The HTTP transport is a mock: no test
calls the network."""

import json
import logging
from typing import Any

import httpx
import pytest

from app.files.detect_llm import TOOL_NAME, AnthropicDetector, make_detector
from app.settings import Settings
from hukuk_ingest.classify import classify
from hukuk_ingest.classify.llm import DetectorError, DetectRequest

REQUEST = DetectRequest("belge.pdf", "Kanun Numarası : 4857", ("doc_type", "title"))


def detector(handler: Any) -> AnthropicDetector:
    return AnthropicDetector(
        "key-1", "claude-test", "https://llm.test", 5.0, httpx.MockTransport(handler)
    )


def test_the_request_names_the_tool_and_carries_only_the_excerpt_and_the_file_name() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-test-2",
                "content": [
                    {"type": "text", "text": "ok"},
                    {
                        "type": "tool_use",
                        "name": TOOL_NAME,
                        "input": {"doc_type": {"value": "kanun"}},
                    },
                ],
                "usage": {"input_tokens": 80, "output_tokens": 12},
            },
        )

    result = detector(handler).detect(REQUEST)
    assert seen["url"] == "https://llm.test/v1/messages"
    assert seen["headers"]["x-api-key"] == "key-1"
    assert seen["body"]["model"] == "claude-test"
    assert seen["body"]["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    prompt = seen["body"]["messages"][0]["content"]
    assert "belge.pdf" in prompt and "Kanun Numarası : 4857" in prompt
    assert set(seen["body"]["tools"][0]["input_schema"]["properties"]) == {"doc_type", "title"}
    assert (result.answer, result.model, result.input_tokens, result.output_tokens) == (
        {"doc_type": {"value": "kanun"}},
        "claude-test-2",
        80,
        12,
    )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": "quota"}),
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"content": [{"type": "text", "text": "no tool"}]}),
    ],
)
def test_a_failed_call_is_a_detector_error(response: httpx.Response) -> None:
    with pytest.raises(DetectorError):
        detector(lambda request: response).detect(REQUEST)


def _tool(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "content": [{"type": "tool_use", "name": TOOL_NAME, "input": {"title": {"value": "x"}}}],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    return {**body, **over}


@pytest.mark.parametrize(
    "body",
    [
        _tool(usage={"input_tokens": None, "output_tokens": 1}),
        _tool(usage={"input_tokens": "many", "output_tokens": 1}),
        _tool(usage={"input_tokens": 1}),
        _tool(usage=None),
        {"content": _tool()["content"]},
        _tool(content=["text"]),
        _tool(content=[{"name": TOOL_NAME}]),
        _tool(content=[{"type": "tool_use", "name": TOOL_NAME}]),
        _tool(content=[{"type": "tool_use", "name": TOOL_NAME, "input": "{}"}]),
        _tool(content="none"),
        ["not", "an", "object"],
    ],
)
def test_a_malformed_body_is_a_detector_error(body: Any) -> None:
    with pytest.raises(DetectorError):
        detector(lambda request: httpx.Response(200, json=body)).detect(REQUEST)


def test_the_text_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "Kanun Numarası : 4857 GİZLİ-METİN"
    fake = detector(lambda request: httpx.Response(200, json=_tool(usage={"input_tokens": "x"})))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(DetectorError):
            fake.detect(DetectRequest("belge.pdf", secret, ("title",)))
        classify(secret, "pdf", "belge.pdf", fake)
        ok = detector(lambda request: httpx.Response(200, json=_tool()))
        classify(secret, "pdf", "belge.pdf", ok)
    assert caplog.records
    assert "GİZLİ-METİN" not in caplog.text and "4857" not in caplog.text


def test_a_timeout_is_a_detector_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(DetectorError, match="ReadTimeout"):
        detector(handler).detect(REQUEST)


def test_without_a_provider_or_a_key_there_is_no_detector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("FILE_DETECT_LLM_PROVIDER", "FILE_DETECT_LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert make_detector(Settings(database_url="unused")) is None
    assert (
        make_detector(Settings(database_url="unused", file_detect_llm_provider="anthropic")) is None
    )
    assert (
        make_detector(Settings(database_url="unused", file_detect_llm_api_key="k")) is None
    )  # a key alone does not switch it on
    on = Settings(
        database_url="unused", file_detect_llm_provider="anthropic", file_detect_llm_api_key="k"
    )
    assert isinstance(make_detector(on), AnthropicDetector)
