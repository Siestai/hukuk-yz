"""The eval set and its scorer (`eval/score.py`, task 15): the cases are well formed and the
hand-made fixtures score full marks."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

EVAL = Path(__file__).parents[1]
FIXTURES = EVAL / "fixtures"
CASES = EVAL / "cases"
IDS = ["SB-001", "SB-016", "SB-026"]

spec = importlib.util.spec_from_file_location("eval_score", EVAL / "score.py")
assert spec and spec.loader
score_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_module)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_answer(name: str) -> dict[str, Any]:
    return load(FIXTURES / name)  # type: ignore[no-any-return]


def test_cases_are_well_formed() -> None:
    paths = sorted(CASES.glob("*.yaml"))
    assert len(paths) == 10
    for path in paths:
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert case["id"] == path.stem
        assert case["question"].strip()
        expected = case["expected"]
        assert expected["status"] in ("definite", "conditional")
        assert expected["headline_contains"] and expected["must_cite"]
        assert case["tags"]


@pytest.mark.parametrize("case_id", IDS)
def test_every_fixture_answer_gets_full_marks(case_id: str) -> None:
    case = score_module.load_case(CASES / f"{case_id}.yaml")
    scenario = load(FIXTURES / f"{case_id}.scenario.json")
    clarification = score_module.load_clarification(FIXTURES / f"{case_id}.scenario.json")
    for name in (scenario["on_skip"], scenario["on_complete"]):
        metrics = score_module.score(load(FIXTURES / name), case, clarification)
        # `status` is the expected one only for one of the two answers of a scenario.
        measured = [m for m in metrics if m.name != "status"]
        assert all(m.value == 1.0 for m in measured), score_module.render(case_id, metrics)


@pytest.mark.parametrize("case_id", IDS)
def test_one_fixture_answer_has_the_expected_status(case_id: str) -> None:
    case = score_module.load_case(CASES / f"{case_id}.yaml")
    scenario = load(FIXTURES / f"{case_id}.scenario.json")
    statuses = [
        load(FIXTURES / n)["status"] for n in (scenario["on_skip"], scenario["on_complete"])
    ]
    assert case["expected"]["status"] in statuses


def test_scorer_catches_what_it_should() -> None:
    case = score_module.load_case(CASES / "SB-016.yaml")
    clarification = score_module.load_clarification(FIXTURES / "SB-016.scenario.json")
    raw = _fixture_answer("SB-016.answer.json")
    raw["headline"] = "Cevap verilmiyor."
    raw["points"][0]["text"] += " SSİY m.102"
    for point in raw["points"]:
        for citation in point["citations"]:
            citation["ref"] = "9999 m.1"
    for row in raw["holding_map"]["rows"]:
        row["citation"]["ref"] = "9999 m.1"
    raw["disclaimer"] = ""
    by_name = {m.name: m for m in score_module.score(raw, case, clarification)}
    assert by_name["headline"].value == 0.0
    assert by_name["must_not"].value < 1.0
    assert by_name["formal_mode"].value == 0.0
    assert by_name["must_cite"].value < 1.0
    assert by_name["disclaimer"].value == 0.0
    assert by_name["schema"].value == 0.0
    # must_ask cannot be measured without the clarification
    none = {m.name: m for m in score_module.score(_fixture_answer("SB-016.answer.json"), case)}
    assert none["must_ask"].value is None
