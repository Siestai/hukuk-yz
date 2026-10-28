"""Embeddings for the search index and the search query (task 14): OpenAI
`text-embedding-3-large`, cut to `EMBEDDING_DIM` dimensions (the width of `chunk.embedding`).

The client is injected, so tests never reach the network. Retries and the wait on a rate limit
(`Retry-After`) are the client's own (`MAX_RETRIES`); a batch that still fails raises.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.models.chunk import EMBEDDING_DIM
from app.settings import Settings, get_settings

MAX_RETRIES = 8
TIMEOUT_SECONDS = 60.0
# US dollars per million tokens of text-embedding-3-large (OpenAI price list); a report estimate.
PRICE_PER_MILLION_TOKENS = 0.13


@dataclass(frozen=True)
class Embedded:
    vectors: list[list[float]]
    tokens: int


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """Written to `chunk.embedding_model`: the model and the dimension."""
        ...

    async def embed(self, texts: Sequence[str]) -> Embedded: ...


class OpenAIEmbedder:
    def __init__(self, client: Any, model: str, dimensions: int = EMBEDDING_DIM) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions

    @property
    def model_id(self) -> str:
        return f"{self._model}:{self._dimensions}"

    async def embed(self, texts: Sequence[str]) -> Embedded:
        response = await self._client.embeddings.create(
            model=self._model, input=list(texts), dimensions=self._dimensions
        )
        data = sorted(response.data, key=lambda d: d.index)
        if len(data) != len(texts):
            raise ValueError(f"asked for {len(texts)} embeddings, got {len(data)}")
        return Embedded([list(d.embedding) for d in data], response.usage.total_tokens)


def make_embedder(settings: Settings) -> Embedder | None:
    """None without `OPENAI_API_KEY`."""
    if settings.openai_api_key is None:
        return None
    client = AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        max_retries=MAX_RETRIES,
        timeout=TIMEOUT_SECONDS,
    )
    return OpenAIEmbedder(client, settings.embedding_model)


def estimate_cost(tokens: int) -> float:
    return tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS


@lru_cache
def get_embedder() -> Embedder | None:
    """The embedder of the API process (one client, reused); tests override this dependency."""
    return make_embedder(get_settings())
