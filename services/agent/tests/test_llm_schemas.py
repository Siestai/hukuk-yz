"""Request-local draft contracts; these tests do not establish legal source support."""

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from agent.llm_schemas import DraftOutput, draft_output_type
from agent.topics import Topic, get_topic
from hukuk_models.chat import CaseFacts, Fact


def payload(*keys: str | None) -> dict[str, Any]:
    return {
        "status": "conditional",
        "headline": "Koşulludur.",
        "points": [{"text": "Belirlenmelidir.", "citations": [{"source_id": "s", "quote": "q"}]}],
        "missing_info": [
            {"fact_key": k, "condition": "Bilinmezse", "result": "Belirsizdir."} for k in keys
        ],
        "reasoning_summary": "Eksiktir.",
    }


def case(**statuses: str) -> CaseFacts:
    return CaseFacts(
        title="Olay",
        facts=[
            Fact(key=k, label=k, status=v, value=None if v == "unknown" else "verildi")
            for k, v in statuses.items()
        ],
    )


def test_request_keys_coverage_and_isolation() -> None:
    topic = get_topic("ise_iade")
    facts = case(
        bildirim_tarihi="unknown", kisaltma="unknown", kidem="known", yer_alti="assumed_never"
    )
    contract = draft_output_type(topic, facts)
    with pytest.raises(ValidationError, match="kisaltma"):
        contract.model_validate(payload("bildirim_tarihi"))
    assert contract.model_validate(payload("bildirim_tarihi", "kisaltma", None))
    all_unknown = case(**{f.key: "unknown" for f in topic.facts})
    full = draft_output_type(topic, all_unknown)
    assert full.model_validate(payload(*(f.key for f in topic.facts if f.critical)))
    independent = draft_output_type(get_topic("genel"), case())
    with pytest.raises(ValidationError):
        independent.model_validate(payload("bildirim_tarihi"))
    assert contract.model_validate(payload("bildirim_tarihi", "kisaltma"))
    # Static public draft remains compatible, including arbitrary strings.
    assert DraftOutput.model_validate(payload("arbitrary"))


def test_empty_topic_is_null_only_and_general_uses_its_own_keys() -> None:
    empty = Topic(id="empty", title="Boş", description="Boş", facts=[])
    contract = draft_output_type(empty, case())
    assert contract.model_validate(payload(None))
    assert contract.model_validate(payload())
    with pytest.raises(ValidationError):
        contract.model_validate(payload("olay_tarihi"))
    general = draft_output_type(get_topic("genel"), case(olay_tarihi="unknown", statu="unknown"))
    assert general.model_validate(payload("olay_tarihi", "statu"))
    with pytest.raises(ValidationError):
        general.model_validate(payload(None))


@pytest.mark.parametrize(
    "change", ["key", "citation", "quote", "sub", "status", "point_count", "missing_count"]
)
def test_rewrite_preserves_identifiers_citations_and_structure(change: str) -> None:
    topic = get_topic("ise_iade")
    original = DraftOutput.model_validate(payload("bildirim_tarihi"))
    contract = draft_output_type(topic, case(), original=original)
    changed = deepcopy(original.model_dump())
    if change == "key":
        changed["missing_info"][0]["fact_key"] = "kisaltma"
    elif change in {"citation", "quote", "sub"}:
        field = "source_id" if change == "citation" else change
        changed["points"][0]["citations"][0][field] = "changed"
    elif change == "status":
        changed["status"] = "definite"
    elif change == "point_count":
        changed["points"].append(deepcopy(changed["points"][0]))
    else:
        changed["missing_info"] = []
    with pytest.raises(ValidationError, match="Rewrite changed"):
        contract.model_validate(changed)
    allowed = original.model_dump()
    allowed["headline"] = "Düzeltilmiştir."
    allowed["points"][0]["text"] = "Düzeltilmiştir."
    allowed["points"][0]["citations"][0]["used_for"] = "Açıklama"
    allowed["missing_info"][0]["condition"] = "Bilinmemekteyse"
    assert contract.model_validate(allowed)


def test_invented_fact_key_is_rejected_by_actual_parser() -> None:
    from agent_fakes import draft

    output_type = draft_output_type(get_topic("ise_iade"), CaseFacts(title="Olay", facts=[]))
    payload = draft(missing=False)
    payload["missing_info"] = [
        {
            "fact_key": "fesih_olayinin_varligi_ve_bildirim_tarihi",
            "condition": "Belirsizdir.",
            "result": "Belirlenememektedir.",
        }
    ]
    with pytest.raises(ValidationError):
        output_type.model_validate(payload)


def test_single_fact_topic_also_exposes_an_enum() -> None:
    from agent.topics import TopicFact

    topic = Topic(
        id="one", title="Tek", description="Tek", facts=[TopicFact(key="key", label="Olgu")]
    )
    contract = draft_output_type(topic, case())
    schema = contract.model_json_schema()
    variants = schema["$defs"]["RequestMissingDraft"]["properties"]["fact_key"]["anyOf"]
    assert any(branch.get("enum") == ["key"] for branch in variants)
    assert contract.model_validate(payload("key", None))
    with pytest.raises(ValidationError):
        contract.model_validate(payload("invented"))
