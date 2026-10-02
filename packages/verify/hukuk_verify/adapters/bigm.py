"""The Adalet Bakanlığı BİGM search app behind karararama.yargitay.gov.tr, emsal.uyap.gov.tr and
karararama.danistay.gov.tr: `POST /aramadetaylist` and `GET /getDokuman?id=` (task 06 §3.1-3.4)."""

import re
from abc import abstractmethod
from datetime import date, datetime
from typing import Any, ClassVar

import httpx

from hukuk_verify.adapters.base import SourceAdapter
from hukuk_verify.errors import UnexpectedResponse
from hukuk_verify.matching import normalize_number
from hukuk_verify.models import DecisionKey, LookupResult, OfficialRow, OfficialText
from hukuk_verify.ratelimit import RateLimiter

_NUMBER = re.compile(r"^(\d{4})/(\d+)$")
PAGE_SIZE = 10


def split_number(raw: str | None) -> tuple[str, str] | None:
    """`"2017/17327"` -> `("2017", "17327")`; None when it is not a `YYYY/N` number."""
    found = _NUMBER.match(normalize_number(raw or ""))
    return (found.group(1), found.group(2)) if found else None


def parse_site_date(raw: str) -> date | None:
    """`dd.MM.yyyy`, which is what these sites write."""
    try:
        return datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        return None


class BigmAdapter(SourceAdapter):
    CHAMBER_FIELD: ClassVar[str] = "daire"  # the row key that holds the chamber
    RETRY_WITHOUT_CHAMBER: ClassVar[bool] = False
    # Search body keys common to the three sites besides the filters.
    BASE_BODY: ClassVar[dict[str, Any]] = {}

    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter) -> None:
        super().__init__(client, limiter)
        self._session_open = False

    def supports(self, key: DecisionKey) -> bool:
        return split_number(key.esas_no) is not None and split_number(key.karar_no) is not None

    @abstractmethod
    def chamber_filter(self, key: DecisionKey) -> dict[str, str]:
        """The body entries that narrow the search to the decision's chamber; {} for none."""

    async def _open_session(self) -> None:
        """`GET /` first: the app hands out its cookie there."""
        await self._request("GET", f"{self.ORIGIN}/")

    async def lookup(self, key: DecisionKey) -> LookupResult:
        if not self._session_open:
            await self._open_session()
            self._session_open = True
        filters = self.chamber_filter(key)
        rows = await self._search(key, filters)
        if not rows and filters and self.RETRY_WITHOUT_CHAMBER:
            rows = await self._search(key, {})
        return LookupResult(rows)

    async def _search(self, key: DecisionKey, filters: dict[str, str]) -> list[OfficialRow]:
        esas, karar = split_number(key.esas_no), split_number(key.karar_no)
        assert esas and karar  # `supports` guards the call
        body = {
            **self.BASE_BODY,
            **filters,
            "esasYil": esas[0],
            "esasIlkSiraNo": esas[1],
            "esasSonSiraNo": esas[1],
            "kararYil": karar[0],
            "kararIlkSiraNo": karar[1],
            "kararSonSiraNo": karar[1],
            "siralama": "1",
            "siralamaDirection": "desc",
            "pageSize": PAGE_SIZE,
            "pageNumber": 1,
        }
        response = await self._request(
            "POST",
            f"{self.ORIGIN}/aramadetaylist",
            json={"data": body},
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.ORIGIN}/",
            },
        )
        return self._rows(self._json(response))

    def _rows(self, answer: Any) -> list[OfficialRow]:
        """`metadata.FMTY == "ERROR"` is an error, not an empty result."""
        try:
            if answer["metadata"]["FMTY"] == "ERROR":
                raise UnexpectedResponse("the site answered with an error envelope")
            return [self._row(raw) for raw in answer["data"]["data"]]
        except (KeyError, TypeError) as exc:
            raise UnexpectedResponse("unknown answer shape") from exc

    def _row(self, raw: dict[str, Any]) -> OfficialRow:
        return OfficialRow(
            ref=str(raw["id"]),
            url=f"{self.ORIGIN}/getDokuman?id={raw['id']}",
            chamber=raw[self.CHAMBER_FIELD],
            esas_no=raw["esasNo"],
            karar_no=raw["kararNo"],
            decision_date=parse_site_date(raw["kararTarihi"]),
        )

    async def fetch_text(self, ref: str) -> OfficialText | None:
        response = await self._request("GET", f"{self.ORIGIN}/getDokuman", params={"id": ref})
        answer = self._json(response)
        body = answer.get("data") if isinstance(answer, dict) else None
        return OfficialText(body, answer) if isinstance(body, str) and body else None
