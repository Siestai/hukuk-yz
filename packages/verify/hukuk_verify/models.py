"""Plain data shared by the adapters and the matcher."""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    verified_official = "verified_official"
    verified_uyap = "verified_uyap"
    mismatch = "mismatch"
    not_in_source = "not_in_source"


class FieldMatch(StrEnum):
    match = "match"
    fuzzy = "fuzzy"
    mismatch = "mismatch"
    absent = "absent"


@dataclass(frozen=True)
class DecisionKey:
    """The `decision` columns a lookup needs (enum values as their string labels)."""

    court: str
    court_level: str
    chamber: str
    source_chamber: str
    bam_region: str
    esas_no: str | None
    karar_no: str | None
    decision_date: date | None
    decision_kind: str | None


@dataclass(frozen=True)
class OfficialRow:
    """One search result row, with the site's own spelling kept in `chamber`."""

    ref: str
    url: str
    chamber: str
    esas_no: str
    karar_no: str
    decision_date: date | None


@dataclass(frozen=True)
class LookupResult:
    rows: list[OfficialRow]


@dataclass(frozen=True)
class OfficialText:
    """What the site serves for a decision: `body` is hashed, `payload` is the raw answer kept in
    the file cache (never in the database)."""

    body: str
    payload: dict[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    outcome: Outcome
    source: str
    official_ref: str | None = None
    official_url: str | None = None
    # Per-field match / fuzzy / mismatch / absent, the site's own values, `fuzzy`, `ambiguous`,
    # `skipped`. Court and party names never appear here.
    matched: dict[str, Any] = field(default_factory=dict)
    official_text: OfficialText | None = None
