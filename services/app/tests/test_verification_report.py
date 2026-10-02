import json
import random
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

from app.verification.report import build_summary, render_markdown, write_report
from app.verification.runner import RunOptions, SourceStats, run_court
from app.verification.store import Candidate
from hukuk_verify import DecisionKey, Outcome
from hukuk_verify.adapters import SourceAdapter
from hukuk_verify.errors import SourceUnavailable
from hukuk_verify.models import LookupResult, OfficialRow, OfficialText
from hukuk_verify.ratelimit import RateLimiter

PARTY = "AYŞE YILMAZ"  # what a decision text would carry; must never reach a report


def stats() -> SourceStats:
    s = SourceStats("yargitay", "karararama_yargitay", candidates=5, unsupported=1)
    s.outcomes.update(["verified_official", "verified_official", "mismatch", "not_in_source"])
    s.by_band["2015+"].update(["verified_official", "mismatch"])
    s.by_band["<=2009"].update(["not_in_source"])
    s.fuzzy.update(["decision_date"])
    s.errors.update(["SourceUnavailable"])
    s.mismatches.append("yargitay 9. HD E. 2017/1 K. 2020/2")
    s.sample = {"checked": 20, "found": 0, "heuristic_disabled": False}
    s.rate_limited, s.backoff_seconds, s.requests = 2, 180.0, 31
    return s


def test_summary_counts_per_source() -> None:
    summary = build_summary([stats()], dry_run=False)
    source = summary["sources"]["yargitay"]
    assert source["outcomes"] == {
        "verified_official": 2,
        "verified_uyap": 0,
        "mismatch": 1,
        "not_in_source": 1,
        "error": 1,
    }
    assert source["by_year_band"] == {
        "<=2009": {"not_in_source": 1},
        "2015+": {"verified_official": 1, "mismatch": 1},
    }
    assert source["fuzzy_fields"] == {"decision_date": 1}
    assert (source["rate_limited"], source["backoff_seconds"]) == (2, 180.0)
    assert source["mismatches"] == ["yargitay 9. HD E. 2017/1 K. 2020/2"]


def test_markdown_lists_mismatches_and_the_sample() -> None:
    text = render_markdown(build_summary([stats()], dry_run=True))
    assert "Network: live; DB write: no" in text
    assert "- yargitay 9. HD E. 2017/1 K. 2020/2" in text
    assert "20 queried, 0 found" in text
    assert "DB write: yes" in render_markdown(build_summary([stats()], dry_run=False))
    assert "| 2015+ | 1 | 0 | 1 | 0 | 0 |" in text


def test_write_report_creates_both_files(tmp_path: Path) -> None:
    write_report(build_summary([SourceStats("aym", "aym_kbb")], dry_run=False), tmp_path / "out")
    data = json.loads((tmp_path / "out" / "verify-summary.json").read_text(encoding="utf-8"))
    assert data["sources"]["aym"]["source"] == "aym_kbb"
    assert (tmp_path / "out" / "verify-summary.md").exists()


class LeakyStub(SourceAdapter):
    """A source whose official text and error carry a party name; the report must not."""

    SOURCE = "karararama_yargitay"
    VERIFIED = Outcome.verified_official
    ORIGIN = "https://stub.invalid"

    def __init__(self) -> None:
        super().__init__(httpx.AsyncClient(), RateLimiter())

    def supports(self, key: DecisionKey) -> bool:
        return True

    async def lookup(self, key: DecisionKey) -> LookupResult:
        if key.esas_no == "2020/9":
            raise SourceUnavailable(f"timeout for {PARTY}")
        wrong_date = date(2019, 1, 1) if key.esas_no == "2020/2" else key.decision_date
        assert key.esas_no and key.karar_no
        return LookupResult(
            [OfficialRow("1", "u", "9. Hukuk Dairesi", key.esas_no, key.karar_no, wrong_date)]
        )

    async def fetch_text(self, ref: str) -> OfficialText | None:
        return OfficialText(f"Davacı {PARTY}", {"data": f"Davacı {PARTY}"})


async def test_a_report_carries_no_decision_text_or_party_name(tmp_path: Path) -> None:
    key = DecisionKey(
        "yargitay", "daire", "9. HD", "", "", "2020/1", "2020/1", date(2020, 5, 1), "karar"
    )
    todo = [
        Candidate(None, key),
        Candidate(None, DecisionKey(**{**key.__dict__, "esas_no": "2020/2"})),
        Candidate(None, DecisionKey(**{**key.__dict__, "esas_no": "2020/9"})),
    ]
    options = RunOptions(rng=random.Random(1))
    result = await run_court(None, "yargitay", LeakyStub(), todo, options)
    assert result.mismatches == ["yargitay 9. HD E. 2020/2 K. 2020/1"]
    assert result.errors == Counter({"SourceUnavailable": 1})

    write_report(build_summary([result], dry_run=True), tmp_path)
    for report in tmp_path.iterdir():
        assert PARTY not in report.read_text(encoding="utf-8")
        assert "Davacı" not in report.read_text(encoding="utf-8")
