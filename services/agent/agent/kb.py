"""The knowledge base as the agent sees it: `GET /kb/search` of `app` (docs/tasks/14-kb-search.md).

The client is a protocol, so the graph is tested with a fake one. A hit is one record with the
matching passages (`matches`); a passage of an `internal_only` chunk comes without text and cannot
be read.
"""

import re
from collections.abc import Sequence
from datetime import date
from typing import Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

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
    parent_id: str | None = None
    version_id: str | None = None
    category: CitationCategory
    title: str
    ref: str
    review_status: ReviewStatus
    verification: Verification | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    score: float = 0.0
    matches: list[KbMatch] = []
    complete: bool = False


class KbSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[KbHit] = Field(validation_alias="results")


class KbClient(Protocol):
    async def search(
        self,
        q: str,
        *,
        categories: Sequence[CitationCategory] = (),
        as_of: date | None = None,
        limit: int = 10,
    ) -> list[KbHit]: ...

    async def read_article(self, ref: str, as_of: date) -> list[KbHit]: ...


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
            hits = KbSearchResponse.model_validate(response.json()).items
            # One source parent can contain many articles/versions. Keep the read unit identity
            # so search and full article reads merge without collapsing unrelated articles.
            return [
                h.model_copy(update={"source_id": h.version_id or h.parent_id or h.source_id})
                for h in hits
            ]
        except (httpx.HTTPError, ValueError) as exc:
            raise KbUnavailable(str(exc)) from exc

    async def read_article(self, ref: str, as_of: date) -> list[KbHit]:
        match = re.fullmatch(r"(\d+) m\.(.+)", ref)
        if match is None:
            return []
        number, article = match.groups()
        # The route takes the number as a path: a '/' ("18/A") stays a separator, not %2F.
        try:
            response = await self._http.get(
                f"/statutes/{number}/articles/{quote(article, safe='/')}",
                params={"as_of": as_of.isoformat()},
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
            if data["status"] != "found":
                return []
            version = data.get("version")
            if not version or not version.get("text") or not version.get("id"):
                return []
            return [
                KbHit(
                    source_id=str(version["id"]),
                    category="statute",
                    title=f"{number} m.{article}",
                    ref=ref,
                    review_status="approved",
                    valid_from=version.get("valid_from"),
                    valid_to=version.get("valid_to"),
                    complete=True,
                    matches=[
                        KbMatch(
                            chunk_id=str(version["id"]),
                            text=version["text"],
                            char_start=0,
                            char_end=len(version["text"]),
                        )
                    ],
                )
            ]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise KbUnavailable("article read failed") from exc

    async def aclose(self) -> None:
        await self._http.aclose()
