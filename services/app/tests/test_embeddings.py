"""The OpenAI embedder with a fake client (task 14): no network."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from app.embeddings import OpenAIEmbedder, estimate_cost, make_embedder
from app.settings import Settings


class FakeClient:
    def __init__(self, answer: list[int] | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self._answer = answer
        self.embeddings = SimpleNamespace(create=self._create)

    async def _create(self, **request: Any) -> Any:
        self.requests.append(request)
        order = self._answer or list(range(len(request["input"])))
        data = [SimpleNamespace(index=i, embedding=[float(i)] * 4) for i in order]
        return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=7 * len(order)))


async def test_the_request_names_the_model_and_the_dimension() -> None:
    client = FakeClient()
    embedder = OpenAIEmbedder(client, "text-embedding-3-large")
    result = await embedder.embed(["bir", "iki"])
    assert client.requests == [
        {"model": "text-embedding-3-large", "input": ["bir", "iki"], "dimensions": 1024}
    ]
    assert embedder.model_id == "text-embedding-3-large:1024"
    assert result.tokens == 14


async def test_vectors_come_back_in_the_order_of_the_texts() -> None:
    result = await OpenAIEmbedder(FakeClient(answer=[2, 0, 1]), "m").embed(["a", "b", "c"])
    assert [v[0] for v in result.vectors] == [0.0, 1.0, 2.0]


async def test_a_short_answer_is_an_error() -> None:
    client = FakeClient(answer=[0])
    with pytest.raises(ValueError, match="asked for 2"):
        await OpenAIEmbedder(client, "m").embed(["a", "b"])


def test_without_a_key_there_is_no_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert make_embedder(Settings()) is None
    settings = Settings(openai_api_key=SecretStr("sk-test"))
    embedder = make_embedder(settings)
    assert embedder is not None
    assert embedder.model_id == "text-embedding-3-large:1024"


def test_the_cost_estimate_is_per_million_tokens() -> None:
    assert estimate_cost(1_000_000) == pytest.approx(0.13)
    assert estimate_cost(0) == 0
