import json
from pathlib import Path
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
from hukuk_ingest.pipeline import cache_base

DATA = Path(__file__).resolve().parents[3] / "data" / "extracted"
GOLD = Path(__file__).parent / "gold" / "decisions_gold.jsonl"


def parse(text: str) -> DecisionFields:
    journal = clean_journal(text)
    return extract_fields(journal, detect_layout(journal))


# --- OCR typos in header labels ----------------------------------------------------------------


def _header(karar_line: str, tarih_line: str, between: str = "") -> str:
    return era2_text().replace(
        "Karar No. 2012/6789\nTarihi: 07.06.2012", f"{karar_line}\n{between}{tarih_line}"
    )


@pytest.mark.parametrize(
    "karar_line",
    ["KARAR N0: 2012/6789", "KARAR NO0: 2012/6789", "KARAR: 2012/6789", "Karr No. 2012/6789"],
)
def test_ocr_karar_label_does_not_stop_the_header_scan(karar_line: str) -> None:
    f = parse(_header(karar_line, "Tarihi: 07.06.2012"))
    assert (f.karar_no, f.decision_date) == ("2012/6789", "2012-06-07")


@pytest.mark.parametrize(
    "tarih_line",
    ["TARİH: 07.06.2012", "TARTHi :07.06.2012", "TARIHI 07.06.2012", "Tar;h;: 07.06.2012",
     "TARİHİ : 07.06.2012", "Karar Tç07/06/2012"],
)  # fmt: skip
def test_ocr_tarih_label_variants(tarih_line: str) -> None:
    assert parse(_header("Karar No. 2012/6789", tarih_line)).decision_date == "2012-06-07"


def test_court_of_origin_lines_do_not_stop_the_scan() -> None:
    # The origin block sits between the numbers and the date, so Karar No still comes through.
    between = "MAHKEMESI \n:\nAdana 2. İş Mahkemesi\n"
    f = parse(_header("Karar No. 2012/6789", "Tarihi: 07.06.2012", between))
    assert f.karar_no == "2012/6789"


_ILAMI_TEXT = (
    "T.C.\nYARGITAY\n9.HUKUK DAİRESİ\nYARGITAY İLAMI\nESAS NO \n:\n2004/784\nKARAR NO \n:\n"
    "2004/13279\nMAHKEMESİ \n:\nAdana 2bİş Mahkemesi\nTARİHİ 12.12.2003\nNO 230-1403\n"
    "DAVACI Örnek Kişi adına Avukat Örnek\nDAVA :Davacı, örnek talebi istemiştir.\n"
    + "Örnek cümle. "
    * 80
)


def test_date_after_the_origin_court_is_the_lower_courts_and_stays_empty() -> None:
    f = parse(_ILAMI_TEXT)
    assert (f.esas_no, f.karar_no) == ("2004/784", "2004/13279")
    assert f.decision_date == ""
    assert "date_is_lower_court" in f.warnings


def test_inline_origin_court_with_ocr_labels_stays_empty() -> None:
    text = (
        "T.C.\nYARGITAY \n9.HUKUK DAIRESi\nYARGITAY I LAM I\nESAS NO :2004/278\n"
        "KARAR NO =2004/12229\nMAHKEMESI :Bursa 2.1$ Mahkemesi\nTARTHi :8.10.2003\n"
        "NO : 169-716\nDAVACI :Örnek\nDAVA :Davaci, ornek talebi istemistir.\n" + "Örnek. " * 80
    )
    f = parse(text)
    assert (f.karar_no, f.decision_date) == ("2004/12229", "")
    assert "date_is_lower_court" in f.warnings


def test_date_before_the_origin_court_is_taken() -> None:
    text = _ILAMI_TEXT.replace(
        "MAHKEMESİ \n:\nAdana 2bİş Mahkemesi\nTARİHİ 12.12.2003\nNO 230-1403\n",
        "TARİHİ 07.06.2004\nMAHKEMESİ \n:\nAdana 2bİş Mahkemesi\nNO 230-1403\n",
    )
    f = parse(text)
    assert f.decision_date == "2004-06-07"
    assert "date_is_lower_court" not in f.warnings


def test_ocr_labels_never_pick_values_from_the_body() -> None:
    # Header without a date; the body starts with a line that looks like a typo'd label.
    text = era2_text().replace("Tarihi: 07.06.2012\n", "")
    body = "KARAR: 01.01.2020 tarihli\nTARİH: 02.02.2020\nDAVA: Davacı"
    text = text.replace("DAVA: Davacı", body)
    f = parse(text)
    assert f.decision_date == ""


def test_ocr_label_with_prose_value_is_not_a_value() -> None:
    f = parse(_header("KARAR: verildi", "Tarihi: 07.06.2012"))
    assert f.karar_no == ""


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


@pytest.mark.parametrize("raw", ["08/04/20219", "12.05.20", "7.6.200"])
def test_malformed_year_is_empty_and_flagged_invalid(raw: str) -> None:
    assert parse_date(raw) == (None, True)


def test_text_without_a_date_token_is_not_invalid() -> None:
    assert parse_date("") == (None, False)
    assert parse_date("tarihsiz") == (None, False)


@pytest.mark.parametrize("tarih", ["31.02.2012", "08/04/20219"])
def test_invalid_decision_date_adds_a_warning(tarih: str) -> None:
    f = parse(era2_text(tarih=tarih))
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
        ("YARGITAY\n9. HUKUK \nAİRESİ", "9. HD"),  # wrapped header lost the "D"
        ("YARGITAY\n9. HUKUK \nDAİRESİ", "9. HD"),
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


def _warnings(court: str) -> list[str]:
    return parse_text(era2_text(court=court), "p", "ab" * 32).warnings


def test_daire_without_a_chamber_number_warns() -> None:
    warnings = _warnings("T.C\nYARGITAY\nHUKUK DAİRESİ")
    assert "chamber_missing" in warnings
    assert "chamber_missing" in _warnings("T.C.\nİSTANBUL\nBÖLGE ADLİYE MAHKEMESİ\nHUKUK DAİRESİ")


def test_chamber_missing_is_not_reported_for_found_or_chamberless_courts() -> None:
    assert "chamber_missing" not in _warnings("T.C\nYARGITAY\n9. HUKUK DAİRESİ")
    assert "chamber_missing" not in _warnings("T.C\nYARGITAY\nHUKUK GENEL KURULU")


def test_karar_year_differing_from_the_date_year_is_flagged_not_changed() -> None:
    record = parse_text(era2_text(karar="2011/6789"), "p", "ab" * 32)
    assert record.karar_no == "2011/6789"
    assert record.decision_date == "2012-06-07"
    assert "karar_year_ne_date_year" in record.warnings
    assert "karar_year_ne_date_year" not in parse_text(era2_text(), "p", "ab" * 32).warnings


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
        ("XYZ", "2012-01-01", (None, False)),
    ],
)
def test_abbreviation_mapping(
    label: str, decision_date: str | None, expected: tuple[int | None, bool]
) -> None:
    assert resolve_statute(None, label, decision_date) == expected


@pytest.mark.parametrize(
    ("label", "decision_date", "expected"),
    [
        ("STK", "2012-11-06", (2821, True)),  # Sendikalar Kanunu until 6356 came into force
        ("STK", "2012-11-07", (6356, True)),
        ("STSK", "2012-11-06", (2821, True)),
        ("STSK", "2012-11-07", (6356, True)),
        ("STİSK", "2012-11-06", (2821, True)),
        ("STİSK", "2012-11-07", (6356, True)),
        ("TSK", "2012-11-06", (2822, True)),  # TİSGLK 2822 until 6356 replaced its content
        ("TSK", "2012-11-07", (6356, True)),
        ("TSGLK", "2012-11-06", (2822, True)),
        ("TSGLK", "2012-11-07", (6356, True)),
        ("STK", None, (None, False)),  # dated abbreviation without a decision date
        ("TSGLK", None, (None, False)),
    ],
)
def test_union_statute_abbreviations_change_at_6356(
    label: str, decision_date: str | None, expected: tuple[int | None, bool]
) -> None:
    assert resolve_statute(None, label, decision_date) == expected


def test_union_abbreviation_is_inferred_from_the_decision_date_in_a_record() -> None:
    f = parse(era2_text(related="STK/25", tarih="03.03.2009"))
    assert f.related_articles[0]["statute"] == 2821
    assert "statute_inferred_from_date" in f.warnings


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


# --- gold set -------------------------------------------------------------------------------


def _gold_rows() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if "_meta" not in r]


@pytest.mark.skipif(not DATA.is_dir(), reason="data/extracted not available")
def test_gold_set_accuracy() -> None:
    rows = _gold_rows()
    assert len(rows) >= 60
    hits: dict[str, int] = {}
    for row in rows:
        clean = cache_base(DATA, row["sha256"]).with_suffix(".clean.txt")
        if not clean.is_file():
            pytest.skip("gold decision text is not in data/extracted")
        got = parse_text(clean.read_text(encoding="utf-8"), "gold", row["sha256"]).to_dict()
        for name in (
            "court",
            "court_level",
            "chamber",
            "esas_no",
            "karar_no",
            "decision_date",
            "layout",
        ):
            hits[name] = hits.get(name, 0) + (got[name] == row[name])
        want = [(e["statute"], e["articles"]) for e in row["related_articles"]]
        have = [(e["statute"], e["articles"]) for e in got["related_articles"]]
        hits["related_articles"] = hits.get("related_articles", 0) + (want == have)
    accuracy = {name: n / len(rows) for name, n in hits.items()}
    for name in ("court", "court_level", "chamber", "esas_no", "karar_no", "decision_date"):
        assert accuracy[name] == 1.0, (name, accuracy)
    assert accuracy["related_articles"] >= 0.95, accuracy
    assert accuracy["layout"] >= 0.95, accuracy
