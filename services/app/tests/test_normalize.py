from typing import Any

import pytest

from app.loaders.normalize import OUTCOMES, normalize


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "outcome": "bozma",
        "court": "yargitay",
        "court_level": "daire",
        "decision_date": "2019-03-12",
    }
    return {**row, **overrides}


def test_a_clean_row_passes_unchanged() -> None:
    row = _row()
    assert normalize(row) == (row, [])


@pytest.mark.parametrize(
    ("parser_value", "stored"),
    [
        ("düzelterek onama", "duzelterek_onama"),
        ("bozma", "bozma"),
        ("ihlal_yok", "ihlal_yok"),
        ("", ""),
    ],
)
def test_outcome_gets_the_ascii_label(parser_value: str, stored: str) -> None:
    out, warnings = normalize(_row(outcome=parser_value))
    assert out["outcome"] == stored
    assert warnings == []
    assert stored == "" or stored in OUTCOMES


def test_unknown_outcome_is_emptied_with_a_warning() -> None:
    out, warnings = normalize(_row(outcome="kısmen bozma"))
    assert out["outcome"] == ""
    assert warnings == ["outcome_unmapped"]


def test_empty_court_stays_empty_with_a_warning() -> None:
    out, warnings = normalize(_row(court="", court_level=""))
    assert (out["court"], out["court_level"]) == ("", "")
    assert warnings == ["court_missing"]


def test_court_values_outside_the_enums_are_emptied() -> None:
    out, warnings = normalize(_row(court="konsey", court_level="üst"))
    assert (out["court"], out["court_level"]) == ("", "")
    assert warnings == ["court_unmapped", "court_level_unmapped"]


def test_invalid_date_is_emptied_without_a_new_warning() -> None:
    out, warnings = normalize(_row(decision_date="2019-13-45"))
    assert out["decision_date"] == ""
    assert warnings == []


def test_the_input_row_is_not_modified() -> None:
    row = _row(outcome="düzelterek onama")
    normalize(row)
    assert row["outcome"] == "düzelterek onama"
