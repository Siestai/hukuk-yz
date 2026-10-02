from typing import Any

import pytest

from app.loaders.confidence import LOW_PENALTY, MEDIUM_PENALTY, RULES, confidence, reasons_of


def _fields(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "court": "yargitay",
        "court_level": "daire",
        "chamber": "9. HD",
        "decision_kind": "karar",
        "esas_no": "2017/16188",
        "karar_no": "2019/1234",
        "decision_date": "2019-03-12",
        "related_articles": [{"statute": 4857}],
        "keywords": ["fesih"],
        "outcome": "bozma",
        "editorial_summary": "özet",
        "full_text": "metin",
        "layout": "era2_classic",
        "text_completeness": "full",
    }
    return {**record, **overrides}


def test_a_clean_record_is_high() -> None:
    assert confidence(_fields(), []) == {"score": 100, "band": "high", "reasons": []}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"court": "", "court_level": ""}, "missing_court"),
        ({"esas_no": ""}, "missing_esas_no"),
        ({"karar_no": ""}, "missing_karar_no"),
        ({"decision_date": ""}, "missing_decision_date"),
        ({"chamber": ""}, "missing_chamber"),
        ({"layout": "unknown"}, "layout_unknown"),
        ({"text_completeness": "summary_only"}, "text_summary_only"),
        (
            {"duplicate_group": {"key": [], "dup_kind": "different_text"}},
            "duplicate_different_text",
        ),
        ({"duplicate_group": {"key": [], "dup_kind": "date_mismatch"}}, "duplicate_date_mismatch"),
    ],
)
def test_low_rules(overrides: dict[str, Any], reason: str) -> None:
    result = confidence(_fields(**overrides), [])
    assert result["band"] == "low"
    assert reason in result["reasons"]


@pytest.mark.parametrize("warning", ["body_not_found", "duplicate_of"])
def test_low_warnings(warning: str) -> None:
    result = confidence(_fields(), [warning])
    assert (result["band"], result["reasons"]) == ("low", [warning])


@pytest.mark.parametrize(
    "warning",
    [
        "header_closing_date_mismatch",
        "karar_year_ne_date_year",
        "date_is_lower_court",
        "date_from_closing",
        "body_start_approximate",
        "statute_inferred_from_date",
        "statute_unmapped",
        "date_outside_issue_year",
        "multiple_esas_candidates:2010/1",
    ],
)
def test_medium_warnings(warning: str) -> None:
    result = confidence(_fields(), [warning])
    assert result["band"] == "medium"
    assert result["score"] == 100 - MEDIUM_PENALTY


@pytest.mark.parametrize("dup_kind", ["excerpt", "same_text"])
def test_medium_duplicate_groups(dup_kind: str) -> None:
    result = confidence(_fields(duplicate_group={"key": [], "dup_kind": dup_kind}), [])
    assert (result["band"], result["reasons"]) == ("medium", [f"duplicate_{dup_kind}"])


def test_the_worst_band_wins_and_penalties_add_up() -> None:
    result = confidence(_fields(esas_no=""), ["date_from_closing"])
    assert result["band"] == "low"
    assert result["score"] == 100 - LOW_PENALTY - MEDIUM_PENALTY
    assert result["reasons"] == ["missing_esas_no", "date_from_closing"]


def test_the_score_never_goes_below_zero() -> None:
    result = confidence(_fields(esas_no="", karar_no="", decision_date=""), ["body_not_found"])
    assert result["score"] == 0


def test_fields_a_court_does_not_have_are_not_missing() -> None:
    abad = _fields(court="abad", court_level="international", chamber="", esas_no="", karar_no="")
    assert confidence(abad, []) == {"score": 100, "band": "high", "reasons": []}


def test_warnings_outside_the_table_are_ignored() -> None:
    assert reasons_of(_fields(), ["closing_date_rejected", "invalid_date"]) == []


def test_every_rule_is_low_or_medium() -> None:
    assert {band for band, _ in RULES.values()} == {"low", "medium"}
