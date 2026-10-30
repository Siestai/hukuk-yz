"""The model calls: typed output, counted into the trace of the node."""

import pytest
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from agent.llm import Llm, Models, _cost
from agent.trace import current_trace


class Out(BaseModel):
    word: str


async def test_a_call_returns_the_typed_output_and_counts_its_tokens() -> None:
    fast, strong = (
        TestModel(custom_output_args={"word": "hızlı"}),
        TestModel(custom_output_args={"word": "güçlü"}),
    )
    llm = Llm(Models(fast, strong))

    async with current_trace().node("intake", {}) as record:
        quick = await llm.run("fast", Out, "talimat", "soru")
        deep = await llm.run("strong", Out, "talimat", "soru")

    assert (quick.word, deep.word) == ("hızlı", "güçlü")
    assert record.input_tokens > 0 and record.output_tokens > 0
    assert record.models == ["test:test"]
    assert record.cost is None


@pytest.mark.parametrize(
    ("model", "expected"),
    [("anthropic:claude-sonnet-5-5", 0.003), ("anthropic:claude-haiku-4-5-20251001", 0.0015)],
)
def test_the_cost_of_a_known_model_comes_from_its_price(model: str, expected: float) -> None:
    assert _cost(model, 1000, 100) == pytest.approx(expected)


def test_the_cost_of_an_unknown_model_is_unknown() -> None:
    assert _cost("test:test", 1000, 100) is None


@pytest.mark.parametrize(
    "instruction_name",
    ["INTAKE_INSTRUCTIONS", "HOLDING_INSTRUCTIONS", "DRAFT_INSTRUCTIONS", "REWRITE_INSTRUCTIONS"],
)
async def test_conditional_register_contract_reaches_openai_typed_payload(
    instruction_name: str,
) -> None:
    import json

    import httpx2 as httpx
    from agent_fakes import draft
    from openai import AsyncOpenAI
    from pydantic_ai.models import override_allow_model_requests
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from agent import prompts
    from agent.llm_schemas import DraftOutput

    instructions = getattr(prompts, instruction_name)
    original = "Kayıt çalışıyorsa ne olur?"
    payload = draft()
    prompt = prompts.rewrite_prompt(
        json.dumps(payload, ensure_ascii=False), ["çalışıyorsa"], question=original
    )
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "offline.invalid"
        body = json.loads(request.content)
        calls.append(body)
        assert len(calls) == 1
        system = body["messages"][0]["content"]
        assert system == instructions
        for text in (
            "-iyorsa/-ıyorsa/-uyorsa/-üyorsa",
            "karşılayabiliyorsa",
            "missing_info.condition/result",
            "title",
            "fact_value",
            "used_for",
        ):
            assert text in system
        assert body["messages"][1]["content"] == prompt
        tool = body["tools"][0]["function"]
        assert tool["parameters"]["additionalProperties"] is False
        assert "question" not in tool["parameters"]["$defs"]["MissingDraft"]["properties"]
        return httpx.Response(
            200,
            json={
                "id": "offline",
                "object": "chat.completion",
                "created": 0,
                "model": "offline",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "out",
                                    "type": "function",
                                    "function": {
                                        "name": tool["name"],
                                        "arguments": json.dumps(payload),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIProvider(
            openai_client=AsyncOpenAI(
                api_key="offline-placeholder",
                base_url="https://offline.invalid/v1",
                http_client=client,
                max_retries=0,
            )
        )
        model = OpenAIChatModel("offline", provider=provider)
        with override_allow_model_requests(True):
            result = await Llm(Models(model, model)).run(
                "strong", DraftOutput, instructions, prompt
            )
    assert result == DraftOutput.model_validate(payload)
    assert len(calls) == 1
