"""The holding map is checked by code: a row stays only on a read, valid source and a verbatim
quote."""

from datetime import date
from typing import Any

from agent_fakes import M18_1, M18_4, hit, row

from agent.holding import verify_rows
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


def verify(*rows: dict) -> tuple[list, int]:  # type: ignore[type-arg]
    return verify_rows(HoldingDraft.model_validate({"rows": list(rows)}), READ, DAY)


def test_a_row_with_a_verbatim_quote_of_a_read_source_stays() -> None:
    rows, dropped = verify(row("statute:4857:m18", M18_4, sub="4"))

    assert dropped == 0
    assert rows[0].citation.ref == "4857 m.18/4"
    assert rows[0].citation.quote == M18_4
    assert rows[0].citation.char_start is not None


def test_a_row_with_a_fabricated_quote_drops() -> None:
    rows, dropped = verify(row("statute:4857:m18", "Bu ifade kanunda hiç geçmemektedir"))

    assert (rows, dropped) == ([], 1)


def test_a_row_on_a_source_that_was_not_read_drops() -> None:
    assert verify(row("statute:4857:m19", M18_4)) == ([], 1)


def test_a_row_on_a_text_not_in_force_on_the_date_drops() -> None:
    assert verify(row("statute:old", "Bu hüküm artık yürürlükte değildir")) == ([], 1)


def test_a_quote_too_short_to_prove_anything_drops() -> None:
    assert verify(row("statute:4857:m18", "işçinin")) == ([], 1)


def test_the_good_rows_stay_when_others_drop() -> None:
    rows, dropped = verify(
        row("statute:4857:m18", M18_4, "unknown"), row("statute:4857:m18", "uydurma bir alıntı yok")
    )

    assert len(rows) == 1 and dropped == 1
    assert rows[0].result == "unknown"


def test_a_paragraph_the_text_does_not_have_is_left_out_of_the_citation() -> None:
    rows, dropped = verify(row("statute:4857:m18", M18_4, sub="99"))

    assert dropped == 0
    assert rows[0].citation.ref == "4857 m.18"


def test_a_quote_in_a_different_paragraph_is_cited_at_article_level() -> None:
    rows, dropped = verify(row("statute:4857:m18", M18_4, sub="1"))
    assert dropped == 0
    assert rows[0].citation.ref == "4857 m.18"


def test_informal_holding_text_is_dropped_before_it_can_reach_the_fallback() -> None:
    candidate = row("statute:4857:m18", M18_4)
    for field in ("condition", "fact_value"):
        assert verify({**candidate, field: "İşçi çalışıyordu"}) == ([], 1)


def test_the_expiry_day_is_not_a_valid_holding_source_date() -> None:
    draft = HoldingDraft.model_validate({"rows": [row("statute:4857:m18", M18_1)]})
    expired = READ[0].model_copy(update={"valid_to": DAY})
    assert verify_rows(draft, [expired], DAY) == ([], 1)


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
            (["missing_key"], "unknown" if result in ("met", "not_met") else result),
        ):
            candidate = {**row("statute:4857:m18", M18_1, result), "depends_on_facts": dependencies}
            verified, dropped = verify_rows(
                HoldingDraft.model_validate({"rows": [candidate]}), READ, DAY, facts=facts
            )
            assert dropped == 0
            assert verified[0].result == expected
            assert verified[0].condition_quote == M18_1


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
    assert verify_rows(original, [source], DAY) == ([], 3)
    for value in ("bilinmemektedir", "belirsiz"):
        formal = original.model_copy(deep=True)
        for candidate in formal.rows:
            assert candidate.fact_value is not None
            candidate.fact_value = candidate.fact_value.replace("bilinmiyor", value)
        rows, dropped = verify_rows(formal, [source], DAY)
        assert dropped == 0 and len(rows) == 3
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
        for field in ("condition", "fact_value"):
            invalid = formal.model_copy(deep=True)
            for candidate in invalid.rows:
                setattr(candidate, field, "Olgu bilinmiyor")
            assert verify_rows(invalid, [source], DAY) == ([], 3)
