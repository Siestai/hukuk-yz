"""The knowledge base as the agent sees it: `GET /kb/search` of `app` (docs/tasks/14-kb-search.md)
and the whole-text reads of a statute article and of a genelge section.

The client is a protocol, so the graph is tested with a fake one. A hit is one record with the
matching passages (`matches`); a passage of an `internal_only` chunk comes without text and cannot
be read.
"""

from collections.abc import Sequence
from datetime import date
from typing import Literal, NamedTuple, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from agent.kunye import admin_act_section, statute_article
from hukuk_models import Band
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
    # The confidence band of an `analyzed` record (a test source, decision K1).
    band: Band | None = None
    verification: Verification | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    score: float = 0.0
    matches: list[KbMatch] = []
    complete: bool = False


UnreadableReason = Literal["not_found", "gap", "not_in_force"]


class Unreadable(NamedTuple):
    """Why a genelge section was not read: `not_found`, or the status the knowledge base gave
    (`gap`: no text on file for the date; `not_in_force`)."""

    reason: UnreadableReason


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

    async def read_section(self, ref: str, as_of: date) -> KbHit | Unreadable: ...


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
        found = statute_article(ref)
        if found is None:
            return []
        number, article = found
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
            if not version or not version.get("text"):
                return []
            review_status = data["review_status"]
            # An unreviewed article has no published row: its extraction is the record, the
            # same one a search hit of it names.
            source_id = str(version["id"] if review_status == "approved" else data["extraction_id"])
            return [
                KbHit(
                    source_id=source_id,
                    category="statute",
                    title=f"{number} m.{article}",
                    ref=ref,
                    review_status=review_status,
                    band=data.get("band"),
                    valid_from=version.get("valid_from"),
                    valid_to=version.get("valid_to"),
                    complete=True,
                    matches=[
                        KbMatch(
                            chunk_id=source_id,
                            text=version["text"],
                            char_start=0,
                            char_end=len(version["text"]),
                        )
                    ],
                )
            ]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise KbUnavailable("article read failed") from exc

    async def read_section(self, ref: str, as_of: date) -> KbHit | Unreadable:
        found = admin_act_section(ref)
        if found is None or found.section is None:
            return Unreadable("not_found")
        try:
            # The route names the genelge with a dash for the slash: "2020-8".
            response = await self._http.get(
                f"/admin-acts/{found.act.replace('/', '-')}/sections/{quote(found.section)}",
                params={"as_of": as_of.isoformat()},
            )
            if response.status_code == 404:
                return Unreadable("not_found")
            response.raise_for_status()
            data = response.json()
            if data["status"] in ("gap", "not_in_force"):
                return Unreadable(data["status"])
            version = data.get("version")
            if data["status"] != "found" or not version or not version.get("text"):
                return Unreadable("not_found")
            source_id = str(data["extraction_id"])
            return KbHit(
                source_id=source_id,
                category="admin_act",
                title=data["citation"],
                ref=data["citation"],
                review_status=data["review_status"],
                band=data.get("band"),
                valid_from=version.get("valid_from"),
                valid_to=version.get("valid_to"),
                complete=True,
                matches=[
                    KbMatch(
                        chunk_id=source_id,
                        text=version["text"],
                        char_start=0,
                        char_end=len(version["text"]),
                    )
                ],
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise KbUnavailable("section read failed") from exc

    async def aclose(self) -> None:
        await self._http.aclose()
