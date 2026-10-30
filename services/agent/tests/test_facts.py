"""The facts and the clarification, from the template: who is asked what, and how an answer fills
the fact."""

from datetime import date

import pytest

from agent.facts import (
    apply_answers,
    build_facts,
    clarification_for,
    critical_unknown,
    event_date_of,
    stated_in,
)
from agent.llm_schemas import IntakeFact, IntakeOutput
from agent.topics import Topic, get_topic
from hukuk_models.chat import CaseFacts, ClarificationAnswer

TOPIC = get_topic("ise_iade")


def intake(*facts: IntakeFact, event: date | None = None) -> IntakeOutput:
    return IntakeOutput(topic="ise_iade", title="İşe iade", event_date=event, facts=list(facts))


TODAY = date(2026, 10, 28)


def build(
    topic: Topic, extracted: IntakeOutput, previous: CaseFacts | None, question: str = ""
) -> CaseFacts:
    return build_facts(topic, extracted, previous, question=question, today=TODAY)


KIDEM = IntakeFact(key="kidem", value="5 ay", status="known")


def statuses(facts: CaseFacts) -> dict[str, str]:
    return {f.key: f.status for f in facts.facts}


def test_the_facts_are_the_templates_and_what_the_question_does_not_say_is_unknown() -> None:
    facts = build(TOPIC, intake(KIDEM), None)

    assert [f.key for f in facts.facts] == [f.key for f in TOPIC.facts]
    assert statuses(facts)["kidem"] == "known"
    assert statuses(facts)["isci_sayisi"] == "unknown"
    assert facts.title == "İşe iade"


def test_a_fact_the_model_invents_is_left_out() -> None:
    facts = build(TOPIC, intake(IntakeFact(key="maas", value="50.000", status="known")), None)

    assert "maas" not in statuses(facts)


def test_a_value_that_is_an_option_becomes_the_options_label() -> None:
    facts = build(
        TOPIC, intake(IntakeFact(key="sozlesme_turu", value="belirsiz", status="known")), None
    )

    fact = next(f for f in facts.facts if f.key == "sozlesme_turu")
    assert (fact.value, fact.status) == ("Belirsiz süreli", "known")


def test_assumed_never_needs_the_users_word_for_it() -> None:
    said = IntakeFact(key="yer_alti", value="Yer altı işi değil", status="assumed_never")
    silent = IntakeFact(key="onceki_donem", value=None, status="assumed_never")

    facts = build(TOPIC, intake(said, silent), None)

    assert statuses(facts)["yer_alti"] == "assumed_never"
    assert statuses(facts)["onceki_donem"] == "unknown"


def test_earlier_turns_fill_what_this_question_does_not_say() -> None:
    first = build(TOPIC, intake(KIDEM), None)
    again = build(TOPIC, intake(), first)

    assert statuses(again)["kidem"] == "known"


def test_only_unknown_critical_facts_are_asked_in_the_order_of_the_template() -> None:
    facts = build(
        TOPIC, intake(KIDEM, IntakeFact(key="isci_sayisi", value="45", status="known")), None
    )

    assert critical_unknown(TOPIC, facts) == [
        "sozlesme_turu",
        "bildirim_tarihi",
        "onceki_donem",
        "yer_alti",
        "kisaltma",
    ]
    clarification = clarification_for(TOPIC, facts, {})
    assert clarification is not None
    assert [q.id for q in clarification.questions] == ["q1", "q2", "q3", "q4", "q5"]
    assert clarification.questions[0].text == "İş sözleşmesi belirsiz süreli mi?"
    assert clarification.questions[0].input.allow_unknown
    assert clarification.questions[0].source_refs == []


def test_nothing_is_asked_when_every_critical_fact_is_known() -> None:
    every = [
        IntakeFact(key=k, value="03.10.2026" if k == "bildirim_tarihi" else "x", status="known")
        for k in [f.key for f in TOPIC.facts]
    ]
    facts = build(TOPIC, intake(*every), None, "03.10.2026")

    assert clarification_for(TOPIC, facts, {}) is None


def test_answers_fill_the_facts_and_the_date_answer_is_the_event_date() -> None:
    facts = build(TOPIC, intake(KIDEM), None)
    clarification = clarification_for(TOPIC, facts, {})
    assert clarification is not None
    answers = [
        ClarificationAnswer(question_id="q1", value="gte_30"),
        ClarificationAnswer(question_id="q2", value="belirsiz"),
        ClarificationAnswer(question_id="q3", value="2026-10-03"),
        ClarificationAnswer(question_id="q4", value="hayir"),
        ClarificationAnswer(question_id="q5", unknown=True),
    ]

    done = apply_answers(TOPIC, clarification, answers, facts)

    by_key = {f.key: f for f in done.facts}
    assert by_key["isci_sayisi"].value == "30 veya fazla"
    assert by_key["bildirim_tarihi"].value == "03.10.2026"
    assert (by_key["onceki_donem"].value, by_key["onceki_donem"].status) == (
        "Hayır",
        "assumed_never",
    )
    assert by_key["yer_alti"].status == "unknown"
    assert done.event_date == date(2026, 10, 3)
    assert event_date_of(TOPIC, done.facts) == date(2026, 10, 3)


def test_an_answer_that_is_no_option_and_no_date_leaves_the_fact_unknown() -> None:
    facts = build(TOPIC, intake(KIDEM), None)
    clarification = clarification_for(TOPIC, facts, {})
    assert clarification is not None
    answers = [
        ClarificationAnswer(question_id="q1", value="belki"),
        ClarificationAnswer(question_id="q3", value="geçen hafta"),
        ClarificationAnswer(question_id="q99", value="x"),
    ]

    done = apply_answers(TOPIC, clarification, answers, facts)

    assert statuses(done)["isci_sayisi"] == "unknown"
    assert statuses(done)["bildirim_tarihi"] == "unknown"
    assert done.event_date is None


def test_an_event_date_the_question_names_is_kept() -> None:
    facts = build(
        TOPIC, intake(KIDEM, event=date(2026, 10, 3)), None, "Fesih 3 Ekim 2026 günü oldu"
    )

    assert facts.event_date == date(2026, 10, 3)


@pytest.mark.parametrize(
    ("event", "question"),
    [
        (date(2026, 10, 3), "Fesih geçen hafta oldu"),
        (date(2027, 1, 5), "Fesih 05.01.2027 tarihinde olacak"),
        (date(2026, 10, 13), "Fesih 3.10.2026 günü oldu"),
    ],
)
def test_an_event_date_the_question_does_not_name_or_in_the_future_is_unknown(
    event: date, question: str
) -> None:
    assert build(TOPIC, intake(KIDEM, event=event), None, question).event_date is None


@pytest.mark.parametrize(
    "text", ["3.10.2026", "03/10/2026", "2026-10-03", "3 ekim 2026", "03 Ekim 2026"]
)
def test_the_forms_of_a_date_in_a_question(text: str) -> None:
    assert stated_in(date(2026, 10, 3), f"Fesih {text} günüdür")


@pytest.mark.parametrize("value", ["2027-01-05", "2026-10-13", "invalid"])
def test_date_fact_cannot_bypass_the_event_date_grounding(value: str) -> None:
    out = intake(IntakeFact(key="bildirim_tarihi", value=value, status="known"))
    facts = build(TOPIC, out, None, "Bildirim 3.10.2026 günü yapıldı; 05.01.2027 gelecek tarihtir")
    assert facts.event_date is None
    assert statuses(facts)["bildirim_tarihi"] == "unknown"
    assert "bildirim_tarihi" in critical_unknown(TOPIC, facts)


def test_a_future_clarification_date_stays_unknown_and_clears_the_old_event_date() -> None:
    facts = build(TOPIC, intake(), None).model_copy(update={"event_date": date(2020, 1, 1)})
    clarification = clarification_for(TOPIC, facts, {})
    assert clarification is not None
    done = apply_answers(
        TOPIC,
        clarification,
        [ClarificationAnswer(question_id="q3", value="2027-01-05")],
        facts,
        today=TODAY,
    )
    assert done.event_date is None
    assert statuses(done)["bildirim_tarihi"] == "unknown"


@pytest.mark.parametrize(
    ("event", "value", "status", "question", "expected"),
    [
        (
            date(2024, 1, 1),
            None,
            None,
            "Düzeltme: bildirim 2024-01-01 tarihinde ulaştı.",
            date(2024, 1, 1),
        ),
        (
            date(2027, 1, 5),
            "2027-01-05",
            "known",
            "Düzeltme: bildirim tarihi 2027-01-05 olacak.",
            None,
        ),
        (date(2027, 1, 5), None, None, "Düzeltme: bildirim tarihi 2027-01-05 olacak.", None),
        (None, "2024-01-01", "known", "Düzeltme: bildirim 2024-01-01.", date(2024, 1, 1)),
        (None, "2024-01-01", "known", "Düzeltme: bildirim geçen hafta.", None),
        (None, "invalid", "known", "Düzeltme: bildirim tarihi geçersiz.", None),
        (None, None, "unknown", "Düzeltme: bildirim tarihini bilmiyorum.", None),
        (date(2024, 1, 1), "2023-01-01", "known", "Bildirim 2024-01-01 veya 2023-01-01.", None),
        (None, None, None, "İşçi sayısı 45.", date(2020, 1, 1)),
    ],
)
def test_date_corrections_replace_or_invalidate_previous_dates(
    event: date | None, value: str | None, status: str | None, question: str, expected: date | None
) -> None:
    from agent.plan import make_plan

    old = build(
        TOPIC,
        intake(
            IntakeFact(key="bildirim_tarihi", value="2020-01-01", status="known"),
            event=date(2020, 1, 1),
        ),
        None,
        "Bildirim 2020-01-01",
    )
    supplied = (
        []
        if status is None
        else [
            IntakeFact.model_validate({"key": "bildirim_tarihi", "value": value, "status": status})
        ]
    )
    new = build(TOPIC, intake(*supplied, event=event), old, question)
    fact = next(f for f in new.facts if f.key == "bildirim_tarihi")
    assert new.event_date == event_date_of(TOPIC, new.facts) == expected
    assert fact.status == ("unknown" if expected is None else "known")
    if expected is None:
        assert fact.value is None
    clarification = clarification_for(TOPIC, new, {})
    assert clarification is not None
    assert any(q.fact_key == "bildirim_tarihi" for q in clarification.questions) == (
        expected is None
    )
    plan = make_plan(TOPIC, question, new, TODAY)
    assert plan.as_of == (expected or TODAY)
    assert plan.as_of_assumed == (expected is None)
