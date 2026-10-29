"""The holding map is checked by code: a row stays only on a read, valid source and a verbatim
quote."""

from datetime import date

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
