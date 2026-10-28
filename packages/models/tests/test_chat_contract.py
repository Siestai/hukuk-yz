"""The chat contract (task 15): validators, the hand-made fixtures and the eval scorer."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from hukuk_models.chat import (
    Answer,
    CaseFacts,
    ChatEvent,
    Clarification,
    MessageRequest,
    Turn,
)

EVAL = Path(__file__).parents[3] / "eval"
FIXTURES = EVAL / "fixtures"
CASES = EVAL / "cases"
IDS = ["SB-001", "SB-016", "SB-026"]

spec = importlib.util.spec_from_file_location("eval_score", EVAL / "score.py")
assert spec and spec.loader
score_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_module)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def answer_files() -> list[Path]:
    return sorted(FIXTURES.glob("*.answer.json"))


@pytest.mark.parametrize("path", answer_files(), ids=lambda p: p.name)
def test_answer_fixtures_validate(path: Path) -> None:
    answer = Answer.model_validate(load(path))
    assert answer.disclaimer == "Hukuki görüş değildir."
    # the stream carries it unchanged
    ChatEvent.model_validate({"type": "answer", "answer": answer.model_dump(mode="json")})


@pytest.mark.parametrize("case_id", IDS)
def test_scenarios_validate(case_id: str) -> None:
    raw = load(FIXTURES / f"{case_id}.scenario.json")
    CaseFacts.model_validate(raw["facts"])
    CaseFacts.model_validate(raw["facts_complete"])
    clarification = Clarification.model_validate(raw["clarification"])
    assert set(raw["complete_answers"]) == {q.id for q in clarification.questions}
    assert Answer.model_validate(load(FIXTURES / raw["on_skip"])).status == "conditional"


def test_every_event_type_round_trips() -> None:
    for payload in (
        {"type": "step", "node": "retrieve", "label": "Kaynaklar okunuyor"},
        {"type": "error", "code": "chat_unavailable", "params": {}},
        {"type": "done", "turn_id": None, "trace_id": None},
    ):
        assert ChatEvent.model_validate(payload).model_dump(mode="json")["type"] == payload["type"]
    with pytest.raises(ValidationError):
        ChatEvent.model_validate({"type": "nope"})
    with pytest.raises(ValidationError):
        ChatEvent.model_validate({"type": "error", "code": "not_a_code"})


def _fixture_answer(name: str = "SB-001.answer.json") -> dict[str, Any]:
    return load(FIXTURES / name)  # type: ignore[no-any-return]


def test_conditional_answer_needs_missing_info() -> None:
    raw = _fixture_answer()
    assert raw["status"] == "conditional"
    raw["missing_info"] = []
    with pytest.raises(ValidationError, match="missing_info"):
        Answer.model_validate(raw)


def test_definite_answer_cannot_rest_on_an_unknown_fact() -> None:
    raw = _fixture_answer("SB-016.answer.json")
    assert raw["status"] == "definite"
    raw["fact_chips"][0]["status"] = "unknown"
    with pytest.raises(ValidationError, match="unknown fact"):
        Answer.model_validate(raw)


def test_definite_answer_has_no_unknown_holding_row() -> None:
    raw = _fixture_answer("SB-016.answer.json")
    raw["holding_map"]["rows"][0]["result"] = "unknown"
    with pytest.raises(ValidationError, match="unknown row"):
        Answer.model_validate(raw)


def test_a_citation_must_have_been_read() -> None:
    raw = _fixture_answer()
    raw["read_sources"]["items"] = []
    raw["read_sources"].update(statute_articles=0, decisions=0, admin_acts=0)
    with pytest.raises(ValidationError, match="cited but not read"):
        Answer.model_validate(raw)


def test_read_source_counts_come_from_items() -> None:
    raw = _fixture_answer()
    raw["read_sources"]["decisions"] += 1
    with pytest.raises(ValidationError, match="counts"):
        Answer.model_validate(raw)


def test_disclaimer_is_fixed() -> None:
    raw = _fixture_answer()
    raw["disclaimer"] = "Hukuki görüştür."
    with pytest.raises(ValidationError):
        Answer.model_validate(raw)


def test_unknown_fields_are_rejected() -> None:
    raw = _fixture_answer()
    raw["extra"] = 1
    with pytest.raises(ValidationError):
        Answer.model_validate(raw)


def test_fact_value_matches_status() -> None:
    CaseFacts.model_validate(
        {"title": "t", "facts": [{"key": "a", "label": "A", "status": "unknown"}]}
    )
    with pytest.raises(ValidationError):
        CaseFacts.model_validate(
            {"title": "t", "facts": [{"key": "a", "label": "A", "value": "x", "status": "unknown"}]}
        )
    with pytest.raises(ValidationError):
        CaseFacts.model_validate(
            {"title": "t", "facts": [{"key": "a", "label": "A", "status": "known"}]}
        )


def test_message_request_is_exactly_one_thing() -> None:
    assert MessageRequest(text="soru").mode == "short"
    assert MessageRequest(skip=True)
    for bad in ({}, {"text": "a", "skip": True}, {"text": ""}):
        with pytest.raises(ValidationError):
            MessageRequest.model_validate(bad)
    with pytest.raises(ValidationError):
        MessageRequest.model_validate({"clarification_answers": [{"question_id": "q1"}]})


def test_turn_roles() -> None:
    base = {"id": "00000000-0000-4000-8000-000000000000", "created_at": "2026-10-28T00:00:00Z"}
    Turn.model_validate({**base, "role": "user", "text": "soru"})
    with pytest.raises(ValidationError):
        Turn.model_validate({**base, "role": "assistant", "text": "soru"})
    with pytest.raises(ValidationError):
        Turn.model_validate({**base, "role": "assistant"})


# --- eval set ---------------------------------------------------------------------------------


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
def test_fixtures_get_full_marks(case_id: str) -> None:
    case = score_module.load_case(CASES / f"{case_id}.yaml")
    scenario = load(FIXTURES / f"{case_id}.scenario.json")
    clarification = score_module.load_clarification(FIXTURES / f"{case_id}.scenario.json")
    # the case's expected status is that of the skipped or the completed answer, whichever fits
    names = [scenario["on_skip"], scenario["on_complete"]]
    scored = [n for n in names if load(FIXTURES / n)["status"] == case["expected"]["status"]]
    assert scored
    for name in scored:
        metrics = score_module.score(load(FIXTURES / name), case, clarification)
        assert all(m.value == 1.0 for m in metrics), score_module.render(case_id, metrics)


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
