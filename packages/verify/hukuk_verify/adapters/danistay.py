"""karararama.danistay.gov.tr (task 06 §3.4): the BİGM app with its own field names. The first
version matches the chamber and the E/K only."""

from hukuk_verify.adapters.bigm import BigmAdapter
from hukuk_verify.matching import expected_chamber
from hukuk_verify.models import DecisionKey, Outcome


class DanistayAdapter(BigmAdapter):
    SOURCE = "karararama_danistay"
    VERIFIED = Outcome.verified_official
    ORIGIN = "https://karararama.danistay.gov.tr"
    CHAMBER_FIELD = "daireKurul"

    def chamber_filter(self, key: DecisionKey) -> dict[str, str]:
        """`10. D` -> `daire: "10. Daire"`; the kurullar (`Büyük Gen.Kur.`, ...) are not mapped."""
        expected = expected_chamber(key)
        if expected and expected.endswith(" D"):
            return {"daire": f"{expected.split()[0]}. Daire"}
        return {}
