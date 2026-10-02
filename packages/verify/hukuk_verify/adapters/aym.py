"""kararlarbilgibankasi.anayasa.gov.tr, the AYM decision bank (task 06 §3.3)."""

import base64
import time
from datetime import date
from typing import Any

import httpx

from hukuk_verify.adapters.base import SourceAdapter
from hukuk_verify.adapters.bigm import split_number
from hukuk_verify.errors import UnexpectedResponse
from hukuk_verify.models import DecisionKey, LookupResult, OfficialRow, OfficialText, Outcome
from hukuk_verify.ratelimit import RateLimiter

PAGE_SIZE = 5
# Without `kararTipi` the free-text search ignores E/K, so the kind must map (probe 2026-10-02).
_NORM = "NormDenetimi"
_INDIVIDUAL = "BireyselBasvuru"
KARAR_TIPI: dict[str, str] = {
    "norm_denetimi": _NORM,
    "iptal": _NORM,
    "red": _NORM,
    "bireysel_basvuru": _INDIVIDUAL,
}


class AymAdapter(SourceAdapter):
    SOURCE = "aym_kbb"
    VERIFIED = Outcome.verified_official
    ORIGIN = "https://kararlarbilgibankasi.anayasa.gov.tr"

    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter) -> None:
        super().__init__(client, limiter)
        self._types: dict[str, str] = {}  # decision uuid -> kararTipi, for `fetch_text`

    def supports(self, key: DecisionKey) -> bool:
        kind = KARAR_TIPI.get(key.decision_kind or "")
        if kind == _INDIVIDUAL:
            # The application number sits in esas_no; there is no karar number.
            return split_number(key.esas_no) is not None
        return (
            kind == _NORM
            and split_number(key.esas_no) is not None
            and split_number(key.karar_no) is not None
        )

    async def lookup(self, key: DecisionKey) -> LookupResult:
        tipi = KARAR_TIPI[key.decision_kind or ""]
        numbers = (
            {"basvuruNo": key.esas_no}
            if tipi == _INDIVIDUAL
            else {"esasNo": key.esas_no, "kararNo": key.karar_no}
        )
        response = await self._request(
            "POST",
            f"{self.ORIGIN}/api/core/public/search",
            json={
                "kararTipi": tipi,
                **numbers,
                "_timestamp": int(time.time() * 1000),
                "page": 1,
                "size": PAGE_SIZE,
                "sort": "yayinTarihi",
                "order": "desc",
            },
            headers={"Origin": self.ORIGIN, "Referer": f"{self.ORIGIN}/"},
        )
        answer = self._json(response)
        try:
            rows = [self._row(raw, tipi) for raw in answer["data"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise UnexpectedResponse("unknown answer shape") from exc
        return LookupResult(rows)

    def _row(self, raw: dict[str, Any], tipi: str) -> OfficialRow:
        ref = str(raw["id"])
        self._types[ref] = tipi
        page_id = base64.b64encode(f"kbb:{ref}".encode()).decode().rstrip("=")
        decided = raw.get("kararTarihi")
        return OfficialRow(
            ref=ref,
            url=f"{self.ORIGIN}/kbb/pages/search/Tumu?id={page_id}&type={tipi}",
            chamber="",
            esas_no=raw.get("esasNo") or raw["basvuruNo"],
            karar_no=raw.get("kararNo") or "",
            decision_date=date.fromisoformat(decided) if decided else None,
        )

    async def fetch_text(self, ref: str) -> OfficialText | None:
        """`icerik`, the HTML text of the decision, from the search by id (what the decision page
        itself asks for). The `dosyalar` list holds attachments, not the decision."""
        answer = self._json(
            await self._request(
                "POST",
                f"{self.ORIGIN}/api/core/public/search",
                json={"id": ref, "size": 1, "kararTipi": self._types.get(ref, _NORM)},
                headers={"Origin": self.ORIGIN, "Referer": f"{self.ORIGIN}/"},
            )
        )
        try:
            body = answer["data"][0].get("icerik")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise UnexpectedResponse("unknown answer shape") from exc
        return OfficialText(body, {"icerik": body}) if body else None
