"""The holding map is checked by code: a row stays only on a read, valid source and a verbatim
quote."""

from datetime import date
from typing import Any

import pytest
from agent_fakes import M18_1, M18_4, hit, row

from agent.holding import Verified, verify_rows
from agent.llm_schemas import HoldingDraft
from agent.sources import as_read_source

READ = [
    s
    for s in [
        as_read_source(
            hit(
                "statute:4857:m18",
                "4857 m.18",
                "4857 sayılı İş Kanunu m.18",
                f"(1) {M18_1}",
                f"(4) {M18_4}",
            )
        ),
        as_read_source(
            hit(
                "statute:old",
                "4857 m.99",
                "Eski madde",
                "Bu hüküm artık yürürlükte değildir",
                valid_to=date(2020, 1, 1),
            )
        ),
    ]
    if s is not None
]
DAY = date(2026, 10, 3)


def verify(*rows: dict) -> Verified:  # type: ignore[type-arg]
    return verify_rows(HoldingDraft.model_validate({"rows": list(rows)}), READ, DAY)


def test_a_row_with_a_verbatim_quote_of_a_read_source_stays() -> None:
    rows, dropped, subs = verify(row("statute:4857:m18", M18_4, sub="4"))

    assert (dropped, subs) == ({}, 0)
    assert rows[0].citation.ref == "4857 m.18/4"
    assert rows[0].citation.quote == M18_4
    assert rows[0].citation.char_start is not None


def test_a_row_with_a_fabricated_quote_drops() -> None:
    rows, dropped, _ = verify(row("statute:4857:m18", "Bu ifade kanunda hiç geçmemektedir"))

    assert (rows, dropped) == ([], {"quote_not_found": 1})


def test_a_row_on_a_source_that_was_not_read_drops() -> None:
    assert verify(row("statute:4857:m19", M18_4))[:2] == ([], {"unread_source": 1})


def test_a_row_on_a_text_not_in_force_on_the_date_drops() -> None:
    assert verify(row("statute:old", "Bu hüküm artık yürürlükte değildir"))[:2] == (
        [],
        {"not_in_force": 1},
    )


def test_a_quote_too_short_to_prove_anything_drops() -> None:
    assert verify(row("statute:4857:m18", "işçinin"))[:2] == ([], {"short_quote": 1})


def test_the_good_rows_stay_when_others_drop() -> None:
    rows, dropped, _ = verify(
        row("statute:4857:m18", M18_4, "unknown"), row("statute:4857:m18", "uydurma bir alıntı yok")
    )

    assert len(rows) == 1 and dropped == {"quote_not_found": 1}
    assert rows[0].result == "unknown"


@pytest.mark.parametrize(
    ("sub", "ref"), [("4", "4857 m.18/4"), ("4-a", "4857 m.18"), (None, "4857 m.18")]
)
def test_a_quote_from_the_cited_paragraph_or_with_no_paragraph_claimed_stays(
    sub: str | None, ref: str
) -> None:
    rows, dropped, subs = verify(row("statute:4857:m18", M18_4, sub=sub))

    assert dropped == {}
    assert rows[0].citation.ref == ref
    # A lettered clause is cited at article level: the paragraph the model gave is counted.
    assert subs == (sub == "4-a")


@pytest.mark.parametrize("sub", ["1", "99", "1-a"])
def test_a_quote_from_another_paragraph_than_the_cited_one_drops(sub: str) -> None:
    # The words are in the article, but in its paragraph (4): they do not support paragraph `sub`.
    assert verify(row("statute:4857:m18", M18_4, sub=sub))[:2] == ([], {"other_paragraph": 1})


def test_a_quote_that_is_also_in_the_cited_paragraph_stays() -> None:
    twice = as_read_source(
        hit("statute:4857:m18", "4857 m.18", "4857 m.18", f"(1) {M18_4}", f"(4) {M18_4}")
    )
    assert twice is not None
    draft = HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_4, sub="4")]})

    rows, dropped, _ = verify_rows(draft, [twice], DAY)

    assert dropped == {}
    assert rows[0].citation.ref == "4857 m.18/4"


def test_an_empty_fact_value_is_no_unknown_fact() -> None:
    rows, dropped, _ = verify({**row("statute:4857:m18", M18_4, "met"), "fact_value": ""})

    assert dropped == {}
    assert (rows[0].fact_value, rows[0].result) == (None, "met")


def test_a_cited_paragraph_is_kept_at_article_level_when_the_text_read_has_no_markers() -> None:
    plain = READ[0].model_copy(
        update={"passages": [p.model_copy(update={"text": p.text[4:]}) for p in READ[0].passages]}
    )
    draft = HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_4, sub="1")]})

    rows, dropped, subs = verify_rows(draft, [plain], DAY)

    assert (dropped, subs) == ({}, 1)
    assert rows[0].citation.ref == "4857 m.18"


def test_informal_holding_text_is_dropped_before_it_can_reach_the_fallback() -> None:
    candidate = row("statute:4857:m18", M18_4)
    for field in ("condition", "fact_value"):
        assert verify({**candidate, field: "İşçi çalışıyordu"})[:2] == ([], {"progressive": 1})
    assert verify({**candidate, "condition": "Kıdem bilinmiyor"})[:2] == ([], {"progressive": 1})
    assert verify({**candidate, "fact_value": "Bilinmiyor; işçi çalışıyor"})[:2] == (
        [],
        {"progressive": 1},
    )


@pytest.mark.parametrize("result", ["met", "not_met", "unknown", "not_applicable"])
@pytest.mark.parametrize(
    ("value", "formal"),
    [
        ("bilinmiyor", "bilinmemektedir"),
        ("Bilinmiyor", "Bilinmemektedir"),
        ("Kıdem: 5 ay; işçi sayısı: bilinmiyor", "Kıdem: 5 ay; işçi sayısı: bilinmemektedir"),
    ],
)
def test_an_unknown_fact_value_keeps_the_row_as_a_conditional_branch(
    value: str, formal: str, result: str
) -> None:
    rows, dropped, _ = verify({**row("statute:4857:m18", M18_4, result), "fact_value": value})

    assert dropped == {}
    assert rows[0].fact_value == formal
    assert rows[0].result == ("unknown" if result in ("met", "not_met") else result)
    assert rows[0].condition_quote == M18_4


def test_the_expiry_day_is_not_a_valid_holding_source_date() -> None:
    draft = HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_1)]})
    expired = READ[0].model_copy(update={"valid_to": DAY})
    assert verify_rows(draft, [expired], DAY)[:2] == ([], {"not_in_force": 1})


def test_declared_dependencies_preserve_unknown_without_erasing_known_results() -> None:
    from agent.facts import build_facts
    from agent.llm_schemas import IntakeOutput
    from agent.topics import get_topic

    facts = build_facts(
        get_topic("ise_iade"),
        IntakeOutput.model_validate(
            {
                "topic": "ise_iade",
                "title": "Kıdem",
                "facts": [
                    {"key": "kidem", "value": "5 ay", "status": "known"},
                ],
            }
        ),
        None,
        question="5 ay",
        today=DAY,
    )
    for result in ("met", "not_met", "unknown", "not_applicable"):
        for dependencies, expected in (
            (["kidem"], result),
            (["kidem", "onceki_donem"], "unknown" if result in ("met", "not_met") else result),
        ):
            candidate = {**row("statute:4857:m18", M18_1, result), "depends_on_facts": dependencies}
            verified, dropped, _ = verify_rows(
                HoldingDraft.model_validate({"rows": [candidate]}), READ, DAY, facts=facts
            )
            assert dropped == {}
            assert verified[0].result == expected
            assert verified[0].condition_quote == M18_1


def test_a_dependency_key_the_template_does_not_have_is_found_and_its_row_drops() -> None:
    from agent.facts import build_facts
    from agent.holding import invented_keys
    from agent.llm_schemas import IntakeOutput
    from agent.topics import get_topic

    facts = build_facts(
        get_topic("ise_iade"),
        IntakeOutput.model_validate({"topic": "ise_iade", "title": "Kıdem", "facts": []}),
        None,
        question="",
        today=DAY,
    )
    good = {**row("statute:4857:m18", M18_1, "unknown"), "depends_on_facts": ["bildirim_tarihi"]}
    bad = {**good, "depends_on_facts": ["kidem", "fesih_bildirim_tarihi", "kisaltma", "x"]}
    draft = HoldingDraft.model_validate({"rows": [good, bad]})

    assert invented_keys(draft, facts) == ["fesih_bildirim_tarihi", "x"]
    assert invented_keys(HoldingDraft.model_validate({"rows": [good]}), facts) == []
    rows, dropped, _ = verify_rows(draft, READ, DAY, facts=facts)
    assert dropped == {"unknown_key": 1} and len(rows) == 1


# Sanitized typed outputs and the literal shown passage from the finished recorded run.
# No provider envelopes, identifiers, usage, credentials or private-file dependency.
def recorded_holding() -> dict[str, Any]:
    import json
    from pathlib import Path

    recording: dict[str, Any] = json.loads(
        (Path(__file__).parent / "fixtures/holding_register.json").read_text()
    )
    return recording


def test_recorded_unknown_rows_require_formal_generated_values_without_losing_data() -> None:
    from agent_fakes import draft

    from agent.gate import progressive_in
    from agent.llm_schemas import DraftOutput

    recording = recorded_holding()
    source = as_read_source(
        hit("statute:4857:m18", "4857 m.18", "4857 m.18", recording["source_text"])
    )
    assert source is not None
    original = HoldingDraft.model_validate(recording["holding"])
    assert len(original.rows) == 3
    # The recorded "bilinmiyor" is the unknown value of the fact, not a register error.
    recorded, dropped, _ = verify_rows(original, [source], DAY)
    assert dropped == {}
    assert [r.fact_value for r in recorded] == [
        (r.fact_value or "").replace("bilinmiyor", "bilinmemektedir") for r in original.rows
    ]
    assert [r.result for r in recorded] == ["unknown"] * 3
    for value in ("bilinmemektedir", "belirsiz"):
        formal = original.model_copy(deep=True)
        for candidate in formal.rows:
            assert candidate.fact_value is not None
            candidate.fact_value = candidate.fact_value.replace("bilinmiyor", value)
        rows, dropped, _ = verify_rows(formal, [source], DAY)
        assert dropped == {} and len(rows) == 3
        for before, after, verified in zip(original.rows, formal.rows, rows, strict=True):
            assert after.depends_on_facts == before.depends_on_facts
            assert after.condition_quote == before.condition_quote == verified.condition_quote
            assert after.condition == before.condition == verified.condition
            assert after.result == before.result == verified.result == "unknown"
            assert verified.fact_value is not None
            assert verified.fact_value == after.fact_value
            assert verified.fact_value.replace(value, "bilinmiyor") == before.fact_value
            assert verified.citation.quote == before.condition_quote
            # The excerpt has no paragraph marker: the recorded sub="1" is not verified.
            assert verified.citation.ref == "4857 m.18"
        assert progressive_in(DraftOutput.model_validate(draft()), rows) == []
        invalid = formal.model_copy(deep=True)
        for candidate in invalid.rows:
            candidate.condition = "Olgu bilinmiyor"
        assert verify_rows(invalid, [source], DAY)[:2] == ([], {"progressive": 3})


def test_a_row_is_dropped_under_the_first_reason_found() -> None:
    old = row("statute:old", "çalışıyor")
    rows, dropped, _ = verify(
        old, row("statute:4857:m18", "işçinin"), row("statute:4857:m18", M18_4)
    )

    assert len(rows) == 1
    assert dropped == {"not_in_force": 1, "short_quote": 1}


def test_the_correction_names_every_row_a_model_can_mend_and_no_other() -> None:
    from agent.holding import holding_feedback
    from hukuk_models.chat import CaseFacts, Fact

    facts = CaseFacts(title="Kıdem", facts=[Fact(key="kidem", label="Kıdem", status="unknown")])
    good = row("statute:4857:m18", M18_4, sub="4")
    draft = HoldingDraft.model_validate(
        {
            "rows": [
                good,
                {
                    **row("statute:4857:m18", "uydurma bir alıntı yok"),
                    "condition": "İşçi çalışıyor",
                },
                row("statute:4857:m18", M18_4, sub="1"),
                {**good, "depends_on_facts": ["isci_sayisi_x"]},
                row("statute:old", "Bu hüküm artık yürürlükte değildir"),
                row("statute:4857:m19", M18_4),
            ]
        }
    )

    feedback = holding_feedback(draft, READ, DAY, facts)

    assert feedback[0].startswith("depends_on_facts içinde olgu listesinde olmayan anahtar: isci_")
    assert len(feedback) == 3
    assert feedback[1].startswith("2. satır (statute:4857:m18, «uydurma bir alıntı yok»)")
    assert "birebir geçmemektedir" in feedback[1] and "(çalışıyor)" in feedback[1]
    assert feedback[2].startswith("3. satır") and "başka bir fıkradadır" in feedback[2]
    assert holding_feedback(HoldingDraft.model_validate({"rows": [good]}), READ, DAY, facts) == []
