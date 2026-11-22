"""Prompt data fidelity only; these tests do not prove model legal reasoning."""

import json
from datetime import date

from agent_fakes import M18_1, row
from test_holding import READ

from agent.holding import verify_rows
from agent.llm_schemas import HoldingDraft
from agent.prompts import HOLDING_INSTRUCTIONS, draft_prompt
from agent.topics import get_topic
from hukuk_models.chat import CaseFacts


def test_draft_receives_the_exact_inclusive_threshold_quote() -> None:
    rows, _, _, _ = verify_rows(
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


def test_an_unreviewed_source_is_labelled_as_a_test_source_in_the_prompt() -> None:
    from agent.prompts import sources_block

    unreviewed = READ[0].model_copy(
        update={"source_id": "analyzed:x", "review_status": "analyzed", "band": "high"}
    )

    approved_block, unreviewed_block = sources_block([READ[0], unreviewed]).split("\n\n")

    assert "onaysız (test)" in unreviewed_block.splitlines()[0]
    assert ", onaylı, " in approved_block.splitlines()[0]
    assert "onaysız" not in approved_block


def test_the_intake_prompt_tells_every_template_apart_and_lists_the_branches() -> None:
    from agent.prompts import intake_prompt
    from agent.topics import load_topics

    topics = load_topics()
    listing = json.loads(
        intake_prompt("Soru", topics, None).split("Konular:\n", 1)[1].split("\n\nSoru:", 1)[0]
    )
    by_id = {t["topic"]: t for t in listing}

    assert set(by_id) == set(topics)
    for topic in topics.values():
        assert by_id[topic.id]["baslik"] == topic.title
        assert by_id[topic.id]["kapsam"] == topic.description
    descriptions = [t.description for t in topics.values()]
    assert len(set(descriptions)) == len(descriptions)
    # Every fact with options is given with them, so that the intake picks one: free text for
    # such a fact counts as unknown.
    assert by_id["kidem_ihbar"]["secenekler"]["fesih_nedeni"]["askerlik"] == (
        "İşçi muvazzaf askerlik nedeniyle ayrıldı"
    )
    assert by_id["ise_iade"]["secenekler"]["isci_sayisi"] == {
        "lt_30": "30'dan az",
        "gte_30": "30 veya fazla",
    }
    assert "hizmet_suresi" not in by_id["kidem_ihbar"]["secenekler"]
    assert "kidem" not in by_id["ise_iade"]["secenekler"]


def test_the_general_template_is_offered_last_and_only_as_the_fallback() -> None:
    from agent.prompts import INTAKE_INSTRUCTIONS, intake_prompt
    from agent.topics import GENERAL, load_topics

    listing = json.loads(
        intake_prompt("Soru", load_topics(), None).split("Konular:\n", 1)[1].split("\n\nSoru:")[0]
    )

    # Round 2: listed second, with a scope naming the whole field, it took SB-008 and SB-032.
    assert [t["topic"] for t in listing][-1] == GENERAL
    assert listing[-1]["kapsam"].startswith("Listedeki öteki konuların hiçbirinin kapsamına")
    assert "kapsamı soruya en yakın konuyu seç" in INTAKE_INSTRUCTIONS


def test_the_instructions_themselves_use_no_progressive_form() -> None:
    import re

    from agent import prompts
    from hukuk_models.formal_turkish import progressive_forms

    for name in ("INTAKE", "HOLDING", "DRAFT", "REWRITE"):
        text = getattr(prompts, f"{name}_INSTRUCTIONS")
        # The forbidden forms are named as quoted examples ("yapılıyor") or as suffixes
        # (-iyorsa); every other word is the register the model is to copy.
        own = re.sub(r'"[^"]*"|(?<!\w)-\w+', "", text)
        assert progressive_forms([own]) == [], name


def test_the_draft_is_told_to_cite_the_paragraph_and_to_state_the_rule_not_the_trap() -> None:
    from agent.prompts import DRAFT_INSTRUCTIONS

    assert '"(N)" fıkra işareti' in DRAFT_INSTRUCTIONS
    assert "sub alanına o fıkranın numarasını yaz" in DRAFT_INSTRUCTIONS
    assert "tuzak notlarını ve ayrımları cevaba yazma" in " ".join(DRAFT_INSTRUCTIONS.split())
    assert "olumlu kuralı yaz" in DRAFT_INSTRUCTIONS


def test_the_draft_prompt_forbids_joining_quote_pieces() -> None:
    # Round 4 SB-008: a quote stitched with "[...]" is in no source and dropped the only row.

    assert '"[...]"' in HOLDING_INSTRUCTIONS and "kesintisiz" in HOLDING_INSTRUCTIONS
