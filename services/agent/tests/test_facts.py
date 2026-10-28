"""The facts and the clarification, from the template: who is asked what, and how an answer fills
the fact."""

from datetime import date

from agent.facts import (
    apply_answers,
    build_facts,
    clarification_for,
    critical_unknown,
    event_date_of,
)
from agent.llm_schemas import IntakeFact, IntakeOutput
from agent.topics import get_topic
from hukuk_models.chat import CaseFacts, ClarificationAnswer

TOPIC = get_topic("ise_iade")


def intake(*facts: IntakeFact, event: date | None = None) -> IntakeOutput:
    return IntakeOutput(topic="ise_iade", title="İşe iade", event_date=event, facts=list(facts))


KIDEM = IntakeFact(key="kidem", value="5 ay", status="known")


def statuses(facts: CaseFacts) -> dict[str, str]:
    return {f.key: f.status for f in facts.facts}


def test_the_facts_are_the_templates_and_what_the_question_does_not_say_is_unknown() -> None:
    facts = build_facts(TOPIC, intake(KIDEM), None)

    assert [f.key for f in facts.facts] == [f.key for f in TOPIC.facts]
    assert statuses(facts)["kidem"] == "known"
    assert statuses(facts)["isci_sayisi"] == "unknown"
    assert facts.title == "İşe iade"


def test_a_fact_the_model_invents_is_left_out() -> None:
    facts = build_facts(TOPIC, intake(IntakeFact(key="maas", value="50.000", status="known")), None)

    assert "maas" not in statuses(facts)


def test_a_value_that_is_an_option_becomes_the_options_label() -> None:
    facts = build_facts(
        TOPIC, intake(IntakeFact(key="sozlesme_turu", value="belirsiz", status="known")), None
    )

    fact = next(f for f in facts.facts if f.key == "sozlesme_turu")
    assert (fact.value, fact.status) == ("Belirsiz süreli", "known")


def test_assumed_never_needs_the_users_word_for_it() -> None:
    said = IntakeFact(key="yer_alti", value="Yer altı işi değil", status="assumed_never")
    silent = IntakeFact(key="onceki_donem", value=None, status="assumed_never")

    facts = build_facts(TOPIC, intake(said, silent), None)

    assert statuses(facts)["yer_alti"] == "assumed_never"
    assert statuses(facts)["onceki_donem"] == "unknown"


def test_earlier_turns_fill_what_this_question_does_not_say() -> None:
    first = build_facts(TOPIC, intake(KIDEM), None)
    again = build_facts(TOPIC, intake(), first)

    assert statuses(again)["kidem"] == "known"


def test_only_unknown_critical_facts_are_asked_in_the_order_of_the_template() -> None:
    facts = build_facts(
        TOPIC, intake(KIDEM, IntakeFact(key="isci_sayisi", value="45", status="known")), None
    )

    assert critical_unknown(TOPIC, facts) == [
        "sozlesme_turu",
        "bildirim_tarihi",
        "onceki_donem",
        "yer_alti",
    ]
    clarification = clarification_for(TOPIC, facts, {})
    assert clarification is not None
    assert [q.id for q in clarification.questions] == ["q1", "q2", "q3", "q4"]
    assert clarification.questions[0].text == "İş sözleşmesi belirsiz süreli mi?"
    assert clarification.questions[0].input.allow_unknown
    assert clarification.questions[0].source_refs == []


def test_nothing_is_asked_when_every_critical_fact_is_known() -> None:
    every = [IntakeFact(key=k, value="x", status="known") for k in [f.key for f in TOPIC.facts]]
    facts = build_facts(TOPIC, intake(*every), None)

    assert clarification_for(TOPIC, facts, {}) is None


def test_answers_fill_the_facts_and_the_date_answer_is_the_event_date() -> None:
    facts = build_facts(TOPIC, intake(KIDEM), None)
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
    facts = build_facts(TOPIC, intake(KIDEM), None)
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
