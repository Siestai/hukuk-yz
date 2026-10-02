"""karararama.yargitay.gov.tr (task 06 §3.1; contract of docs/spike-karararama-2026-10-02.md)."""

from typing import ClassVar

from hukuk_verify.adapters.bigm import BigmAdapter
from hukuk_verify.matching import expected_chamber
from hukuk_verify.models import DecisionKey, Outcome

_HUKUK_DAIRESI = "HD"


class YargitayAdapter(BigmAdapter):
    SOURCE = "karararama_yargitay"
    VERIFIED = Outcome.verified_official
    ORIGIN = "https://karararama.yargitay.gov.tr"
    PRE_2009_SKIP = True
    RETRY_WITHOUT_CHAMBER: ClassVar[bool] = True  # the chamber spelling may differ (§3.1)
    BASE_BODY: ClassVar[dict[str, str]] = {"arananKelime": ""}

    def chamber_filter(self, key: DecisionKey) -> dict[str, str]:
        """`9. HD` -> `birimYrgHukukDaire: "9. Hukuk Dairesi"`; HGK -> `birimYrgKurulDaire`.
        Other chambers (ceza daireleri, İBK, whose body name is unconfirmed) are searched by E/K
        alone and told apart by the chamber of the answer."""
        expected = expected_chamber(key)
        if expected == "HGK":
            return {"birimYrgKurulDaire": "Hukuk Genel Kurulu"}
        if expected and expected.endswith(f" {_HUKUK_DAIRESI}"):
            return {"birimYrgHukukDaire": f"{expected.split()[0]}. Hukuk Dairesi"}
        return {}
