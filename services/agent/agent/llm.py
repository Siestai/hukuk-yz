"""The model calls: typed (Pydantic AI validates the output and asks again on a validation
failure) and counted into the trace of the node that makes them."""

from dataclasses import dataclass
from typing import Literal

from genai_prices import Usage, calc_price
from pydantic_ai import Agent
from pydantic_ai.models import Model

from agent.trace import current_record

Tier = Literal["fast", "strong"]
# The output is checked against the schema this many times more before the call fails.
RETRIES = 2


@dataclass(frozen=True)
class Models:
    """A model is a Pydantic AI model name ("anthropic:claude-sonnet-5-5") or a model object
    (the tests give a `TestModel` or a `FunctionModel`)."""

    fast: Model | str
    strong: Model | str


def _model_name(model: Model | str) -> str:
    return model if isinstance(model, str) else f"{model.system}:{model.model_name}"


def _cost(model: Model | str, input_tokens: int, output_tokens: int) -> float | None:
    name = _model_name(model)
    provider, _, model_id = name.partition(":")
    try:
        price = calc_price(
            Usage(input_tokens=input_tokens, output_tokens=output_tokens),
            model_ref=model_id,
            provider_id=provider,
        )
    except LookupError:
        return None
    return float(price.total_price)


class Llm:
    def __init__(self, models: Models) -> None:
        self._models = models

    async def run[T](self, tier: Tier, output_type: type[T], instructions: str, prompt: str) -> T:
        model = self._models.fast if tier == "fast" else self._models.strong
        agent = Agent(model, output_type=output_type, instructions=instructions, retries=RETRIES)
        result = await agent.run(prompt)
        usage = result.usage
        if (record := current_record()) is not None:
            record.add_usage(
                _model_name(model),
                usage.input_tokens,
                usage.output_tokens,
                _cost(model, usage.input_tokens, usage.output_tokens),
            )
        return result.output
