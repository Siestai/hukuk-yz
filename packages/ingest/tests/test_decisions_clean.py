from hukuk_ingest.decisions.clean import clean_journal


def test_page_header_and_page_number_are_stripped_and_kept_as_provenance() -> None:
    text = (
        "Yargıtay Kararları – Çalışma ve Toplum, 2024/1\n7\nBirinci sayfa metni\n"
        "\fYargıtay Kararları – Çalışma ve Toplum, 2024/1\n8\nİkinci sayfa metni"
    )
    j = clean_journal(text)
    assert (
        j.text == "Birinci sayfa metni\n\nİkinci sayfa metni"
    )  # the page break stays a line break
    assert (j.journal_year, j.journal_no, j.journal_page) == (2024, 1, 7)


def test_header_whose_dash_part_wraps_to_the_next_line() -> None:
    j = clean_journal("Yargıtay Kararları \n– Çalışma ve Toplum, 2024/3\n12\nMetin")
    assert j.text == "Metin"
    assert (j.journal_year, j.journal_no, j.journal_page) == (2024, 3, 12)


def test_plain_header_without_year_leaves_year_empty() -> None:
    j = clean_journal("Yargıtay Kararları\n160\nİlgili Kanun/md:\n")
    assert j.text == "İlgili Kanun/md:\n"
    assert (j.journal_year, j.journal_no, j.journal_page) == (None, None, 160)


def test_header_words_inside_the_text_are_not_removed() -> None:
    body = "Metin\nYargıtay Kararları\n12\nDevam"
    assert clean_journal(body).text == body


def test_foreign_section_titles_are_canonical() -> None:
    assert clean_journal("AlmanFederalMahkemeKararları\n1\nx").header_title == (
        "Alman Federal Mahkeme Kararları"
    )
    assert clean_journal("Alman Federal Mahkeme Kararı \n209\nx").header_title == (
        "Alman Federal Mahkeme Kararları"
    )
    assert clean_journal("Avrupa İnsan Hakları Mahkemesi\n1\nx").header_title == (
        "Avrupa İnsan Hakları Mahkemesi"
    )


def test_private_use_bullets_and_spaces_become_plain() -> None:
    assert clean_journal(" ANAHTAR\n İKİNCİ").text == "• ANAHTAR \n• İKİNCİ"


def test_noncharacter_inside_a_word_is_dropped() -> None:
    assert clean_journal("ÜZERİN￾DEN").text == "ÜZERİNDEN"


def test_ocr_capital_i_circumflex_is_fixed_only_between_capitals() -> None:
    assert clean_journal("TÎS ve ÜÎ tarihi").text == "TİS ve ÜÎ tarihi"


def test_lone_lowercase_word_line_is_joined_to_the_previous_line() -> None:
    text = "Hükmün infazı sırasında yapılan işlemlerin hukuka uygun\nbile\n- etkinliğin olduğu"
    assert clean_journal(text).text == (
        "Hükmün infazı sırasında yapılan işlemlerin hukuka uygun bile\n- etkinliğin olduğu"
    )


def test_short_or_sentence_final_lines_are_not_joined() -> None:
    text = "Kısa satır\nbile\n- devam"
    assert clean_journal(text).text == text
    ended = "Bu cümle uzun bir cümledir ve nokta ile biter.\nbile\n- devam"
    assert clean_journal(ended).text == ended


def test_glued_words_are_left_as_they_are() -> None:
    assert clean_journal("uygulanmayadevamedileceği").text == "uygulanmayadevamedileceği"


def test_esign_banner_and_trailing_page_number_are_removed() -> None:
    text = "Bu belge 5070 sayılı Yasa hükümlerine göre elektronik olarak imzalanmıştır.\nMetin\n698"
    assert clean_journal(text).text == "Metin"


def test_journal_footer_line_is_removed_but_an_inline_citation_is_not() -> None:
    text = (
        "ilk satır\n105\nÇalışma ve Toplum, 2007/3\ndevam\nbkz. Çalışma ve Toplum, 2018/3, s.1497\n"
    )
    assert clean_journal(text).text == "ilk satır\ndevam\nbkz. Çalışma ve Toplum, 2018/3, s.1497\n"


def test_wrapped_labels_are_rejoined() -> None:
    text = "Esas \nNo.\nKara\nr No.\nTari\nhi:\n2009/1"
    assert clean_journal(text).text == "Esas No.\nKarar No.\nTarihi:\n2009/1"


def test_cleaning_is_idempotent() -> None:
    once = clean_journal("Yargıtay Kararları – Çalışma ve Toplum, 2024/1\n7\n AB\nTÎS\n")
    assert clean_journal(once.text).text == once.text
