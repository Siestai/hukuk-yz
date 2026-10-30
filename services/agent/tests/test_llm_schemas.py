"""Request-local draft contracts; these tests do not establish legal source support."""

import json
from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from agent.llm_schemas import DraftOutput, draft_output_type
from agent.topics import Topic, TopicFact, get_topic
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


def test_critical_coverage_is_required_in_generation_schema() -> None:
    contract = draft_output_type(
        get_topic("ise_iade"), case(bildirim_tarihi="unknown", kisaltma="unknown", kidem="known")
    )
    schema = contract.model_json_schema()
    assert "missing_info" in schema["required"]
    assert schema["properties"]["missing_info"] == {
        "$ref": "#/$defs/MissingInfoCoverage",
        "title": "Missing Info",
    }
    coverage = schema["$defs"]["MissingInfoCoverage"]
    assert "critical" in coverage["required"]
    critical = schema["$defs"]["CriticalMissingInfo"]
    assert set(critical["required"]) == {"bildirim_tarihi", "kisaltma"}
    assert set(critical["properties"]) == {"bildirim_tarihi", "kisaltma"}
    assert critical["additionalProperties"] is False


def test_wire_conversion_is_lossless_and_rewrite_preserves_order() -> None:
    facts = case(bildirim_tarihi="unknown", kisaltma="unknown")
    original_data = payload(None, "kisaltma", "bildirim_tarihi", "kisaltma")
    for index, entry in enumerate(original_data["missing_info"]):
        entry["condition"] = f"Koşul {index} bilinmezse"
        entry["result"] = f"Sonuç {index} belirsizdir."
        entry["citations"] = [{"source_id": f"source-{index}", "quote": f"quote-{index}"}]
    original = DraftOutput.model_validate(original_data)
    contract = draft_output_type(get_topic("ise_iade"), facts, original=original)
    data = original.model_dump()
    entries = data["missing_info"]
    data["missing_info"] = {
        "critical": {"bildirim_tarihi": entries[2], "kisaltma": entries[1]},
        "additional": [entries[0], entries[3]],
    }
    assert contract.model_validate_json(json.dumps(data)).model_dump() == original.model_dump()
    changed_citation = deepcopy(data)
    changed_citation["missing_info"]["additional"][1]["citations"][0]["quote"] = "changed"
    with pytest.raises(ValidationError, match="Rewrite changed"):
        contract.model_validate(changed_citation)
    changed_order = deepcopy(data)
    critical = changed_order["missing_info"]["critical"]
    additional = changed_order["missing_info"]["additional"]
    critical["kisaltma"], additional[1] = additional[1], critical["kisaltma"]
    with pytest.raises(ValidationError, match="Rewrite changed"):
        contract.model_validate(changed_order)
    changed = deepcopy(data)
    changed["missing_info"]["critical"]["kisaltma"]["fact_key"] = None
    with pytest.raises(ValidationError):
        contract.model_validate(changed)


async def test_concurrent_request_schema_isolation() -> None:
    import asyncio

    async def parse(key: str) -> None:
        contract = draft_output_type(get_topic("ise_iade"), case(**{key: "unknown"}))
        await asyncio.sleep(0)
        schema = contract.model_json_schema()
        assert schema["$defs"]["CriticalMissingInfo"]["required"] == [key]
        entry = payload(key)["missing_info"][0]
        data = payload()
        data["missing_info"] = {"critical": {key: entry}}
        assert contract.model_validate(data).missing_info[0].fact_key == key
        other = "kisaltma" if key == "bildirim_tarihi" else "bildirim_tarihi"
        data["missing_info"] = {"critical": {other: entry}}
        with pytest.raises(ValidationError):
            contract.model_validate(data)

    await asyncio.gather(parse("bildirim_tarihi"), parse("kisaltma"))


def test_known_and_general_generation_shapes() -> None:
    topic = get_topic("ise_iade")
    known = draft_output_type(topic, case(**{f.key: "known" for f in topic.facts}))
    assert known.model_json_schema()["properties"]["missing_info"]["type"] == "array"
    assert known.model_validate(payload()).missing_info == []
    noncritical = Topic(
        id="noncritical",
        title="Olgu",
        description="Olgu",
        facts=[TopicFact(key="key", label="Olgu", critical=False)],
    )
    optional = draft_output_type(noncritical, case(key="unknown"))
    assert optional.model_json_schema()["properties"]["missing_info"]["type"] == "array"
    assert optional.model_validate(payload("key"))
    general = draft_output_type(get_topic("genel"), case(olay_tarihi="unknown", statu="known"))
    data = payload()
    entry = payload("olay_tarihi")["missing_info"][0]
    data["missing_info"] = {"critical": {"olay_tarihi": entry}, "additional": []}
    assert general.model_validate(data).missing_info[0].fact_key == "olay_tarihi"
    data["missing_info"]["critical"]["invented"] = entry
    with pytest.raises(ValidationError):
        general.model_validate(data)


def test_additional_entries_cannot_replace_required_critical_properties() -> None:
    contract = draft_output_type(get_topic("ise_iade"), case(kisaltma="unknown"))
    data = payload()
    entry = payload("kisaltma")["missing_info"][0]
    for critical in ({}, {"kisaltma": None}):
        data["missing_info"] = {"critical": critical, "additional": [entry]}
        with pytest.raises(ValidationError):
            contract.model_validate(data)
    data["missing_info"] = {
        "critical": {"kisaltma": entry},
        "additional": payload("invented")["missing_info"],
    }
    with pytest.raises(ValidationError):
        contract.model_validate(data)
