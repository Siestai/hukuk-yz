"""The topic templates: the question set of each topic is the template's, with sources and
without a progressive form; each eval case falls into its template and is asked what it wants."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from agent.facts import build_facts, clarification_for, follow_up
from agent.llm_schemas import IntakeFact, IntakeOutput
from agent.topics import GENERAL, TOPICS_DIR, Topic, get_topic, load_topics, parse_date
from hukuk_models.chat import CaseFacts, QuestionInput
from hukuk_models.formal_turkish import progressive_forms

EXPECTED = {
    "calisma_kosulu_degisikligi",
    "grev_lokavt",
    "hakli_fesih_devamsizlik",
    "hizmet_tespiti",
    "idari_para_cezasi",
    "ise_iade",
    "kidem_ihbar",
    "olum_yaslilik_aylik",
    "sgk_bildirim_prim",
    "tis_sendikal",
    "ucret_turu",
    "yillik_izin",
    GENERAL,
}
EVAL = Path(__file__).parents[3] / "eval"
CASES = {
    case["id"]: case
    for case in (
        yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in sorted((EVAL / "cases").glob("*.yaml"))
    )
}
# The raw intake output of the first real eval run, one file per case (task 19, B5).
INTAKE_RECORDS = EVAL / "fixtures" / "intake"


def test_the_templates_of_the_eval_topics_and_the_general_one_exist() -> None:
    assert set(load_topics()) == EXPECTED


def test_a_topic_without_a_template_gets_the_general_one() -> None:
    assert get_topic("sendika_tis").id == GENERAL
    assert get_topic(None).id == GENERAL
    assert get_topic("ise_iade").id == "ise_iade"


# What a user reads (the question card, the facts panel) or the model takes as a rule; option
# values, keys and search queries are identifiers and words of the sources.
VISIBLE = {"title", "description", "label", "text", "why", "traps", "needs"}


def _visible(node: Any, key: str = "") -> Iterator[str]:
    if isinstance(node, str):
        if key in VISIBLE:
            yield node
    elif isinstance(node, list):
        for item in node:
            yield from _visible(item, key)
    elif isinstance(node, dict):
        for name, value in node.items():
            yield from _visible(value, name)


@pytest.mark.parametrize("path", sorted(TOPICS_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_a_template_uses_the_formal_register(path: Path) -> None:
    assert progressive_forms(_visible(yaml.safe_load(path.read_text(encoding="utf-8")))) == []


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


def _topic(*facts: dict[str, Any]) -> Topic:
    return Topic.model_validate(
        {"id": "t", "title": "T", "description": "T.", "facts": list(facts)}
    )


BRANCH = {
    "key": "dal",
    "label": "Dal",
    "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
}


def _conditional(asked_when: dict[str, list[str]], *, critical: bool = True) -> dict[str, Any]:
    return {
        "key": "olgu",
        "label": "Olgu",
        "critical": critical,
        "asked_when": asked_when,
        "question": {"text": "Olgu?", "why": "Gerekir.", "kind": "text"},
    }


ASKED_BRANCH: dict[str, Any] = {
    "key": "dal",
    "label": "Dal",
    "critical": True,
    "question": {
        "text": "Dal?",
        "why": "Gerekir.",
        "kind": "choice",
        "options": [{"value": "a", "label": "A"}],
    },
}


def test_a_condition_names_a_branch_fact_and_its_options() -> None:
    topic = _topic(BRANCH, _conditional({"dal": ["a", "unknown"]}))
    assert topic.facts[1].asked_when == {"dal": ["a", "unknown"]}
    # A branch fact that is asked while unknown may open its facts on one value only.
    assert _topic(ASKED_BRANCH, _conditional({"dal": ["a"]})).facts[1].asked_when == {"dal": ["a"]}


@pytest.mark.parametrize(
    ("facts", "error"),
    [
        ((BRANCH, _conditional({"yok": ["a"]})), "no fact yok"),
        ((BRANCH, _conditional({"dal": ["c"]})), "not an option of dal"),
        ((BRANCH, _conditional({"dal": []})), "no value"),
        ((BRANCH, _conditional({"dal": ["a"]}, critical=False)), "for a critical fact only"),
        (({"key": "dal", "label": "Dal"}, _conditional({"dal": ["a"]})), "dal has no options"),
        ((_conditional({"olgu": ["a"]}),), "itself"),
        # Never asked and not listing "unknown": the fact would drop silently.
        ((BRANCH, _conditional({"dal": ["a"]})), "never asked"),
        (
            (
                {**ASKED_BRANCH, "key": "ust", "question": {**ASKED_BRANCH["question"]}},
                {**ASKED_BRANCH, "asked_when": {"ust": ["a"]}},
                _conditional({"dal": ["a"]}),
            ),
            "never asked",
        ),
        (
            (
                {"key": "dal", "label": "Dal", "options": [{"value": "unknown", "label": "?"}]},
                _conditional({"dal": ["unknown"]}),
            ),
            "the unknown state",
        ),
        (
            (
                {
                    "key": "dal",
                    "label": "Dal",
                    "options": [{"value": "a", "label": "A"}],
                    "question": {
                        "text": "Dal?",
                        "why": "Gerekir.",
                        "kind": "choice",
                        "options": [{"value": "a", "label": "A"}],
                    },
                },
            ),
            "options of its question",
        ),
    ],
)
def test_a_condition_on_no_such_fact_or_value_is_refused(
    facts: tuple[dict[str, Any], ...], error: str
) -> None:
    with pytest.raises(ValidationError, match=error):
        _topic(*facts)


# What each eval question states of the facts that steer the template, as the intake is to read
# it; the rest of the facts the question leaves unknown.
STATED: dict[str, dict[str, str]] = {
    "SB-001": {"kidem": "5 ay"},
    "SB-002": {"sigortalilik_hali": "4c", "talep_turu": "olum_toptan_odemesi"},
    "SB-003": {"degisiklik_konusu": "ucret"},
    "SB-005": {},
    "SB-006": {},
    "SB-008": {"soru_konusu": "hak", "fesih_nedeni": "askerlik"},
    "SB-010": {},
    "SB-012": {"bildirim_konusu": "eksik_gun", "eksik_gun_kodu": "06"},
    "SB-013": {"degisiklik_konusu": "calisma_saati"},
    "SB-014": {"ceza_turu": "bildirge"},
    "SB-016": {"belge_30_gun": "30 gün içinde verildi", "odeme_15_gun": "15 gün içinde ödenmedi"},
    "SB-019": {"fiil": "yalniz_kazanc_eksik"},
    "SB-021": {"fiil": "bordro_gecersiz"},
    "SB-024": {"bildirim_konusu": "ise_giris"},
    "SB-026": {"tespit_yolu": "ilam"},
    "SB-027": {"fesih_sebebi": "devamsizlik", "mazeret_bildirimi": "hayir"},
    "SB-032": {"soru_konusu": "esas_ucret"},
    "SB-035": {"fesih_sebebi": "ucret_odenmemesi"},
    "SB-039": {
        "sendika_uyeligi": "dayanisma_aidati",
        "tis_yururluk": "01.01.2025-31.12.2026, imza 01.10.2025",
    },
    "SB-042": {"talep_turu": "kidem_yazisi"},
}
# Asked beyond the case's must_ask, and why it is not out of place.
ALSO_ASKED: dict[str, set[str]] = {
    # The event date (md. 4) and the full year of service (1475 m.14) hold in the askerlik branch.
    "SB-008": {"fesih_tarihi", "hizmet_suresi"},
    # The question does not say whether the declaration was late or found by an inspection.
    "SB-014": {"fiil", "kendiliginden"},
    # The act the fine is for decides which sub-clause facts follow; the question does not say.
    "SB-016": {"fiil"},
    # The six workdays of m.26 run from the day the employer learnt of the absence.
    "SB-027": {"olay_tarihi"},
}


def test_every_case_has_what_its_template_steers_on() -> None:
    assert set(STATED) == set(CASES)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_case_is_asked_its_must_ask_from_its_template_and_nothing_out_of_place(
    case_id: str,
) -> None:
    case = CASES[case_id]
    topic = get_topic(case["expected"]["topic"])
    assert topic.id == case["expected"]["topic"]
    extracted = IntakeOutput(
        topic=topic.id,
        title=case_id,
        facts=[IntakeFact(key=k, value=v, status="known") for k, v in STATED[case_id].items()],
    )
    assert {f.key for f in extracted.facts} <= {f.key for f in topic.facts}
    facts = build_facts(topic, extracted, None, question=case["question"], today=date(2026, 11, 22))
    clarification = clarification_for(topic, facts, {})
    asked = {q.fact_key for q in clarification.questions} if clarification else set()

    assert asked == set(case["expected"]["must_ask"]) | ALSO_ASKED.get(case_id, set())


def _nothing_known(topic: Topic) -> CaseFacts:
    extracted = IntakeOutput(topic=topic.id, title=topic.title, facts=[])
    return build_facts(topic, extracted, None, question="", today=date(2026, 11, 22))


@pytest.mark.parametrize("topic_id", sorted(EXPECTED))
def test_with_the_branch_unknown_no_critical_fact_drops_silently(topic_id: str) -> None:
    """Every critical fact is asked at once, or after one answer of the first questions."""
    topic = get_topic(topic_id)
    facts = _nothing_known(topic)
    first = clarification_for(topic, facts, {})
    asked = {q.fact_key for q in first.questions} if first else set()
    for fact in topic.facts:
        if not fact.critical or fact.key in asked:
            continue
        assert first is not None and set(fact.asked_when) <= asked, fact.key
        chosen = {
            key: next(o.label for o in branch.choices if o.value in states)
            for key, states in fact.asked_when.items()
            if (branch := topic.fact(key)) is not None
        }
        answered = facts.model_copy(
            update={
                "facts": [
                    f.model_copy(update={"value": chosen[f.key], "status": "known"})
                    if f.key in chosen
                    else f
                    for f in facts.facts
                ]
            }
        )
        more = follow_up(topic, first, answered, {})
        assert more is not None and fact.key in {q.fact_key for q in more.questions}, fact.key


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_a_case_falls_into_its_template_with_the_recorded_intake(case_id: str) -> None:
    """The intake model's recorded output for the case (not a fake), read the way the intake
    node reads it: `eval/fixtures/intake/SB-NNN.json` holds the raw `IntakeOutput` JSON."""
    record = INTAKE_RECORDS / f"{case_id}.json"
    if not record.exists():
        pytest.skip(f"no recorded intake output yet: {record.name} (the first real eval run)")
    out = IntakeOutput.model_validate(json.loads(record.read_text(encoding="utf-8")))

    assert get_topic(out.topic).id == CASES[case_id]["expected"]["topic"]


def test_parse_date_reads_iso_and_turkish_dates() -> None:
    assert parse_date("2026-10-03") == parse_date("03.10.2026")
    assert parse_date("dün") is None
    assert parse_date("31.02.2026") is None


def test_a_question_basis_names_a_section_of_a_genelge_not_the_whole_act() -> None:
    from agent.topics import Question

    def question(ref: str) -> Question:
        return Question.model_validate(
            {
                "text": "Belge kendiliğinden mi verildi?",
                "why": "Genelge ayrım yapmaktadır.",
                "kind": "text",
                "basis": [{"ref": ref, "category": "admin_act"}],
            }
        )

    assert question("2020/8 m.2.6.2.5").basis[0].ref == "2020/8 m.2.6.2.5"
    with pytest.raises(ValidationError, match="section"):
        question("2020/8")


def _reading(when: dict[str, list[str]], *facts: dict[str, Any]) -> Topic:
    return Topic.model_validate(
        {
            "id": "t",
            "title": "T",
            "description": "T.",
            "facts": list(facts),
            "must_read": [{"ref": "2020/8 m.2.8.1", "category": "admin_act", "when": when}],
        }
    )


def test_a_must_read_may_be_read_only_in_a_branch() -> None:
    assert _reading({"dal": ["a"]}, ASKED_BRANCH).must_read[0].when == {"dal": ["a"]}
    assert _reading({"dal": ["a", "unknown"]}, BRANCH).must_read[0].when == {
        "dal": ["a", "unknown"]
    }


@pytest.mark.parametrize(
    ("when", "facts", "error"),
    [
        ({"yok": ["a"]}, (BRANCH,), "no fact yok"),
        ({"dal": ["c"]}, (BRANCH,), "not an option of dal"),
        ({"dal": []}, (BRANCH,), "no value"),
        ({"dal": ["a"]}, ({"key": "dal", "label": "Dal"},), "dal has no options"),
        # Never asked and not listing "unknown": the source would silently go unread.
        ({"dal": ["a"]}, (BRANCH,), "never asked"),
    ],
)
def test_a_must_read_condition_on_no_such_fact_or_value_is_refused(
    when: dict[str, list[str]], facts: tuple[dict[str, Any], ...], error: str
) -> None:
    with pytest.raises(ValidationError, match=error):
        _reading(when, *facts)


def test_the_fine_template_reads_the_genelge_sections_of_its_branch_not_the_whole_act() -> None:
    topic = get_topic("idari_para_cezasi")
    reading = {r.ref: r.when for r in topic.must_read if r.category == "admin_act"}
    assert reading == {
        "2020/8 m.3.1": {},
        "2020/8 m.3.2": {},
        "2020/8 m.2.1.1": {"fiil": ["ise_giris_gec", "ise_giris_tespit"]},
        "2020/8 m.2.8.1": {"fiil": ["bordro_gecersiz"]},
        "2020/8 m.2.8.3": {"fiil": ["bordro_gecersiz"]},
        "2020/8 m.2.6.2.5": {"fiil": ["yalniz_kazanc_eksik"]},
        # No section is named for these acts: the sections the search finds (at most six).
        "2020/8": {"fiil": ["defter_ibraz", "diger"]},
    }
