"""Prompt data fidelity only; these tests do not prove model legal reasoning."""

import json
from datetime import date

from agent_fakes import M18_1, row
from test_holding import READ

from agent.holding import verify_rows
from agent.llm_schemas import HoldingDraft
from agent.prompts import draft_prompt
from agent.topics import get_topic
from hukuk_models.chat import CaseFacts


def test_draft_receives_the_exact_inclusive_threshold_quote() -> None:
    rows, _ = verify_rows(
        HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_1, "unknown")]}),
        READ,
        date(2026, 10, 3),
    )
    prompt = draft_prompt(
        get_topic("ise_iade"),
        CaseFacts(title="Kıdem", facts=[]),
        rows,
        READ,
        [],
        [],
        question="Kıdem şartı?",
    )
    payload = prompt.split("Hüküm haritası:\n", 1)[1].split("\n\n", 1)[0]
    assert json.loads(payload)[0]["condition_quote"] == M18_1
    assert "en az altı aylık" in M18_1


def test_holding_register_contract_covers_generated_fields_and_preserves_verbatim_data() -> None:
    from agent.prompts import HOLDING_INSTRUCTIONS, holding_prompt
    from hukuk_models.chat import Fact

    assert "condition ve fact_value" in HOLDING_INSTRUCTIONS
    assert '"bilinmiyor" yerine "bilinmemektedir" veya "belirsiz"' in HOLDING_INSTRUCTIONS
    assert "result=unknown ve depends_on_facts" in HOLDING_INSTRUCTIONS
    assert (
        "condition_quote ve kullanıcıdan alınan özgün olgu metnini değiştirme"
        in HOLDING_INSTRUCTIONS
    )
    original = "Çalışıyorum; önceki dönemimi bilmiyorum."
    source = READ[0].model_copy(
        update={"passages": [READ[0].passages[0].model_copy(update={"text": original})]}
    )
    facts = CaseFacts(
        title="Olgu", facts=[Fact(key="kidem", label="Kıdem", value=original, status="known")]
    )
    prompt = holding_prompt(get_topic("ise_iade"), facts, [source], question=original)
    assert json.loads(prompt.split("\n", 1)[1].split("\n\n", 1)[0]) == original
    payload = prompt.split("Olgular:\n", 1)[1].split("\n\n", 1)[0]
    assert json.loads(payload)["olgular"][0]["value"] == original
    assert prompt.endswith(original)
