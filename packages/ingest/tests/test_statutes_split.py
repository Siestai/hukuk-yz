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


def test_range_stub_ends_the_article_and_is_not_a_numbering_gap() -> None:
    text = (
        "Kanun Numarası : 1\n"
        "MADDE 10- (1) Onuncu madde metni.\n"
        "MADDE 11 ila 16 -(22/5/2003 tarihli ve 4857 sayılı İş Kanunu ile ilgili olup yerine\n"
        "işlenmiştir.)\n"
        "MADDE 17 ila 36- (Başka kanunlarla ilgili olup yerine işlenmiştir.)\n"
        "Yürürlük\n"
        "MADDE 37- (1) Bu Kanun yayımı tarihinde yürürlüğe girer.\n"
        "MADDE 39- (1) Son madde.\n"
    )
    snap = split_statute(text)
    arts = {a.article_no: a for a in snap.articles}
    assert list(arts) == ["10", "37", "39"]
    assert arts["10"].text == "(1) Onuncu madde metni."
    assert arts["37"].heading == "Yürürlük"
    assert [a.ordinal for a in snap.articles] == [1, 2, 3]
    assert "range_stub:11-16" in snap.warnings and "range_stub:17-36" in snap.warnings
    # 11-36 are printed as stubs; 38 is really missing
    assert [w for w in snap.warnings if w.startswith("number_skipped")] == [
        "number_skipped:main:0->10",
        "number_skipped:main:37->39",
    ]


def test_hyphen_range_stubs_of_a_repealed_law_are_no_articles() -> None:
    text = (
        "Kanun Numarası : 1\n"
        "Madde 1-13/E- (Mülga: 22/5/2003/4857/120 md.)\n"
        "Kıdem tazminatı:\n"
        "Madde 14 – Kıdem tazminatı ödenir.\n"
        "Madde 15-110- (Mülga: 22/5/2003/4857/120 md.)\n"
        "Ek Madde 1-4- (Mülga: 22/5/2003/4857/120 md.)\n"
        "Geçici Madde 1-13- (Mülga: 22/5/2003/4857/120 md.)\n"
        "Madde 111-112- (Mülga: 22/5/2003/4857/120 md.)\n"
    )
    snap = split_statute(text)
    assert [(a.article_no, a.heading, a.text) for a in snap.articles] == [
        ("14", "Kıdem tazminatı:", "Kıdem tazminatı ödenir.")
    ]
    assert not [w for w in snap.warnings if w.startswith("number_skipped")]
    assert [w for w in snap.warnings if w.startswith("range_stub")] == [
        "range_stub:1-13",
        "range_stub:15-110",
        "range_stub:Ek 1-4",
        "range_stub:Geçici 1-13",
        "range_stub:111-112",
    ]


def test_lone_footnote_marker_line_leaves_the_text_only_under_the_new_rules() -> None:
    text = (
        "Kanun Numarası : 1\n"
        "Madde 1 - Bir fon tesis edilir.\n"
        "1\n"
        "Fon tesisi kanunla düzenlenir.\n"
        "1 2/7/2018 tarihli ve 700 sayılı KHK’nin 60 ıncı maddesiyle ibare eklenmiştir.\n"
    )
    art = split_statute(text, new_rules=True).articles[0]
    assert art.text == "Bir fon tesis edilir.\nFon tesisi kanunla düzenlenir."
    assert [f.no for f in art.footnotes] == [1] and art.warnings == []
    art = split_statute(text).articles[0]  # the reviewed 4857 / 5510 output keeps the marker
    assert art.text == "Bir fon tesis edilir. 1 Fon tesisi kanunla düzenlenir."
    assert art.warnings == ["footnote_marker_not_found"]


def test_in_force_table_is_cut_only_on_request() -> None:
    text = (
        "Kanun Numarası : 1\n"
        "Madde 1 - Bu Kanun hükümlerini Bakanlar Kurulu yürütür.\n"
        "1 SAYILI KANUNA EK VE DEĞİŞİKLİK GETİREN MEVZUATIN VEYA\n"
        "ANAYASA MAHKEMESİ İPTAL KARARLARININ YÜRÜRLÜĞE\n"
        "GİRİŞ TARİHLERİNİ GÖSTERİR LİSTE\n"
        "7445 3 1/9/2023\n"
    )
    cut = split_statute(text, new_rules=True)
    assert cut.articles[0].text == "Bu Kanun hükümlerini Bakanlar Kurulu yürütür."
    assert [w.split(":")[0] for w in cut.warnings] == ["in_force_table_ignored"]
    kept = split_statute(text)  # the reviewed 4857 output keeps the table in its last article
    assert "7445 3 1/9/2023" in kept.articles[0].text and kept.warnings == []


def test_repealed_first_paragraph_does_not_repeal_the_article() -> None:
    text = (
        "Kanun Numarası : 1\n"
        "Madde 1 - (1) (Mülga: 10/9/2014-6552/144 md.)\n"
        "(2) İkinci fıkra yürürlüktedir.\n"
        "Madde 2 - (Ek: 1/1/2010-5000/1 md.) (Mülga: 10/9/2014-6552/144 md.)\n"
    )
    arts = {a.article_no: a for a in split_statute(text).articles}
    assert (arts["1"].status, arts["1"].warnings) == ("in_force", [])
    assert arts["2"].status == "repealed"


def test_parse_header_without_data() -> None:
    assert parse_header("nothing here") == (None, "", None, None, None)
