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
