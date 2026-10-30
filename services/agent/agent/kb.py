"""The knowledge base as the agent sees it: `GET /kb/search` of `app` (docs/tasks/14-kb-search.md).

The client is a protocol, so the graph is tested with a fake one. A hit is one record with the
matching passages (`matches`); a passage of an `internal_only` chunk comes without text and cannot
be read.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr

from hukuk_models.chat import CitationCategory, ReviewStatus, Verification


class KbUnavailable(Exception):
    """/kb/search could not be reached or did not answer as the contract says."""


class KbMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    text: str | None = None
    char_start: int | None = None
    char_end: int | None = None


class KbHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str
    category: CitationCategory
    title: str
    ref: str
    review_status: ReviewStatus
    verification: Verification | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    score: float = 0.0
    matches: list[KbMatch] = []


class KbSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[KbHit]


class KbClient(Protocol):
    async def search(
        self,
        q: str,
        *,
        categories: Sequence[CitationCategory] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]: ...


class HttpKbClient:
    def __init__(
        self,
        base_url: str,
        service_key: SecretStr,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Service-Key": service_key.get_secret_value()},
            timeout=timeout,
            transport=transport,
        )

    async def search(
        self,
        q: str,
        *,
        categories: Sequence[CitationCategory] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]:
        params: dict[str, str | int | list[str]] = {"q": q, "limit": limit}
        if categories:
            params["category"] = list(categories)
        if as_of is not None:
            params["as_of"] = as_of.isoformat()
        try:
            response = await self._http.get("/kb/search", params=params)
            response.raise_for_status()
            return KbSearchResponse.model_validate(response.json()).items
        except (httpx.HTTPError, ValueError) as exc:
            raise KbUnavailable(str(exc)) from exc

    async def aclose(self) -> None:
        await self._http.aclose()
