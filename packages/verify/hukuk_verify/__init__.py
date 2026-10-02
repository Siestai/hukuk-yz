"""Official-source lookup and E/K matching for court decisions (task 06). No database."""

from hukuk_verify.models import DecisionKey, FieldMatch, Outcome, VerifyResult
from hukuk_verify.verify import verify

__all__ = ["DecisionKey", "FieldMatch", "Outcome", "VerifyResult", "verify"]
