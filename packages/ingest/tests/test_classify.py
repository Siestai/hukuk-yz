"""Detection of the type and reference fields from extracted text (task 13a). Synthetic texts in
the layouts of the real files; the language model is a fake `Detector`."""

from typing import Any

import pytest

from hukuk_ingest.classify import Suggestions, classify
from hukuk_ingest.classify.evidence import DOC_TYPES, collapse, locate
from hukuk_ingest.classify.llm import (
    MAX_CHARS,
    DetectorError,
    DetectRequest,
    DetectResult,
    answer_schema,
    excerpt,
)
from hukuk_ingest.classify.similar import containment, shingles

KANUN = """DENEME KANUNU
(ESKİ KANUN ADI VE DİĞER KANUNLAR)

\t\tKanun Numarası\t\t: 9001
\t\tKabul Tarihi\t\t: 22/5/2003
\t\tYayımlandığı R.Gazete\t: Tarih :  10/6/2003   Sayı : 25134

Madde 1 - Bu Kanunun amacı işçilerin hak ve sorumluluklarını düzenlemektir.
"""

YONETMELIK = """ALT İŞVERENLİK YÖNETMELİĞİ
BİRİNCİ BÖLÜM
Amaç ve Kapsam
MADDE 1 –(1) Bu Yönetmeliğin amacı, asıl işveren-alt işveren ilişkisini düzenlemektir.
"""

YONETMELIK_RG_FIRST = """Resmi Gazete Tarihi: 18.11.2008 Resmi Gazete Sayısı: 27058
ÜCRET, PRİM, İKRAMİYE VE BU NİTELİKTEKİ HER TÜRLÜ İSTİHKAKIN
BANKALAR ARACILIĞIYLA ÖDENMESİNE DAİR YÖNETMELİK
BİRİNCİ BÖLÜM
MADDE 1 – (1) Bu Yönetmeliğin amacı ücretin bankalar aracılığıyla ödenmesidir.
"""

TEBLIG = """MUHTASAR VE PRİM HİZMET BEYANNAMESİ GENEL
TEBLİĞİ (SIRA NO: 1)
Resmi Gazete No:
29983
Resmi Gazete Tarihi:
18/02/2017
Amaç ve kapsam
MADDE 1 – (1) Bu Tebliğin amacı usul ve esasları belirlemektir.
"""

GENELGE = """T.C.
SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI
Sigorta Primleri Genel Müdürlüğü
Sayı : E-69053920-010.06.01-24043199 16.04.2021
Konu : Yapı Ruhsatı Başvurularında
Çalıştırılacağı Bildirilen Sigortalıların
Tescil İşlemleri
GENELGE
2021/11
Bilindiği üzere, 18.06.2020 tarihli ve 2020/20 sayılı Genelgenin hükümleri uygulanır.
"""

GENELGE_OLD = """T.C.
SOSYAL GÜVENLPK KURUMU BAŞKANLIĞI
Sayı : 82200845/788
Konu : Tarımsal Kesinti Uygulaması
02/07/2013
GENELGE
İ2013-27
1- Genel Açıklamalar
"""

GENELGE_TITLE = """EMEKLİLİK HİZMETLERİ GENEL
MÜDÜRLÜĞÜ
2013/11 SAYILI SİGORTALILIK İŞLEMLERİ
HAKKINDA GENELGE
(2/9/2025 tarihli ve 2025/15 sayılı Genelge İşlenmiş Haliyle)
"""

IC_EMRI = """T.C.
SOSYAL GÜVENLİK KURUMU
Rehberlik ve Teftiş Başkanlığı
2014/04
İÇ EMİR
Sayı : 16747942-19623529 30/12/2014
Konu : İş Kazası ve Meslek Hastalığı Soruşturmaları.
"""

GENEL_YAZI = """T.C.
SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI
Hukuk Müşavirliği
Sayı : E-72044944-640-45915510 23.05.2022
Konu : 5510 Sayılı Kanunun 39 uncu Madde
Uygulaması
EMEKLİLİK HİZMETLERİ GENEL MÜDÜRLÜĞÜNE
İlgi : 28.04.2022 tarihli ve 44830110 sayılı yazınız.
"""

KARAR = """Yargıtay Kararları – Çalışma ve Toplum, 2021/4
3231
İlgili Kanun / Madde
6100 S. HMK/110
T.C
YARGITAY
9. HUKUK DAİRESİ
Esas No. 2021/5329
Karar No. 2021/9588
Tarihi: 26.05.2021
DAVALARIN YIĞILMASI
ÖZETİ: Davaların yığılması halinde her talep için ayrı ıslah yapılabilir.
DAVA: Davacı, alacaklarının tahsilini istemiştir.
"""

KARAR_TWO_COLUMN = """YARGITAY
9. HUKUK DAİRESİ
Esas No.
Karar No.
Tarihi:
2013/10344
2013/28364
06.11.2013
İlgili Kanun / Madde
6100 S.HMK/107
ÖZETİ Davacının talepleri aynı dilekçede ileri sürülmüştür.
DAVA: Davacı alacaklarını istemiştir.
"""

KARAR_SITE = """22. Hukuk Dairesi         2017/5455 E.  ,  2017/4143 K.
"İçtihat Metni"
MAHKEMESİ :İş Mahkemesi
Taraflar arasında görülen dava sonucunda verilen kararın temyizen incelenmesi istenilmiştir.
Y A R G I T A Y K A R A R I
Gereği düşünüldü. 12.04.2017 gününde oy birliğiyle karar verildi.
"""


def found(text: str, detected_type: str = "pdf") -> dict[str, Any]:
    """The suggestions as `{field: value}`; every quote must occur in the text."""
    suggestions = classify(text, detected_type, "x.pdf").suggestions
    for name, suggestion in suggestions.items():
        assert suggestion.source == "rule", name
        assert suggestion.evidence is not None, name
        if "quote" in suggestion.evidence:
            assert collapse(suggestion.evidence["quote"]) in collapse(text), name
    return {name: s.value for name, s in suggestions.items()}


def test_a_kanun_header_gives_type_number_date_and_title() -> None:
    result = classify(KANUN, "pdf", "x.pdf").suggestions
    assert {name: s.value for name, s in result.items()} == {
        "doc_type": "kanun",
        "official_ref": "9001",
        "doc_date": "2003-06-10",
        "title": "DENEME KANUNU",
    }
    assert result["doc_date"].evidence == {
        "page": 1,
        "quote": "R.Gazete : Tarih : 10/6/2003 Sayı : 25134",
    }
    assert result["official_ref"].evidence == {"page": 1, "quote": "Kanun Numarası : 9001"}


def test_a_yonetmelik_and_a_teblig_are_told_by_the_word_that_ends_the_heading() -> None:
    assert found(YONETMELIK) == {"doc_type": "yonetmelik", "title": "ALT İŞVERENLİK YÖNETMELİĞİ"}
    assert found(TEBLIG) == {
        "doc_type": "teblig",
        "title": "MUHTASAR VE PRİM HİZMET BEYANNAMESİ GENEL TEBLİĞİ (SIRA NO: 1)",
        "doc_date": "2017-02-18",
        "official_ref": "RG 29983",
    }


def test_a_resmi_gazete_line_before_the_title_is_skipped_and_gives_the_date() -> None:
    result = found(YONETMELIK_RG_FIRST)
    assert result["doc_type"] == "yonetmelik"
    assert result["doc_date"] == "2008-11-18"
    assert result["official_ref"] == "RG 27058"
    assert result["title"].endswith("BANKALAR ARACILIĞIYLA ÖDENMESİNE DAİR YÖNETMELİK")


def test_a_genelge_gives_number_date_subject_and_issuer() -> None:
    assert found(GENELGE) == {
        "doc_type": "genelge",
        "official_ref": "2021/11",
        "doc_date": "2021-04-16",
        "title": (
            "Yapı Ruhsatı Başvurularında Çalıştırılacağı Bildirilen Sigortalıların Tescil İşlemleri"
        ),
        "issuer": "SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI",
    }


def test_the_date_of_an_old_genelge_comes_after_the_konu_line() -> None:
    result = found(GENELGE_OLD)
    assert (result["official_ref"], result["doc_date"]) == ("2013/27", "2013-07-02")
    assert result["title"] == "Tarımsal Kesinti Uygulaması"


def test_a_genelge_heading_may_carry_the_number_in_the_title_line() -> None:
    result = found(GENELGE_TITLE)
    assert (result["doc_type"], result["official_ref"]) == ("genelge", "2013/11")


def test_an_ic_emri_is_not_taken_for_a_genel_yazi() -> None:
    assert found(IC_EMRI) == {
        "doc_type": "ic_emri",
        "official_ref": "2014/04",
        "doc_date": "2014-12-30",
        "title": "İş Kazası ve Meslek Hastalığı Soruşturmaları.",
        "issuer": "SOSYAL GÜVENLİK KURUMU",
    }


def test_a_letter_with_sayi_and_konu_but_no_genelge_heading_is_a_genel_yazi() -> None:
    assert found(GENEL_YAZI) == {
        "doc_type": "genel_yazi",
        "official_ref": "E-72044944-640-45915510",
        "doc_date": "2022-05-23",
        "title": "5510 Sayılı Kanunun 39 uncu Madde Uygulaması",
        "issuer": "SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI",
    }


def test_a_mixed_case_genelge_in_the_body_is_not_a_heading() -> None:
    assert (
        found("Bu yazı 2020/5 sayılı Genelge uyarınca düzenlendi.\n2020/5 Genelge İşlemleri") == {}
    )


def test_a_decision_is_read_by_the_archive_parser() -> None:
    result = classify(KARAR, "pdf", "k.pdf").suggestions
    assert {name: s.value for name, s in result.items()} == {
        "doc_type": "karar",
        "official_ref": "2021/5329 E., 2021/9588 K.",
        "title": "Yargıtay 9. HD 2021/5329 E., 2021/9588 K.",
        "issuer": "Yargıtay 9. HD",
        "doc_date": "2021-05-26",
    }
    assert result["doc_date"].evidence == {"page": 1, "quote": "Tarihi: 26.05.2021"}
    assert result["official_ref"].evidence == {
        "page": 1,
        "quote": "Esas No. 2021/5329 Karar No. 2021/9588",
    }


def test_a_decision_with_the_labels_apart_from_the_values_still_has_evidence() -> None:
    result = classify(KARAR_TWO_COLUMN, "pdf", "k.pdf").suggestions
    assert result["official_ref"].value == "2013/10344 E., 2013/28364 K."
    assert result["doc_date"].value == "2013-11-06"
    assert result["official_ref"].evidence is not None
    assert "2013/10344" in result["official_ref"].evidence["quote"]
    assert result["doc_date"].evidence == {"page": 1, "quote": "06.11.2013"}


def test_a_decision_in_the_header_of_the_court_site_is_found_with_its_closing_date() -> None:
    assert found(KARAR_SITE) == {
        "doc_type": "karar",
        "official_ref": "2017/5455 E., 2017/4143 K.",
        "title": "Yargıtay 22. Hukuk Dairesi 2017/5455 E., 2017/4143 K.",
        "issuer": "Yargıtay 22. Hukuk Dairesi",
        "doc_date": "2017-04-12",
    }


def test_the_page_of_a_quote_counts_form_feeds() -> None:
    result = classify("sayfa bir\n\f" + KANUN, "pdf", "x.pdf").suggestions
    assert result["official_ref"].evidence is not None
    assert result["official_ref"].evidence["page"] == 2


@pytest.mark.parametrize("detected", ["xlsx_xlsm", "xls"])
def test_a_spreadsheet_is_a_hesap_tablosu_by_its_file_type(detected: str) -> None:
    result = classify("", detected, "Bordro.xlsm").suggestions
    assert list(result) == ["doc_type"]
    assert result["doc_type"].value == "hesap_tablosu"
    assert result["doc_type"].evidence == {"file_type": detected}


def test_text_that_shows_nothing_gives_no_suggestion() -> None:
    assert found("Bugün hava çok güzel. Yarın da güzel olacak.") == {}
    assert found("") == {}


def test_the_doc_types_are_the_labels_of_the_app_enum() -> None:
    assert DOC_TYPES[0] == "kanun"
    assert len(set(DOC_TYPES)) == len(DOC_TYPES) == 12


# --- evidence ---------------------------------------------------------------------------------


def test_a_quote_is_found_ignoring_case_and_white_space_and_returns_the_text_as_printed() -> None:
    text = "ilk sayfa\fKanun  Numarası\n: 4857\nsonra"
    assert locate(text, "KANUN NUMARASI : 4857") == {"page": 2, "quote": "Kanun Numarası : 4857"}
    assert locate(text, "ısınma") is None
    assert locate(text, "  ") is None


def test_turkish_case_folding_keeps_i_and_dotless_i_apart() -> None:
    assert locate("SİGORTA PRİMİ", "sigorta primi") is not None
    assert locate("ISINMA", "ısınma") is not None
    assert locate("ISINMA", "isinma") is None


# --- the language-model fallback --------------------------------------------------------------


class FakeDetector:
    def __init__(self, answer: dict[str, Any] | None = None, error: str | None = None) -> None:
        self.answer = answer or {}
        self.error = error
        self.requests: list[DetectRequest] = []

    def detect(self, request: DetectRequest) -> DetectResult:
        self.requests.append(request)
        if self.error:
            raise DetectorError(self.error)
        return DetectResult(self.answer, "fake-model", 120, 30)


UNCLEAR = (
    "Başlıksız belge\nSayfa 1\n15 Mart 2021 tarihinde toplanan kurul, 2021/7 sayılı kararı aldı.\n"
)


def run(detector: FakeDetector, text: str = UNCLEAR) -> tuple[Suggestions, list[str]]:
    result = classify(text, "pdf", "belge.pdf", detector)
    return result.suggestions, result.warnings


def test_a_document_the_rules_fully_read_does_not_reach_the_model() -> None:
    detector = FakeDetector()
    classify(KANUN, "pdf", "kanun.pdf", detector)
    assert detector.requests == []  # type, date, ref and title found; only issuer is missing


def test_the_model_fills_the_missing_fields_with_evidence_from_the_text() -> None:
    detector = FakeDetector(
        {
            "doc_type": {"value": "diger", "quote": "kurul"},
            "doc_date": {"value": "2021-03-15", "quote": "15 Mart 2021"},
            "official_ref": {"value": "2021/7", "quote": "2021/7 sayılı kararı"},
            "title": {"value": "Kurul kararı", "quote": "Başlıksız belge"},
        }
    )
    suggestions, warnings = run(detector)
    assert warnings == []
    assert detector.requests[0].fields == (
        "doc_type",
        "doc_date",
        "official_ref",
        "title",
        "issuer",
    )
    assert detector.requests[0].file_name == "belge.pdf"
    assert {name: (s.value, s.source) for name, s in suggestions.items()} == {
        "doc_type": ("diger", "llm"),
        "doc_date": ("2021-03-15", "llm"),
        "official_ref": ("2021/7", "llm"),
        "title": ("Kurul kararı", "llm"),
    }
    assert suggestions["doc_date"].evidence == {"page": 1, "quote": "15 Mart 2021"}


def test_an_invented_quote_drops_the_field() -> None:
    detector = FakeDetector(
        {
            "official_ref": {"value": "2099/1", "quote": "2099/1 sayılı karar"},
            "title": {"value": "Uydurma", "quote": "Metinde olmayan başlık"},
            "issuer": {"value": "Yargıtay", "quote": ""},
        }
    )
    suggestions, _ = run(detector)
    assert suggestions == {}


def test_a_date_that_its_quote_does_not_show_is_dropped() -> None:
    detector = FakeDetector(
        {
            "doc_date": {"value": "2021-03-16", "quote": "15 Mart 2021"},
        }
    )
    assert run(detector)[0] == {}
    bad = FakeDetector({"doc_date": {"value": "2021-13-45", "quote": "15 Mart 2021"}})
    assert run(bad)[0] == {}


def test_a_ref_that_is_not_in_its_quote_is_dropped() -> None:
    detector = FakeDetector({"official_ref": {"value": "2021/9", "quote": "2021/7 sayılı kararı"}})
    assert run(detector)[0] == {}


def test_a_doc_type_without_a_quote_is_kept_but_marked_without_evidence() -> None:
    detector = FakeDetector({"doc_type": {"value": "kitap"}})
    suggestions, _ = run(detector)
    assert (suggestions["doc_type"].value, suggestions["doc_type"].source) == ("kitap", "llm")
    assert suggestions["doc_type"].evidence is None
    invented = FakeDetector({"doc_type": {"value": "kitap", "quote": "metinde yok"}})
    assert run(invented)[0]["doc_type"].evidence is None


def test_a_doc_type_outside_the_enum_is_dropped() -> None:
    assert run(FakeDetector({"doc_type": {"value": "sozlesme"}}))[0] == {}


def test_malformed_answers_are_ignored() -> None:
    answer = {
        "doc_type": "kanun",
        "title": {"value": 5},
        "doc_date": None,
        "issuer": {"value": "x" * 400},
    }
    assert run(FakeDetector(answer))[0] == {}


def test_a_failing_model_leaves_a_warning_and_the_rule_suggestions() -> None:
    detector = FakeDetector(error="HTTP 429")
    result = classify(YONETMELIK, "pdf", "y.pdf", detector)
    assert result.warnings == ["detector_failed"]
    assert result.suggestions["doc_type"].value == "yonetmelik"
    assert "doc_date" not in result.suggestions


def test_the_model_does_not_overwrite_what_the_rules_found() -> None:
    detector = FakeDetector(
        {"doc_type": {"value": "kanun"}, "doc_date": {"value": "2020-01-01", "quote": "2020"}}
    )
    result = classify(YONETMELIK, "pdf", "y.pdf", detector)
    assert result.suggestions["doc_type"].source == "rule"
    assert detector.requests[0].fields == ("doc_date", "official_ref", "issuer")


def test_nothing_is_asked_without_a_detector_or_without_text() -> None:
    assert classify(UNCLEAR, "pdf", "belge.pdf").suggestions == {}
    detector = FakeDetector()
    assert classify("", "pdf", "scan.pdf", detector).suggestions == {}
    assert detector.requests == []


def test_the_excerpt_is_two_pages_or_six_thousand_characters() -> None:
    pages = ["a" * 100, "b" * 100, "c" * 100]
    assert excerpt("\f".join(pages)) == "a" * 100 + "\f" + "b" * 100
    assert excerpt("x" * 20000) == "x" * MAX_CHARS
    assert len(excerpt(("y" * 5000 + "\f") * 3)) <= MAX_CHARS


def test_the_answer_schema_lists_only_the_wanted_fields() -> None:
    schema = answer_schema(("doc_type", "title"))
    assert set(schema["properties"]) == {"doc_type", "title"}
    assert schema["properties"]["doc_type"]["properties"]["value"]["enum"] == list(DOC_TYPES)


# --- similarity -------------------------------------------------------------------------------

SENTENCES = " ".join(
    f"madde {n} gereğince işçi {n} numaralı işyerinde çalışmaya devam eder" for n in range(60)
)


def test_the_same_text_laid_out_differently_is_similar_and_another_text_is_not() -> None:
    a = shingles(SENTENCES)
    b = shingles("ÖZETİ: başka bir özet\n" + SENTENCES.replace(" gereğince ", "\ngereğince\n"))
    other = shingles(
        " ".join(f"tamamen farklı bir metin {n} sigorta primi borcu {n}" for n in range(60))
    )
    assert containment(a, b) > 0.9
    assert containment(a, other) < 0.1


def test_an_excerpt_is_contained_in_the_whole_and_a_short_text_is_never_similar() -> None:
    whole = shingles(SENTENCES)
    assert containment(shingles(SENTENCES[: len(SENTENCES) // 2]), whole) == 1.0
    assert containment(shingles("kısa metin"), whole) == 0.0
