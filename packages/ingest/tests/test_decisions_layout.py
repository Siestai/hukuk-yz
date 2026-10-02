import pytest
from conftest import era1_text, era2_text, era3_text, era4_text, foreign_text

from hukuk_ingest.decisions.clean import clean_journal
from hukuk_ingest.decisions.layout import Layout, detect_layout


@pytest.mark.parametrize(
    ("text", "layout"),
    [
        (era1_text(), Layout.ERA1_SUMMARY_FIRST),
        (era2_text(), Layout.ERA2_CLASSIC),
        (era3_text(), Layout.ERA3_TWO_COLUMN),
        (era4_text(), Layout.ERA4_NEW_TEMPLATE),
        (foreign_text(), Layout.FOREIGN_ARTICLE),
        ("Başlıksız ve etiketsiz bir metin.\nİkinci satır.", Layout.UNKNOWN),
    ],
)
def test_layout_comes_from_markers_in_the_text(text: str, layout: Layout) -> None:
    assert detect_layout(clean_journal(text)) is layout


def test_era3_also_covers_the_individual_application_two_column_block() -> None:
    text = "T.C. ANAYASA\nMAHKEMESİ\nBaş. No.\nKarar Tarihi:\n2014/15627\n05.10.2017\n"
    assert detect_layout(clean_journal(text)) is Layout.ERA3_TWO_COLUMN


def test_summary_before_the_labels_is_era1_even_without_a_journal_header() -> None:
    text = "ÖZÜ: Özet.\nT.C.\nYARGITAY\n9. Hukuk Dairesi\nESAS NO: 2003/1\nKARAR NO: 2003/2\n"
    assert detect_layout(clean_journal(text)) is Layout.ERA1_SUMMARY_FIRST


def test_journal_header_alone_does_not_make_era4() -> None:
    # Issue 43 carries the "Çalışma ve Toplum, YYYY/N" header with the classic body.
    text = era2_text().replace(
        "Yargıtay Kararları\n117", "Yargıtay Kararları – Çalışma ve Toplum, 2014/4\n117"
    )
    assert detect_layout(clean_journal(text)) is Layout.ERA2_CLASSIC
