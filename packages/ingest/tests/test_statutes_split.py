import pytest
from statute_texts import marker_line_style, numbered_style, rule_style

from hukuk_ingest.statutes.split import parse_header, split_statute


def _by_no(text: str) -> dict[str, object]:
    return {a.article_no: a for a in split_statute(text).articles}


def test_header_and_head_variants_are_normalised() -> None:
    snap = split_statute(rule_style())
    assert (snap.number, str(snap.kabul_tarihi), str(snap.rg_tarihi), snap.rg_sayisi) == (
        "9001",
        "2003-05-22",
        "2003-06-10",
        "25134",
    )
    assert snap.title == "DENEME KANUNU"
    assert [a.article_no for a in snap.articles] == ["1", "2", "3", "5", "Geçici 1", "Ek 1"]
    assert [a.ordinal for a in snap.articles] == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Madde 18 - Metin.", "18"),
        ("MADDE 18- Metin.", "18"),
        ("Madde 30 – Metin.", "30"),
        ("MADDE 4/A- Metin.", "4/A"),
        ("Ek Madde 2 - Metin.", "Ek 2"),
        ("EK MADDE 2- Metin.", "Ek 2"),
        ("Geçici Madde 4 - Metin.", "Geçici 4"),
        ("GEÇİCİ MADDE 4- Metin.", "Geçici 4"),
        ("Madde 87 (Mülga: 20/6/2012-6331/37 md.)", "87"),
    ],
)
def test_article_no_normalisation(line: str, expected: str) -> None:
    snap = split_statute(f"Kanun Numarası : 1\n{line}\n")
    assert [a.article_no for a in snap.articles] == [expected]


def test_margin_heading_and_section_titles() -> None:
    arts = {a.article_no: a for a in split_statute(rule_style()).articles}
    assert arts["1"].heading == "Amaç ve kapsam"  # the BÖLÜM label and its title are skipped
    assert arts["2"].heading == "Tanımlar"
    assert "Tanımlar" not in arts["1"].text
    assert "BÖLÜM" not in arts["1"].text


def test_rule_style_footnotes_never_reach_the_text_and_are_attached() -> None:
    snap = split_statute(rule_style())
    for art in snap.articles:
        assert RULE_MARK not in art.text
        assert "hüküm altına alınmıştır" not in art.text
        assert "8424" not in art.text
    first = snap.articles[0]
    assert [f.no for f in first.footnotes] == [1]
    assert (
        "1/7/2008 tarihinde yürürlüğe gireceği hüküm altına alınmıştır" in first.footnotes[0].text
    )
    assert first.text.endswith("burada biter.")
    assert "(1)" in first.text  # the marker stays in the running text
    assert snap.footnote_count == 2


RULE_MARK = "––––"


def test_rule_style_marker_glued_to_heading_is_stripped() -> None:
    arts = {a.article_no: a for a in split_statute(rule_style()).articles}
    assert arts["5"].heading == "Engelli çalıştırma zorunluluğu"
    assert [f.no for f in arts["5"].footnotes] == [2]


def test_numbered_style_footnotes_and_glued_heading_markers() -> None:
    snap = split_statute(numbered_style())
    arts = {a.article_no: a for a in snap.articles}
    for art in snap.articles:
        assert "tarihli ve" not in art.text
    assert arts["3"].heading == "Yaşlılık aylığının başlangıcı ve kesilmesi"
    assert arts["4"].heading == "Engelli ve eski hükümlü çalıştırma zorunluluğu"  # markers 3, 4
    assert [f.no for f in arts["2"].footnotes] == [1]
    assert [f.no for f in arts["3"].footnotes] == [2]
    assert [f.no for f in arts["4"].footnotes] == [3, 4]
    assert "metne işlendiği biçimde değiştirilmiştir" in arts["3"].footnotes[0].text
    assert all(fn.marker_found for a in snap.articles for fn in a.footnotes)


def test_numbered_style_ignores_the_trailer_of_unmerged_provisions() -> None:
    snap = split_statute(numbered_style())
    assert [a.article_no for a in snap.articles] == ["1", "2", "3", "4", "5", "6"]
    assert snap.articles[-1].text == "Bu Kanun hükümlerini Bakanlar Kurulu yürütür."
    assert any(w.startswith("trailer_ignored") for w in snap.warnings)


def test_marker_line_style_and_page_start_heads() -> None:
    snap = split_statute(marker_line_style())
    arts = {a.article_no: a for a in snap.articles}
    assert list(arts) == ["1", "87", "88"]
    assert "Cumhurbaşkanlığı kararnamesine" not in arts["1"].text
    assert [f.no for f in arts["1"].footnotes] == [1]
    assert arts["87"].status == "repealed"
    assert arts["88"].heading == "Tanımlar"


def test_wrapped_lines_join_into_paragraphs() -> None:
    art = split_statute(numbered_style()).articles[1]
    assert art.text == (
        "Bu Kanun, sigortalıları kapsar. Ancak 15 gün süreyle çalışanlar bu hükmün dışındadır.1"
    )
    first = split_statute(numbered_style()).articles[0]
    assert first.text == (
        "Bu Kanunun amacı, sosyal sigortaları düzenlemek ve işleyişe ilişkin usûl ve esasları "
        "belirlemektir."
    )


def test_repealed_stub_stays_an_article() -> None:
    arts = {a.article_no: a for a in split_statute(rule_style()).articles}
    assert arts["3"].status == "repealed"
    assert arts["3"].text == "(Mülga: 20/6/2012-6331/37 md.)"
    assert arts["2"].status == "in_force"


def test_numbering_checks_flag_skips_and_repeats() -> None:
    snap = split_statute(rule_style())
    assert "number_skipped:main:3->5" in snap.warnings
    text = "Kanun Numarası : 1\nMadde 1 - A.\nMadde 2 - B.\nMadde 2 - C.\nMadde 1 - D.\n"
    snap = split_statute(text)
    assert [a.article_no for a in snap.articles] == ["1", "2", "2 (2)", "1 (2)"]
    assert "duplicate_article:2" in snap.warnings
    assert "duplicate_article:2" in snap.articles[2].warnings


def test_parse_header_without_data() -> None:
    assert parse_header("nothing here") == (None, "", None, None, None)
