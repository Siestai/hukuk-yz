"""emsal.uyap.gov.tr, BAM decisions only (task 06 §3.2). Yargıtay and Danıştay are not searched
here: the site's entries for them are plain links to their own karar arama sites."""

import re
from typing import ClassVar

import httpx

from hukuk_verify.adapters.bigm import BigmAdapter
from hukuk_verify.matching import expected_chamber, fold
from hukuk_verify.models import DecisionKey, Outcome
from hukuk_verify.ratelimit import RateLimiter

_SELECT = re.compile(
    r'<select[^>]*name="Bam Hukuk Mahkemeleri"[^>]*>(.*?)</select>', re.DOTALL | re.IGNORECASE
)
_OPTION = re.compile(r'<option value="([^"]*)"')


class UyapEmsalAdapter(BigmAdapter):
    SOURCE = "uyap_emsal"
    VERIFIED = Outcome.verified_uyap
    ORIGIN = "https://emsal.uyap.gov.tr"
    BASE_BODY: ClassVar[dict[str, str]] = {"arananKelime": ""}

    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter) -> None:
        super().__init__(client, limiter)
        self._chambers: dict[str, str] = {}  # folded full name -> the option value to send

    async def _open_session(self) -> None:
        """The home page also carries the list of BAM chambers the search can filter by."""
        response = await self._request("GET", f"{self.ORIGIN}/")
        if select := _SELECT.search(response.text):
            self._chambers = {fold(v): v for v in _OPTION.findall(select.group(1))}

    def chamber_filter(self, key: DecisionKey) -> dict[str, str]:
        """`bam_region` + " Bölge Adliye Mahkemesi " + `n` + ". Hukuk Dairesi", matched to the
        site's option list ignoring `Istanbul` / `İstanbul`. A chamber that is not in the list
        gets no filter: the search is by E/K and the chamber of the answer is compared."""
        expected = expected_chamber(key)
        if not (key.bam_region and expected and expected.endswith(" HD")):
            return {}
        name = f"{key.bam_region} Bölge Adliye Mahkemesi {expected.split()[0]}. Hukuk Dairesi"
        option = self._chambers.get(fold(name))
        return {"birimHukukMah": option} if option else {}
