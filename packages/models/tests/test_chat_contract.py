"""The chat contract (task 15): the schema validators and the hand-made fixtures against them."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from hukuk_models.chat import (
    Answer,
    CaseFacts,
    ChatEvent,
    Clarification,
    MessageRequest,
    Turn,
)

FIXTURES = Path(__file__).parents[3] / "eval" / "fixtures"
IDS = ["SB-001", "SB-016", "SB-026"]


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
