"""The topic templates: the question set of each topic is the template's, with sources and
without a progressive form."""

from collections.abc import Iterator
from typing import Any

import pytest

from agent.topics import GENERAL, get_topic, load_topics, parse_date
from hukuk_models.chat import QuestionInput
from hukuk_models.formal_turkish import progressive_forms

EXPECTED = {
    "ise_iade",
    "idari_para_cezasi",
    "hizmet_tespiti",
    "kidem_ihbar",
    "yillik_izin",
    GENERAL,
}


def test_the_templates_of_the_eval_topics_and_the_general_one_exist() -> None:
    assert set(load_topics()) == EXPECTED


def test_a_topic_without_a_template_gets_the_general_one() -> None:
    assert get_topic("sendika_tis").id == GENERAL
    assert get_topic(None).id == GENERAL
    assert get_topic("ise_iade").id == "ise_iade"


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif hasattr(node, "model_dump"):
        yield from _strings(node.model_dump())


@pytest.mark.parametrize("topic_id", sorted(EXPECTED))
def test_a_template_uses_the_formal_register(topic_id: str) -> None:
    assert progressive_forms(_strings(get_topic(topic_id))) == []


@pytest.mark.parametrize("topic_id", sorted(EXPECTED))
def test_every_asked_question_is_valid_input_and_every_critical_fact_is_asked(
    topic_id: str,
) -> None:
    for fact in get_topic(topic_id).facts:
        if fact.question is None:
            assert not fact.critical
            continue
        QuestionInput(
            kind=fact.question.kind,
            options=[{"value": o.value, "label": o.label} for o in fact.question.options],
        )
        assert fact.question.why


@pytest.mark.parametrize("topic_id", sorted(EXPECTED - {GENERAL}))
def test_a_topic_names_what_to_read(topic_id: str) -> None:
    topic = get_topic(topic_id)
    assert topic.must_read
    assert topic.queries
    assert topic.traps


def test_sb001_asks_what_the_eval_case_wants_asked() -> None:
    asked = [f.key for f in get_topic("ise_iade").facts if f.critical]
    assert asked == [
        "isci_sayisi",
        "sozlesme_turu",
        "bildirim_tarihi",
        "onceki_donem",
        "yer_alti",
        "kisaltma",
    ]
    assert get_topic("ise_iade").event_date_fact == "bildirim_tarihi"


def test_sb016_and_sb026_ask_what_the_eval_cases_want_asked() -> None:
    assert {f.key for f in get_topic("idari_para_cezasi").facts if f.critical} == {
        "ceza_turu",
        "kendiliginden",
    }
    assert {"hizmet_yillari", "bildirim_durumu"} <= {
        f.key for f in get_topic("hizmet_tespiti").facts if f.critical
    }


def test_parse_date_reads_iso_and_turkish_dates() -> None:
    assert parse_date("2026-10-03") == parse_date("03.10.2026")
    assert parse_date("dün") is None
    assert parse_date("31.02.2026") is None
