"""What was read: references, quotes, validity and the citations built from them."""

from datetime import date

from agent_fakes import M18_1, M18_4, hit

from agent.sources import (
    MAX_SOURCE_CHARS,
    ReadSource,
    as_read_source,
    checked_sub,
    citation,
    covers,
    locate,
    merge,
    named_source,
    shown,
    split_ref,
    summarize,
    valid_on,
)


def source(
    *passages: str, valid_from: date | None = None, valid_to: date | None = None
) -> ReadSource:
    found = as_read_source(
        hit(
            "statute:4857:m18",
            "4857 m.18",
            "4857 sayılı İş Kanunu m.18",
            *passages,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    )
    assert found is not None
    return found


def test_split_ref_separates_the_article_from_the_paragraph() -> None:
    assert split_ref("4857 m.18/1") == ("4857 m.18", "/1")
    assert split_ref("4857 m.17/2-a") == ("4857 m.17", "/2-a")
    assert split_ref("4857 m.18/1 son cümle") == ("4857 m.18", "/1 son cümle")
    assert split_ref("5510 m.102") == ("5510 m.102", "")
    assert split_ref("9. HD E.2016/28920 K.2017/17860") == (
        "9. HD E.2016/28920 K.2017/17860",
        "",
    )


def test_a_hit_covers_the_reference_it_is_or_contains() -> None:
    assert covers("4857 m.18", "4857 m.18/1")
    assert covers("4857 m.18/1", "4857 m.18")
    assert not covers("4857 m.180", "4857 m.18")
    assert not covers("4857 m.1", "4857 m.18")
    assert covers("2020/8 İPC Genelgesi m.3.1", "2020/8")


def test_a_hit_without_text_cannot_be_read() -> None:
    internal = hit("decision:x", "9. HD E.1/2 K.3/4", "Karar", category="decision")
    internal.matches[:] = []

    assert as_read_source(internal) is None


def test_a_quote_is_found_word_for_word_with_its_offsets() -> None:
    read = source(M18_1, M18_4)

    assert locate(read, M18_4) == (len(M18_1) + 1, len(M18_1) + 1 + len(M18_4))
    assert locate(read, "aynı işverenin  bir veya\ndeğişik işyerlerinde") is not None
    assert locate(read, "kıdem şartı aranmaz") is None
    assert locate(read, "   ") is None


def test_a_quote_without_offsets_in_the_source_is_found_without_them() -> None:
    read = source(M18_1)
    read.passages[0].char_start = None

    assert locate(read, "en az altı aylık") == (None, None)


# 2020/8 m.2.1.1 as the knowledge base holds it: typographic apostrophes and quotation marks.
GENELGE = (
    "Kurumca re\u2019sen düzenlenir; \u201cek belge\u201d için asgari ücretin 2/3\u2019ü "
    "\u2013 uygulanır."
)


def test_typographic_marks_match_their_plain_forms_and_the_citation_quotes_the_source() -> None:
    read = source(GENELGE)
    plain = "Kurumca re'sen düzenlenir; \"ek belge\" için asgari ücretin 2/3'ü - uygulanır."

    assert locate(read, plain) == (0, len(GENELGE))
    cited = citation(read, quote="için asgari ücretin 2/3'ü")
    assert cited.quote == "için asgari ücretin 2/3\u2019ü"
    # Only the glyph of a mark is free: the words stay verbatim, letter case included.
    assert locate(read, "Kurumca resen düzenlenir") is None
    assert locate(read, "kurumca re'sen düzenlenir") is None
    assert locate(read, "Kurumca re sen düzenlenir") is None


def test_a_model_may_name_a_read_source_by_its_kunye_when_only_one_has_it() -> None:
    m18 = source(M18_1)
    other = m18.model_copy(update={"source_id": "statute:4857:m18:eski"})
    sources = {m18.source_id: m18}

    assert named_source(sources, "statute:4857:m18") is m18
    assert named_source(sources, "4857 m.18") is m18
    assert named_source(sources, " 4857 M.18/1 ") is m18
    assert named_source(sources, "4857 m.19") is None
    assert named_source(sources, "statute:4857") is None
    # Two sources read under the same künye: the künye names neither.
    assert named_source({**sources, other.source_id: other}, "4857 m.18") is None


def test_valid_on_respects_the_bounds_that_are_recorded() -> None:
    read = source(M18_1, valid_from=date(2020, 1, 1), valid_to=date(2024, 12, 31))

    assert valid_on(read, date(2022, 6, 1))
    assert not valid_on(read, date(2019, 12, 31))
    assert not valid_on(read, date(2025, 1, 1))
    assert not valid_on(read, date(2024, 12, 31))
    assert valid_on(read, date(2020, 1, 1))
    assert valid_on(source(M18_1), date(1999, 1, 1))


def test_a_citation_takes_metadata_from_the_source_and_checks_the_requested_paragraph() -> None:
    ref = citation(source(M18_1, f"(4) {M18_4}"), sub="4", quote=M18_4, used_for="Önceki süreler")

    assert ref.label == "4857 sayılı İş Kanunu m.18/4"
    assert ref.ref == "4857 m.18/4"
    assert (ref.char_start, ref.char_end) == (len(M18_1) + 5, len(M18_1) + 5 + len(M18_4))
    assert ref.verification == "not_applicable"
    assert ref.review_status == "approved"


def test_a_source_read_twice_keeps_each_passage_once() -> None:
    merged = merge([source(M18_1)], [source(M18_1, M18_4)])

    assert len(merged) == 1
    assert [p.text for p in merged[0].passages] == [M18_1, M18_4]


def test_the_read_sources_count_the_distinct_sources_per_category() -> None:
    decision = as_read_source(
        hit("decision:a", "9. HD E.1/2 K.3/4", "Karar", "metin", category="decision")
    )
    assert decision is not None

    summary = summarize([source(M18_1), decision])

    assert (summary.statute_articles, summary.decisions, summary.admin_acts) == (1, 1, 0)
    assert [i.source_id for i in summary.items] == ["statute:4857:m18", "decision:a"]


def test_an_unreviewed_source_is_listed_as_analyzed_with_its_band() -> None:
    unreviewed = as_read_source(
        hit(
            "analyzed:5510:m.8:2008-10-01",
            "5510 m.8",
            "5510 m.8",
            "metin",
            review_status="analyzed",
            band="medium",
        )
    )
    assert unreviewed is not None

    items = summarize([source(M18_1), unreviewed]).items

    assert [(i.ref, i.review_status, i.band) for i in items] == [
        ("4857 m.18", "approved", None),
        ("5510 m.8", "analyzed", "medium"),
    ]
    assert citation(unreviewed, quote="metin").band == "medium"


def test_a_paragraph_is_cited_only_when_its_number_stands_in_the_text_read() -> None:
    read = source(f"(1) {M18_1}", f"(4) {M18_4}")

    assert checked_sub(read, "4") == "4"
    assert checked_sub(read, "1-a") is None
    assert checked_sub(read, "99") is None
    assert checked_sub(read, None) is None
    assert checked_sub(source(M18_1), "1") is None


def test_the_models_are_shown_no_more_than_what_is_recorded_as_read() -> None:
    long = "x" * (MAX_SOURCE_CHARS - 10)

    cut = shown(source(long, M18_1, M18_4))

    assert [len(p.text) for p in cut.passages] == [MAX_SOURCE_CHARS - 10, 10]
    assert shown(source(M18_1)).passages == source(M18_1).passages
    # A source named by its künye gets a higher limit.
    assert shown(source(long, M18_1, M18_4), MAX_SOURCE_CHARS * 2).passages == (
        source(long, M18_1, M18_4).passages
    )


def test_a_quote_in_another_paragraph_cannot_support_the_requested_sub() -> None:
    read = source(f"(1) {M18_1}\n(4) {M18_4}")
    assert checked_sub(read, "1", M18_4) is None
    assert checked_sub(read, "4", M18_4) == "4"
    assert citation(read, sub="1", quote=M18_4).ref == "4857 m.18"
    assert checked_sub(read, "4-invented", M18_4) is None


def test_literal_quote_does_not_match_inside_a_word_or_cross_unread_passages() -> None:
    assert locate(source("işçinin kıdemi"), "işçi") is None
    assert locate(source("önceki hizmet", "süresi sayılır"), "hizmet süresi") is None
    assert locate(source("önceki hizmet süresi"), "Hizmet süresi") is None


def test_inline_footnote_markers_do_not_prove_a_paragraph() -> None:
    assert checked_sub(source(f"{M18_1} (99) dipnot"), "99") is None


def test_repeated_quote_offsets_point_to_the_verified_paragraph() -> None:
    text = f"(1) {M18_4}\n(4) {M18_4}"
    ref = citation(source(text), sub="4", quote=M18_4)
    assert ref.ref == "4857 m.18/4"
    assert ref.char_start == text.rindex(M18_4)
    assert ref.char_end == len(text)


def test_search_excerpts_are_not_complete_and_truncation_revokes_completeness() -> None:
    from agent.kb import KbHit, KbMatch
    from agent.sources import MAX_SOURCE_CHARS, as_read_source, shown

    hit = KbHit(
        source_id="synthetic",
        category="statute",
        title="Test",
        ref="4857 m.18",
        review_status="approved",
        matches=[KbMatch(chunk_id="1", text="Short excerpt", char_start=90)],
    )
    partial = as_read_source(hit)
    assert partial is not None and not partial.complete
    full = as_read_source(
        hit.model_copy(
            update={
                "complete": True,
                "matches": [KbMatch(chunk_id="1", text="a" * (MAX_SOURCE_CHARS + 1), char_start=0)],
            }
        )
    )
    assert full is not None and full.complete
    clipped = shown(full)
    assert not clipped.complete
    assert len(clipped.passages[0].text) == MAX_SOURCE_CHARS


def test_full_read_replaces_search_excerpts_without_duplicate_budget_truncation() -> None:
    partial = source("A matched excerpt")
    full = source("x" * (MAX_SOURCE_CHARS - 1)).model_copy(update={"complete": True})
    for left, right in ((partial, full), (full, partial)):
        result = merge([left], [right])
        assert len(result) == 1
        assert result[0].passages == full.passages
        assert shown(result[0]).complete
