"""The gate: what an answer must keep, in pure code."""

from datetime import date

import pytest
from agent_fakes import M18_1, M18_4, draft, hit, row

from agent.facts import build_facts, critical_unknown
from agent.gate import check_draft, not_answered, progressive_in
from agent.holding import verify_rows
from agent.llm_schemas import DraftOutput, HoldingDraft, IntakeOutput
from agent.sources import ReadSource, as_read_source
from agent.topics import get_topic
from hukuk_models.chat import CaseFacts, Fact, HoldingRow

TOPIC = get_topic("ise_iade")
DAY = date(2026, 10, 3)


def read() -> list[ReadSource]:
    found = as_read_source(
        hit(
            "statute:4857:m18",
            "4857 m.18",
            "4857 sayılı İş Kanunu m.18",
            f"(1) {M18_1}",
            f"(4) {M18_4}",
        )
    )
    assert found is not None
    return [found]


def rows(result: str = "met") -> list[HoldingRow]:
    holding = HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_4, result)]})
    return verify_rows(holding, read(), DAY)[0]


def facts(known: bool) -> CaseFacts:
    every = [
        {
            "key": f.key,
            "value": "03.10.2026" if f.key == "bildirim_tarihi" else "x",
            "status": "known",
        }
        for f in TOPIC.facts
        if f.question or known
    ]
    chosen = every if known else [{"key": "kidem", "value": "5 ay", "status": "known"}]
    return build_facts(
        TOPIC,
        IntakeOutput.model_validate({"topic": "ise_iade", "title": "t", "facts": chosen}),
        None,
        question="03.10.2026",
        today=DAY,
    )


def check(output: dict, *, known: bool = False, result: str = "met"):  # type: ignore[no-untyped-def,type-arg]
    return check_draft(
        DraftOutput.model_validate(output),
        topic=TOPIC,
        facts=facts(known),
        rows=rows(result),
        read=read(),
        applied_on=DAY,
        date_assumed=False,
    )


def test_a_good_conditional_draft_becomes_an_answer_the_contract_accepts() -> None:
    result = check(draft())

    assert result.issues == []
    assert result.answer is not None
    assert result.answer.disclaimer == "Hukuki görüş değildir."
    assert result.answer.applied_law_text == "03.10.2026 tarihinde yürürlükte olan metin"
    assert result.answer.short_point_count == 1


def test_definite_with_everything_known_passes() -> None:
    result = check(draft("definite", missing=False), known=True)

    assert result.issues == []
    assert result.answer is not None and result.answer.status == "definite"


def test_definite_is_refused_while_a_critical_fact_is_unknown() -> None:
    result = check(draft("definite", missing=False))

    assert result.answer is None
    assert any("kritik olgu bilinmezken" in i for i in result.issues)


def test_definite_is_refused_when_a_holding_row_is_unknown() -> None:
    result = check(draft("definite", missing=False), known=True, result="unknown")

    assert result.answer is None
    assert any("sonucu bilinmeyen satır" in i for i in result.issues)


def test_conditional_must_say_what_it_depends_on() -> None:
    result = check(draft(missing=False))

    assert result.answer is None
    assert any("missing_info" in i for i in result.issues)


@pytest.mark.parametrize(
    "headline", ["Dava açılıyor.", "İşçi hak kazanıyor.", "Bu durum aranıyor."]
)
def test_the_progressive_scan_finds_iyor_forms(headline: str) -> None:
    output = DraftOutput.model_validate(draft(headline=headline))

    assert progressive_in(output)
    assert any("-iyor" in i for i in check(draft(headline=headline)).issues)


def test_the_progressive_scan_passes_formal_turkish() -> None:
    assert progressive_in(DraftOutput.model_validate(draft())) == []


def test_the_scan_looks_at_every_sentence_the_model_wrote() -> None:
    output = draft()
    output["points"][0]["text"] = "Kıdem aranıyor."
    output["missing_info"][0]["result"] = "Hüküm uygulanıyor."
    output["reasoning_summary"] = "Şart sağlanıyor."

    assert progressive_in(DraftOutput.model_validate(output)) == [
        "aranıyor",
        "sağlanıyor",
        "uygulanıyor",
    ]


def test_a_citation_to_a_text_not_in_force_on_the_date_drops() -> None:
    old = as_read_source(
        hit("statute:4857:m18", "4857 m.18", "t", M18_1, valid_to=date(2020, 1, 1))
    )
    assert old is not None

    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=TOPIC,
        facts=facts(False),
        rows=rows(),
        read=[old],
        applied_on=DAY,
        date_assumed=False,
    )

    assert result.answer is None
    assert result.drops.points == 1
    assert any("atıfı doğrulanan nokta kalmamıştır" in i for i in result.issues)


def test_no_verified_row_is_no_answer() -> None:
    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=TOPIC,
        facts=facts(False),
        rows=[],
        read=read(),
        applied_on=DAY,
        date_assumed=False,
    )

    assert result.answer is None
    assert any("hüküm haritası" in i for i in result.issues)


def test_the_calculations_of_the_template_are_added_by_code() -> None:
    topic = get_topic("kidem_ihbar")
    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=topic,
        facts=build_facts(
            topic,
            IntakeOutput.model_validate({"topic": "kidem_ihbar", "title": "t", "facts": []}),
            None,
            question="",
            today=DAY,
        ),
        rows=rows(),
        read=read(),
        applied_on=DAY,
        date_assumed=True,
    )

    assert result.answer is not None
    assert [c.title for c in result.answer.calculations] == ["Kıdem tazminatı", "İhbar tazminatı"]
    assert "Olay tarihi bilinmediğinden" in result.answer.status_note


def test_the_not_answered_answer_shows_the_verified_rows_or_nothing() -> None:
    kwargs = dict(topic=TOPIC, facts=facts(False), read=read(), applied_on=DAY, date_assumed=False)

    answer = not_answered(rows=rows(), **kwargs)  # type: ignore[arg-type]

    assert answer is not None
    assert answer.headline == "Doğrulanmış kaynakla cevap verilemedi."
    assert answer.holding_map.rows
    assert not_answered(rows=[], **kwargs) is None  # type: ignore[arg-type]


def test_a_paragraph_the_text_read_does_not_have_is_not_cited() -> None:
    output = draft()
    output["points"][0]["citations"][0]["sub"] = "99"

    result = check(output)

    assert result.answer is not None
    assert result.answer.points[0].citations[0].ref == "4857 m.18"
    assert result.answer.points[0].citations[0].label == "4857 sayılı İş Kanunu m.18"


def test_the_scan_looks_at_the_rows_and_the_title_of_the_facts_too() -> None:
    output = DraftOutput.model_validate(draft())
    row_with = HoldingRow.model_validate(
        {
            **rows()[0].model_dump(),
            "condition": "Kıdem aranıyor",
            "fact_value": "Hâlâ çalışıyor",
        }
    )
    titled = facts(False).model_copy(update={"title": "Dava açılıyor"})

    assert progressive_in(output, [row_with], titled) == ["aranıyor", "açılıyor", "çalışıyor"]


def test_an_unread_must_read_source_forbids_definite() -> None:
    result = check_draft(
        DraftOutput.model_validate(draft("definite", missing=False)),
        topic=TOPIC,
        facts=facts(True),
        rows=rows(),
        read=read(),
        applied_on=DAY,
        date_assumed=False,
        unread=["2020/8"],
    )

    assert result.answer is None
    assert any("okunamayan kaynak" in i for i in result.issues)


def test_an_unread_must_read_source_is_named_in_the_note_of_a_conditional_answer() -> None:
    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=TOPIC,
        facts=facts(False),
        rows=rows(),
        read=read(),
        applied_on=DAY,
        date_assumed=False,
        unread=["2020/8"],
    )

    assert result.answer is not None
    assert "Okunamayan kaynaklar bulunmaktadır: 2020/8." in result.answer.status_note


def test_point_quote_in_another_paragraph_does_not_keep_model_sub() -> None:
    output = draft()
    output["points"][0]["citations"] = [
        {"source_id": "statute:4857:m18", "sub": "1", "quote": M18_4}
    ]
    result = check(output)
    assert result.answer is not None
    assert result.answer.points[0].citations[0].ref == "4857 m.18"


def test_fallback_never_returns_informal_holding_rows() -> None:
    informal = rows()[0].model_copy(update={"condition": "Kıdem aranıyorsa"})
    assert (
        not_answered(
            topic=TOPIC,
            facts=facts(False),
            rows=[informal],
            read=read(),
            applied_on=DAY,
            date_assumed=False,
        )
        is None
    )


def test_the_expiry_day_is_not_a_valid_citation_date() -> None:
    expired = read()[0].model_copy(update={"valid_to": DAY})
    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=TOPIC,
        facts=facts(False),
        rows=rows(),
        read=[expired],
        applied_on=DAY,
        date_assumed=False,
    )
    assert result.answer is None
    assert result.drops.citations == result.drops.points == 1


def test_missing_info_citation_purpose_is_also_checked_for_formal_tense() -> None:
    output = draft()
    output["missing_info"][0]["citations"] = [
        {"source_id": "statute:4857:m18", "used_for": "Kıdem aranıyorsa"}
    ]
    assert progressive_in(DraftOutput.model_validate(output)) == ["aranıyorsa"]
    assert check(output).answer is None


@pytest.mark.parametrize(
    ("status", "has_rows", "expected"),
    [
        ("definite", True, {"critical_unknown": 6, "unread_source": 1, "unknown_holding": 1}),
        (
            "conditional",
            False,
            {"missing_conditions": 1, "no_verified_rows": 1, "uncovered_critical_facts": 6},
        ),
    ],
)
def test_issue_counts_use_fixed_codes_while_feedback_keeps_details(
    status: str, has_rows: bool, expected: dict[str, int]
) -> None:
    private = "PRIVATE_SOURCE_12345678901"
    result = check_draft(
        DraftOutput.model_validate(draft(status, missing=False)),
        topic=TOPIC,
        facts=facts(False),
        rows=rows("unknown") if has_rows else [],
        read=read(),
        applied_on=DAY,
        date_assumed=False,
        unread=[private],
    )
    assert result.answer is None
    assert result.issue_counts == expected
    if status == "definite":
        assert private in " ".join(result.issues)
    assert private not in str(result.issue_counts)


@pytest.mark.parametrize(
    ("results", "blocked"),
    [
        ([], True),
        (["not_applicable"], True),
        (["not_applicable", "not_applicable"], True),
        (["not_applicable", "met"], False),
        (["not_applicable", "unknown"], False),
        (["unknown"], False),
        (["not_met"], False),
        (["met"], False),
    ],
)
def test_holding_applicability_controls_ordinary_draft(results: list[str], blocked: bool) -> None:
    verified = [r for value in results for r in rows(value)]
    result = check_draft(
        DraftOutput.model_validate(draft()),
        topic=TOPIC,
        facts=facts(False),
        rows=verified,
        read=read(),
        applied_on=DAY,
        date_assumed=False,
    )
    assert (result.answer is None) is blocked
    if results and blocked:
        assert result.issue_counts == {"all_holdings_not_applicable": 1}
        fallback = not_answered(
            topic=TOPIC,
            facts=facts(False),
            rows=verified,
            read=read(),
            applied_on=DAY,
            date_assumed=False,
        )
        assert fallback is not None
        assert fallback.holding_map.rows == verified
        assert all(m.fact_key is None for m in fallback.missing_info)
        assert fallback.read_sources.items[0].source_id == read()[0].source_id


def test_conditional_branch_with_invalid_quote_cannot_keep_its_consequence() -> None:
    output = draft()
    output["missing_info"][0]["citations"] = [
        {"source_id": "statute:4857:m18", "quote": "Okunmamış bir hüküm metni"}
    ]
    result = check(output)
    assert result.answer is None
    assert result.issue_counts["unsupported_branch"] == 1


def test_source_id_without_quote_cannot_support_a_claim() -> None:
    output = draft()
    output["points"][0]["citations"] = [{"source_id": "statute:4857:m18"}]
    result = check(output)
    assert result.answer is None
    assert result.drops.citations == 1


@pytest.mark.parametrize("omitted", [("bildirim_tarihi", "kisaltma"), ("kisaltma",)])
def test_conditional_rejects_omitted_critical_fact_keys(omitted: tuple[str, ...]) -> None:
    output = draft()
    required = critical_unknown(TOPIC, facts(False))
    assert len(required) == 6
    output["missing_info"] = [
        {"fact_key": key, "condition": key, "result": "Bilgi gerekmektedir."}
        for key in required
        if key not in omitted
    ]
    # Duplicates, null keys and known/unrelated keys cannot replace a missing critical key.
    output["missing_info"] += [output["missing_info"][0]] + [
        {"fact_key": key, "condition": "Ek bilgi", "result": "Bilgi gerekmektedir."}
        for key in (None, "kidem", "unrelated")
    ]
    result = check(output)
    assert result.answer is None
    assert result.issue_counts == {"uncovered_critical_facts": len(omitted)}
    assert all(key in " ".join(result.issues) for key in omitted)
    assert all(key not in str(result.issue_counts) for key in omitted)


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("no_facts", [False, True])
def test_conditional_coverage_uses_actual_critical_unknowns_only(
    known: bool, no_facts: bool
) -> None:
    topic = TOPIC.model_copy(update={"facts": [], "event_date_fact": None}) if no_facts else TOPIC
    case = facts(known)
    case = case.model_copy(
        update={
            "facts": [
                *case.facts,
                Fact(key="unrelated", label="Ek", value="x", status="known"),
                Fact(key="noncritical", label="Ek", status="unknown"),
            ]
        }
    )
    output = draft()
    output["missing_info"] = [
        {
            "fact_key": key,
            "condition": "Eksik bilgi",
            "result": "Okunan kaynaklarla sonuç belirlenememektedir.",
        }
        for key in [*critical_unknown(topic, case), None, "noncritical"]
    ]
    result = check_draft(
        DraftOutput.model_validate(output),
        topic=topic,
        facts=case,
        rows=rows("unknown"),
        read=read(),
        applied_on=DAY,
        date_assumed=False,
        unread=["Okunamayan kaynak"],
    )
    assert result.issues == []
    assert result.answer is not None
    assert all(not item.citations for item in result.answer.missing_info)
