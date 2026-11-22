from datetime import date

from hukuk_ingest.admin_acts import confidence
from hukuk_ingest.admin_acts.split import INTRO, amendments, is_repealed, split_act
from hukuk_ingest.quality import PAGE_BREAK

LETTERHEAD = "T.C.\nÖRNEK KURUMU BAŞKANLIĞI\nBu belge elektronik imza ile imzalanmıştır."


def _filler(n: int) -> str:
    """A line long enough for a page to count as having text; different on every page."""
    return f"Bu {n}. satır sayfanın metin katmanı olduğunu göstermeye yetecek kadar uzundur."


def _pages(*bodies: str) -> str:
    """Pages with the same letterhead on top, as an e-signed genelge has."""
    return PAGE_BREAK.join(f"{LETTERHEAD}\n{body}" for body in bodies)


FLAT = _pages(
    "Sayı : 123-010.06-E.1 01/04/2020\nKonu : Örnek Genelgesi\n"
    "1-GENEL AÇIKLAMALAR......4\n2- CEZA ÖNGÖRÜLEN FİİLLER.....4\n"
    "2.1- Giriş Bildirgesi.......4\n3-DİĞER HUSUSLAR ......9",
    f"GENELGE\n2020/8\n1- GENEL AÇIKLAMALAR\nBilindiği üzere cezalar açıklanmıştır.\n{_filler(1)}\n"
    "2- CEZA ÖNGÖRÜLEN FİİLLER\n2.1- Giriş Bildirgesi\n"
    "2.1.1-5510 sayılı Kanunun 4 üncü maddesi\nkapsamındaki sigortalılar\nBildirge verilir.",
    f"Aşağıdaki hallerde ceza uygulanmaz:\n1- Süresinde verilmesi,\n2- Mücbir sebep,\n"
    f"3- Kurum hatası.\n{_filler(2)}\n2.1.2. Diğer sigortalılar\n15 gün içinde bildirilir.\n"
    "03.12.2010 tarihli karar uygulanır.\n2.2 Ayrılış Bildirgesi\nOn gün içinde verilir.",
    f"3-DİĞER HUSUSLAR\n3.1- Bu genelgeye göre işlem yapılacaktır. İlgili\nmevzuat saklıdır.\n"
    f"{_filler(3)}\nBilgi edinilmesini ve gereğini rica ederim.\nAd SOYAD\nKurum Başkanı",
    f"EK-1\nÖRNEK FORM\n{_filler(4)}",
)


def test_sections_follow_the_numbered_headings() -> None:
    split = split_act(FLAT)

    assert [s.section_no for s in split.sections] == [
        "1",
        "2",
        "2.1",
        "2.1.1",
        "2.1.2",
        "2.2",
        "3",
        "3.1",
    ]
    assert [s.ordinal for s in split.sections] == list(range(8))
    by_no = {s.section_no: s for s in split.sections}
    assert by_no["2"].children == ["2.1", "2.2"]
    assert by_no["2.1"].children == ["2.1.1", "2.1.2"]
    assert by_no["2.1.1"].heading == "5510 sayılı Kanunun 4 üncü maddesi"
    assert by_no["2"].text == "2- CEZA ÖNGÖRÜLEN FİİLLER"  # a parent holds only its own text
    assert not any(s.warnings for s in split.sections)


def test_the_text_of_a_section_is_its_lines_without_the_page_furniture() -> None:
    section = next(s for s in split_act(FLAT).sections if s.section_no == "2.1.1")

    # the section runs over a page break: the letterhead of the next page is not in it, and the
    # numbered list ("3- Kurum hatası.") is text, not the heading of section 3
    assert section.text == (
        "2.1.1-5510 sayılı Kanunun 4 üncü maddesi\n"
        "kapsamındaki sigortalılar\n"
        "Bildirge verilir.\n"
        "Aşağıdaki hallerde ceza uygulanmaz:\n"
        "1- Süresinde verilmesi,\n"
        "2- Mücbir sebep,\n"
        "3- Kurum hatası.\n" + _filler(2)
    )
    assert section.pages == [2, 3]


def test_a_number_or_a_date_at_the_start_of_a_line_is_not_a_heading() -> None:
    section = next(s for s in split_act(FLAT).sections if s.section_no == "2.1.2")

    assert section.text == (
        "2.1.2. Diğer sigortalılar\n15 gün içinde bildirilir.\n03.12.2010 tarihli karar uygulanır."
    )


def test_masthead_contents_closing_and_annexes_are_not_sections() -> None:
    split = split_act(FLAT)

    assert (split.ref, split.issue_date, split.subject) == (
        "2020/8",
        date(2020, 4, 1),
        "Örnek Genelgesi",
    )
    assert split.sections[0].text.startswith("1- GENEL AÇIKLAMALAR")
    assert split.sections[-1].text == (
        "3.1- Bu genelgeye göre işlem yapılacaktır. İlgili\nmevzuat saklıdır.\n" + _filler(3)
    )
    assert (split.toc_entries, split.toc_unmatched) == (4, [])
    assert (split.pages, split.annex_pages, split.pages_without_text) == (5, [5, 5], [])


PARTS = PAGE_BREAK.join(
    [
        "i\nGENELGE\n2018/38\n15/08/2019 tarihli ve 2019/16 sayılı\n21/05/2026 tarihli ve 2026/14 "
        "sayılı\nGenelgeler işlenmiş haliyle\n06 KASIM 2018",
        "ii\nİÇİNDEKİLER\nBİRİNCİ KISIM\nTEMEL KAVRAMLAR\n1. Sigortalılık Süresi........1\n"
        "1.1. Başlangıç ......1\n2. Yaş..2\nİKİNCİ KISIM\nYARDIMLAR\nBİRİNCİ BÖLÜM\n"
        "YAŞLILIK SİGORTASI\nİKİNCİ BÖLÜM\nMALULLÜK SİGORTASI\n"
        "1. Malul Sayılma Koşullarının Tespiti ve Kurumca Yapılacak İşlemler\n..........3",
        f"1\nSayı : 98-010.06-E.1 06/11/2018\nKonu : Emeklilik İşlemleri\nGENELGE\n2018 /38\n"
        f"Bu Genelge emeklilik işlemlerini açıklar.\n{_filler(1)}\nBİRİNCİ KISIM\n"
        "TEMEL KAVRAMLAR\nKavramlar aşağıdadır.\n1. Sigortalılık Süresi\nSüre tanımı.\n"
        "1.1. Başlangıç\nİlk giriş.",
        f"2\n2. Yaş\nYaş tanımı.\n{_filler(2)}\nİKİNCİ KISIM\nYARDIMLAR\nBİRİNCİ BÖLÜM\n"
        "YAŞLILIK SİGORTASI\nBu bölümün numaralı başlığı yoktur.",
        f"3\nİKİNCİ BÖLÜM\nMALULLÜK SİGORTASI\n1. Malul Sayılma Koşullarının Tespiti ve Kurumca "
        f"Yapılacak\nİşlemler\nKoşullar.\n{_filler(3)}\n"
        "Bilgi edinilmesini ve gereğini rica ederim.",
    ]
)


def test_parts_restart_the_numbering_and_prefix_the_section_number() -> None:
    split = split_act(PARTS)

    assert [s.section_no for s in split.sections] == [
        INTRO,
        "K1",
        "K1-1",
        "K1-1.1",
        "K1-2",
        "K2",
        "K2-B1",
        "K2-B2",
        "K2-B2-1",
    ]
    by_no = {s.section_no: s for s in split.sections}
    assert by_no[INTRO].text == f"Bu Genelge emeklilik işlemlerini açıklar.\n{_filler(1)}"
    assert by_no["K1"].heading == "TEMEL KAVRAMLAR"
    assert by_no["K1"].text == "BİRİNCİ KISIM\nTEMEL KAVRAMLAR\nKavramlar aşağıdadır."
    assert by_no["K1"].children == ["K1-1", "K1-2"]
    assert by_no["K1-2"].text == f"2. Yaş\nYaş tanımı.\n{_filler(2)}"
    assert by_no["K2-B1"].text == (
        "BİRİNCİ BÖLÜM\nYAŞLILIK SİGORTASI\nBu bölümün numaralı başlığı yoktur."
    )  # the page number that follows is gone
    assert by_no["K2-B2"].children == ["K2-B2-1"]
    assert by_no["K2-B2-1"].heading == "Malul Sayılma Koşullarının Tespiti ve Kurumca Yapılacak"
    assert split.toc_unmatched == []
    assert (split.ref, split.issue_date) == ("2018/38", date(2018, 11, 6))
    assert split.incorporated == [
        {"date": "2019-08-15", "ref": "2019/16"},
        {"date": "2026-05-21", "ref": "2026/14"},
    ]


def test_a_skipped_or_misnumbered_heading_is_flagged() -> None:
    text = (
        "1. Bir\nMetin.\n1.1. Alt\nMetin.\n1.3. Atlanan\nMetin.\n1.2.2.5. Yanlış numara\nMetin.\n"
        "2. İki\nMetin."
    )

    split = split_act(text)

    by_no = {s.section_no: s for s in split.sections}
    assert list(by_no) == ["1", "1.1", "1.3", "2"]
    assert by_no["1.3"].warnings == ["number_skipped:1.2->1.3", "unplaced_heading:1.2.2.5"]
    assert "1.2.2.5. Yanlış numara" in by_no["1.3"].text
    assert by_no["2"].warnings == ["closing_not_found"]
    assert confidence.band(by_no["1.3"].warnings) == "low"
    assert confidence.band(by_no["2"].warnings) == "medium"
    assert confidence.band(by_no["1"].warnings) == "high"


def test_a_page_without_text_lowers_the_sections_on_it() -> None:
    text = PAGE_BREAK.join(
        [f"1. Bir\n{_filler(1)}", "", f"devam eden metin\n{_filler(2)}\n2. İki\n{_filler(3)}"]
    )

    split = split_act(text)

    assert split.pages_without_text == [2]
    assert [s.warnings for s in split.sections] == [
        ["page_without_text:2"],
        ["closing_not_found"],
    ]
    assert confidence.band(split.sections[0].warnings) == "low"


def test_amendment_notes_are_read_from_the_section() -> None:
    text = (
        "2. Koşullar\n(Değişik, 17/09/2021 tarihli ve 2021/32 sayılı Genelge) Yeni metin.\n"
        "(Ek: 7/2/2025 tarihli ve 2025/4 sayılı\nGenelge) Ek metin.\n(Mülga, okunamayan not)"
    )

    notes, unread = amendments(text)

    assert notes == [
        {"kind": "amended", "date": "2021-09-17", "ref": "2021/32"},
        {"kind": "added", "date": "2025-02-07", "ref": "2025/4"},
    ]
    assert unread == 1


def test_a_section_that_is_only_a_repeal_note_is_repealed() -> None:
    split = split_act(
        "1. Bir\nMetin.\n1.1- (Mülga: 09/04/2026 tarihli ve 2026/9 sayılı Genelge)\n"
        "1.2- Alt\nMetin."
    )

    assert [is_repealed(s) for s in split.sections] == [False, True, False]
