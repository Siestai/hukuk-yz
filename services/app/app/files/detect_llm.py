"""The Anthropic Messages API as a `Detector` (task 13a), over plain HTTP.

Only the excerpt of the text and the file name leave the server, never the file. The answer is
read from a forced tool call, so it is JSON of the schema `answer_schema` asks for; whatever it
holds is checked against the text by `hukuk_ingest.classify.llm.validate`. The call is
synchronous: the worker runs it in a thread."""

import logging
from typing import Any

import httpx

from app.settings import Settings
from hukuk_ingest.classify.llm import (
    SYSTEM_PROMPT,
    Detector,
    DetectorError,
    DetectRequest,
    DetectResult,
    answer_schema,
    user_prompt,
)

logger = logging.getLogger("app.files.detect_llm")

API_VERSION = "2023-06-01"
TOOL_NAME = "report_fields"
MAX_OUTPUT_TOKENS = 600


class AnthropicDetector:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
        )

    def detect(self, request: DetectRequest) -> DetectResult:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt(request)}],
            "tools": [
                {
                    "name": TOOL_NAME,
                    "description": "Report the fields read from the document.",
                    "input_schema": answer_schema(request.fields),
                }
            ],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
        }
        try:
            response = self._client.post("/v1/messages", json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise DetectorError(f"HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise DetectorError(type(exc).__name__) from None
        answer = next(
            (
                block.get("input")
                for block in payload.get("content", [])
                if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME
            ),
            None,
        )
        if not isinstance(answer, dict):
            raise DetectorError("no tool call in the answer")
        usage = payload.get("usage", {})
        return DetectResult(
            answer,
            str(payload.get("model", self.model)),
            int(usage.get("input_tokens", 0)),
            int(usage.get("output_tokens", 0)),
        )


def make_detector(settings: Settings) -> Detector | None:
    """The configured detector, or None (provider `none`, or no key): the step is skipped."""
    if settings.file_detect_llm_provider != "anthropic":
        return None
    if settings.file_detect_llm_api_key is None:
        logger.warning("FILE_DETECT_LLM_PROVIDER is anthropic but no key is set: LLM step off")
        return None
    return AnthropicDetector(
        settings.file_detect_llm_api_key.get_secret_value(),
        settings.file_detect_llm_model,
        settings.file_detect_llm_base_url,
        settings.file_detect_llm_timeout_seconds,
    )
