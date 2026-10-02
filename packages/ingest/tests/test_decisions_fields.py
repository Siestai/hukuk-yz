from typing import Any

import pytest
from conftest import era1_text, era2_text, era3_text, era4_text, foreign_text

from hukuk_ingest.decisions.clean import clean_journal
from hukuk_ingest.decisions.fields import (
    DecisionFields,
    extract_fields,
    normalize_case_no,
    parse_date,
    resolve_statute,
)
from hukuk_ingest.decisions.layout import detect_layout
from hukuk_ingest.decisions.parse import parse_text


def parse(text: str) -> DecisionFields:
    journal = clean_journal(text)
    return extract_fields(journal, detect_layout(journal))


# --- normalisation --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2017/16188", ("2017/16188", "")),
        ("2010 / 37635", ("2010/37635", "")),
        ("ESAS NO: 2003/18121", ("2003/18121", "")),
        ("2024/10-389", ("2024/389", "10")),  # HGK: D-N, D is the source chamber
        ("2031/9-374", ("2031/374", "9")),
        ("2031/(7)22-1234", ("2031/1234", "22")),
        ("2031/27016 E", ("2031/27016", "")),
        ("/2031/8232", ("2031/8232", "")),
    ],
)
def test_case_number_variants_normalise_to_year_slash_number(
    raw: str, expected: tuple[str, str]
) -> None:
    assert normalize_case_no(raw) == expected


def test_case_number_without_year_is_rejected() -> None:
    assert normalize_case_no("12/431") is None


@pytest.mark.parametrize(
    "raw",
    ["07.06.2004", "7.6.2004", "07/06/2004", "7 Haziran 2004", "07 haziran 2004", "7-6-2004"],
)
def test_date_variants_normalise_to_iso(raw: str) -> None:
    assert parse_date(raw) == ("2004-06-07", False)


def test_date_with_spaces_and_trailing_junk() -> None:
    assert parse_date("21.05 .2013") == ("2013-05-21", False)
    assert parse_date("07.06.2023T.C") == ("2023-06-07", False)


@pytest.mark.parametrize("raw", ["31.02.2004", "23.00.2010"])
def test_nonexistent_date_is_empty_and_flagged_invalid(raw: str) -> None:
    assert parse_date(raw) == (None, True)


def test_five_digit_year_is_not_a_date() -> None:
    assert parse_date("08/04/20219") == (None, False)


def test_invalid_decision_date_adds_a_warning() -> None:
    f = parse(era2_text(tarih="31.02.2012"))
    assert f.decision_date == ""
    assert "invalid_date" in f.warnings


# --- court and chamber ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("court_lines", "chamber"),
    [
        ("T.C\nYARGITAY\n9. HUKUK DAİRESİ", "9. HD"),
        ("T.C.\nYARGITAY\n9.Hukuk Dairesi", "9. HD"),
        ("YARGITAY\n22. HUKUK \nDAİRESİ", "22. HD"),
        ("T.C\nY A R G I T A Y\n10. Hukuk Dairesi", "10. HD"),
        ("T.C\nYARGITAY\n5. CEZA DAİRESİ", "5. CD"),
    ],
)
def test_chamber_is_canonical(court_lines: str, chamber: str) -> None:
    f = parse(era2_text(court=court_lines))
    assert (f.court, f.court_level, f.chamber, f.jurisdiction) == (
        "yargitay",
        "daire",
        chamber,
        "adli",
    )


def test_court_in_the_body_is_not_the_court() -> None:
    # The decision cites another chamber and a BAM; the header block says 9. HD.
    text = era2_text().replace(
        "Yerel mahkeme, isteği reddetmiştir.",
        "MAHKEMESİ : ... BÖLGE ADLİYE MAHKEMESİ 24. HUKUK DAİRESİ\n"
        "Yargıtay 10. Hukuk Dairesince verilen karar uyarınca; BÖLGE ADLİYE MAHKEMESİ.",
    )
    f = parse(text)
    assert (f.court, f.chamber) == ("yargitay", "9. HD")


def test_keywords_mentioning_another_court_do_not_change_the_court() -> None:
    text = era2_text().replace("• ÖRNEK ANAHTAR BİR", "• ANAYASA MAHKEMESİNİN İPTAL KARARI")
    assert parse(text).court == "yargitay"


def test_bam_header_gives_chamber_and_region() -> None:
    f = parse(era2_text(court="T.C\nANKARA\nBÖLGE ADLİYE MAHKEMESİ\n6.HUKUK DAİRESİ"))
    assert (f.court, f.court_level, f.chamber, f.bam_region, f.jurisdiction) == (
        "bam",
        "bam_bim",
        "6. HD",
        "Ankara",
        "adli",
    )


def test_bam_region_on_the_same_line() -> None:
    f = parse(era2_text(court="T.C.\nİSTANBUL BÖLGE ADLİYE MAHKEMESİ\n50. HUKUK DAİRESİ"))
    assert (f.court, f.chamber, f.bam_region) == ("bam", "50. HD", "İstanbul")


def test_hgk_header_has_no_chamber_and_keeps_the_source_chamber() -> None:
    f = parse(era2_text(court="T.C\nYARGITAY\nHukuk Genel Kurulu", esas="2031/9-374"))
    assert (f.court, f.court_level, f.chamber) == ("yargitay", "hgk_iddk", "")
    assert (f.esas_no, f.source_chamber) == ("2031/374", "9")


def test_ibk_header() -> None:
    f = parse(
        era2_text(court="YARGITAY İÇTİHADI BİRLEŞTİRME\nBÜYÜK GENEL KURULU KARARI", esas="2031/5")
    )
    assert (f.court, f.court_level, f.decision_kind, f.chamber) == ("yargitay", "ibk", "ibk", "")


def test_aym_individual_application_uses_basvuru_no_and_has_no_karar_no() -> None:
    text = (
        "Yargıtay Kararları – Çalışma ve Toplum, 2025/4\n1\nİlgili Kanun / Madde\n6356 S. STK/39\n"
        "T.C\nANAYASA MAHKEMESİ\nBaşvuru No. 2031/18821\nKarar No.\nTarihi: 20/3/2025\n"
        "•ÖRNEK ANAHTAR\nÖZETİ: Özet.\nI. BAŞVURUNUN KONUSU\nMetin " + "x" * 800
    )
    f = parse(text)
    assert (f.court, f.court_level, f.decision_kind, f.chamber) == (
        "aym",
        "aym",
        "bireysel_basvuru",
        "",
    )
    assert (f.esas_no, f.karar_no, f.decision_date) == ("2031/18821", "", "2025-03-20")


def test_danistay_is_administrative() -> None:
    f = parse(era2_text(court="T.C.\nDANIŞTAY\n10. DAİRESİ"))
    assert (f.court, f.court_level, f.chamber, f.jurisdiction) == (
        "danistay",
        "daire",
        "10. D",
        "idari",
    )
    kurul = parse(era2_text(court="DANIŞTAY\nİDARİ DAVA DAİRELERİ KURULU"))
    assert (kurul.court_level, kurul.chamber) == ("hgk_iddk", "")


def test_foreign_articles_are_classified_by_their_section() -> None:
    f = parse(foreign_text())
    assert (f.court, f.court_level, f.esas_no, f.decision_date) == (
        "foreign",
        "international",
        "",
        "2005-06-29",
    )
    ecj = parse(foreign_text().replace("Hamm Eyalet İş Mahkemesi*", "Avrupa Adalet Divanı"))
    assert ecj.court == "abad"
    ecthr = parse(
        "Avrupa İnsan Hakları Mahkemesi\n1\nÖrnek Başlık\nAvrupa İnsan Hakları Mahkemesi\n"
        "Örnek/Ülke Kararı\n(Başvuru no. 1/16)\n06 Kasım 2025\nGİRİŞ\nMetin " + "x" * 800
    )
    assert (ecthr.court, ecthr.decision_date) == ("aihm", "2025-11-06")


# --- layouts --------------------------------------------------------------------------------


def test_era2_fields_summary_and_body_are_separated() -> None:
    f = parse(era2_text())
    assert (f.esas_no, f.karar_no, f.decision_date) == ("2011/12345", "2012/6789", "2012-06-07")
    assert f.keywords == ["ÖRNEK ANAHTAR BİR", "ÖRNEK ANAHTAR İKİ SATIR KIRILIMI"]
    assert f.editorial_summary == "Örnek özet birinci satır\nikinci satır özet."
    assert f.full_text.startswith("DAVA: Davacı, örnek talebin")
    assert f.full_text.rstrip().endswith("karar verildi.")
    assert "Yargıtay Kararları" not in f.full_text
    assert "118" not in f.full_text.split("\n")[:60]
    assert (f.outcome, f.text_completeness) == ("bozma", "full")


def test_era1_court_block_after_the_summary() -> None:
    f = parse(era1_text())
    assert (f.court, f.chamber, f.esas_no, f.karar_no, f.decision_date) == (
        "yargitay",
        "10. HD",
        "2003/111",
        "2003/222",
        "2003-11-06",
    )
    assert f.editorial_summary == "Örnek özet satırı\nikinci satır."
    assert f.full_text.startswith("DAVA: Davacı")
    assert f.keywords == ["ÖRNEK ANAHTAR"]
    assert f.outcome == "onama"


def test_era3_values_follow_the_labels_in_order() -> None:
    f = parse(era3_text())
    assert (f.chamber, f.esas_no, f.karar_no, f.decision_date) == (
        "22. HD",
        "2014/90305",
        "2014/91998",
        "2014-02-11",
    )
    assert f.outcome == "düzelterek onama"
    assert f.related_articles[0]["articles"] == ["25", "26"]


def test_era4_template_body_and_ruling() -> None:
    f = parse(era4_text())
    assert f.full_text.startswith("I. DAVA")
    assert f.outcome == "bozma"
    assert f.editorial_summary == "Örnek özet."


def test_unlabelled_value_rows_are_read_as_esas_karar_tarih() -> None:
    text = (
        "T.C.\nYARGITAY\n9.Hukuk Dairesi\nYARGITAY İLAMI\n2004/99118\n2004/99119\n"
        "Örnek Asliye Hukuk Hakimliği (İş)\n1.3.2004\nadına Avukat Örnek Kişi\n"
        "DAVA: Davacı, örnek talebi istemiştir.\n" + "Örnek cümle. " * 80
    )
    f = parse(text)
    assert (f.court, f.chamber, f.esas_no, f.karar_no, f.decision_date) == (
        "yargitay",
        "9. HD",
        "2004/99118",
        "2004/99119",
        "2004-03-01",
    )


def test_no_body_marker_means_summary_only_and_a_warning() -> None:
    text = (
        "T.C\nYARGITAY\n9. HUKUK DAİRESİ\nEsas No. 2011/1\nKarar No. 2012/2\nTarihi: 07.06.2012\n"
    )
    record = parse_text(
        text + "ÖZETİ: Sadece özet.\n", "Yargi_Kararlari_Arsivi/9.Sayı-X/a.pdf", "ab" * 32
    )
    assert record.text_completeness == "summary_only"
    assert record.full_text == ""
    assert "body_not_found" in record.warnings
    assert "full_text" in record.missing


def test_short_body_is_an_excerpt() -> None:
    f = parse(era2_text().split("Hüküm süresi")[0] + "Hüküm süresi içinde temyiz edilmiş olmakla.")
    assert f.text_completeness == "excerpt"


# --- related articles -----------------------------------------------------------------------


def related(lines: str, tarih: str = "07.06.2012") -> list[dict[str, Any]]:
    return parse(era2_text(related=lines, tarih=tarih)).related_articles


def test_article_ranges_lists_and_labels() -> None:
    assert related("4857 S. İşK/18-21") == [
        {
            "statute": 4857,
            "label": "İşK",
            "articles": ["18", "19", "20", "21"],
            "raw": "4857 S. İşK/18-21",
        }
    ]
    assert related("4857 S.İşK/2,17-18, 41")[0]["articles"] == ["2", "17", "18", "41"]


def test_sub_items_stay_strings() -> None:
    assert related("4857 S. İşK/4/1-c")[0]["articles"] == ["4/1-c"]
    assert related("6100 S. HMK/Geç. 3")[0]["articles"] == ["Geç. 3"]
    assert related("5620 S. K/Ek-2")[0]["articles"] == ["Ek-2"]
    assert related("1475 S.İş.K/17/II")[0]["articles"] == ["17/II"]


def test_several_statutes_and_raw_is_kept() -> None:
    entries = related("4857 S. İşK/18-21\n1475 s.İşK: 14\n6356 S. STK/25")
    assert [(e["statute"], e["articles"][0]) for e in entries] == [
        (4857, "18"),
        (1475, "14"),
        (6356, "25"),
    ]
    assert entries[1]["raw"] == "1475 s.İşK: 14"


def test_printed_statute_number_wins_over_the_abbreviation() -> None:
    assert resolve_statute(6356, "İşK", "2012-01-01") == (6356, False)


@pytest.mark.parametrize(
    ("label", "decision_date", "expected"),
    [
        ("BK", "2003-11-06", (818, True)),
        ("BK", "2012-07-01", (6098, True)),
        ("HUMK", "2011-09-30", (1086, True)),
        ("HMK", "2011-10-01", (6100, True)),
        ("İşK", "2003-06-09", (1475, True)),
        ("İşK", "2003-06-10", (4857, True)),
        ("İşK", None, (None, False)),  # dated abbreviation without a decision date
        ("SGK", None, (5510, False)),
        ("Bağ-Kur K", None, (1479, False)),
        ("STK", None, (6356, False)),
        ("XYZ", "2012-01-01", (None, False)),
    ],
)
def test_abbreviation_mapping(
    label: str, decision_date: str | None, expected: tuple[int | None, bool]
) -> None:
    assert resolve_statute(None, label, decision_date) == expected


def test_dated_abbreviation_adds_the_inferred_warning() -> None:
    f = parse(era2_text(related="BK:90", tarih="06.11.2003"))
    assert f.related_articles[0]["statute"] == 818
    assert "statute_inferred_from_date" in f.warnings


def test_unmapped_abbreviation_keeps_the_raw_label() -> None:
    f = parse(era2_text(related="ZZK/5"))
    assert f.related_articles[0]["statute"] is None
    assert f.related_articles[0]["label"] == "ZZK"
    assert "statute_unmapped" in f.warnings


def test_keyword_lines_are_not_mistaken_for_articles() -> None:
    f = parse(era2_text(related="4857 S. İşK/18"))
    assert len(f.related_articles) == 1


# --- warnings, outcome ----------------------------------------------------------------------


def test_second_esas_candidate_is_reported_not_silently_chosen() -> None:
    text = era2_text().replace("Karar No. 2012/6789\n", "Karar No. 2012/6789\nEsas No. 2010/99\n")
    f = parse(text)
    assert f.esas_no == "2011/12345"
    assert "multiple_esas_candidates:2010/99" in f.warnings


@pytest.mark.parametrize(
    ("result", "outcome"),
    [
        ("Kararın BOZULMASINA, karar verildi.", "bozma"),
        ("Kararın ONANMASINA, karar verildi.", "onama"),
        ("Kararın DÜZELTİLEREK ONANMASINA, karar verildi.", "düzelterek onama"),
        ("Davanın KABULÜNE, karar verildi.", "kabul"),
        ("Davanın REDDİNE, karar verildi.", "red"),
        ("Hakkın İHLAL EDİLDİĞİNE, karar verildi.", "ihlal"),
        ("Hakkın İHLAL EDİLMEDİĞİNE, karar verildi.", "ihlal_yok"),
    ],
)
def test_outcome_from_the_closing_section(result: str, outcome: str) -> None:
    assert parse(era2_text(result=result)).outcome == outcome


def test_outcome_stays_empty_without_a_ruling() -> None:
    assert parse(era2_text(result="Gerekçe devam ediyor.")).outcome == ""


def test_dissent_after_the_ruling_does_not_change_the_outcome() -> None:
    text = (
        era2_text()
        + "\nMUHALEFET ŞERHİ\nÇoğunluk görüşüne katılmıyoruz; kararın ONANMASI gerekirdi."
    )
    assert parse(text).outcome == "bozma"


def test_parse_text_record_has_provenance_and_constant_verification() -> None:
    record = parse_text(
        era4_text(), "Yargi_Kararlari_Arsivi/80.Sayı-Yargı Kararları (76)/a.pdf", "cd" * 32
    )
    assert (record.journal_issue, record.journal_year, record.journal_no, record.journal_page) == (
        80,
        2024,
        1,
        1,
    )
    assert (record.layout, record.verification, record.status) == (
        "era4_new_template",
        "unverified",
        "ok",
    )
    assert record.sha256 == "cd" * 32
    assert record.missing == []
