"""Chunking of decisions and statute articles for the search index (task 14); no database."""

import pytest

from hukuk_ingest.index.chunking import (
    BODY,
    EDITORIAL_SUMMARY,
    OVERLAP_WORDS,
    WINDOW_WORDS,
    article_label,
    chunk_article,
    chunk_decision,
    content_hash,
    decision_header,
    embedding_input,
    statute_header,
    word_count,
)

HEADER = "Yargıtay 9. HD · E. 2017/1"


def paragraph(n: int, words: int = 60) -> str:
    return " ".join(f"p{n}w{i}." if i % 20 == 19 else f"p{n}w{i}" for i in range(words))


def test_a_short_decision_is_one_chunk_with_exact_offsets() -> None:
    text = "  Davacı kıdem tazminatı istemiştir.\n\nMahkeme kabul etmiştir.  "
    [chunk] = chunk_decision(text, "", HEADER)
    assert chunk.kind == BODY
    assert text[chunk.char_start : chunk.char_end] == chunk.text
    assert chunk.text == text.strip()
    assert chunk.header == HEADER


def test_the_one_chunk_limit_is_500_words() -> None:
    assert len(chunk_decision("kelime " * 500, "", HEADER)) == 1
    assert len(chunk_decision("kelime " * 501, "", HEADER)) > 1


def test_a_long_decision_is_windowed_on_paragraphs_with_a_light_overlap() -> None:
    text = "\n\n".join(paragraph(n, 20) for n in range(90))  # 1.800 words
    chunks = chunk_decision(text, "", HEADER)
    assert len(chunks) > 5
    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text
        assert word_count(chunk.text) <= WINDOW_WORDS + OVERLAP_WORDS
        assert chunk.text.startswith("p")  # whole paragraphs only
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    # the windows overlap: a paragraph that ends one window opens the next
    assert any(a.char_end > b.char_start for a, b in zip(chunks, chunks[1:], strict=False))
    # and nothing is lost between them
    assert all(a.char_end >= b.char_start - 2 for a, b in zip(chunks, chunks[1:], strict=False))
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)


def test_a_paragraph_without_breaks_falls_back_to_sentences_then_words() -> None:
    sentences = " ".join(paragraph(n, 40) for n in range(40))  # one paragraph, sentences
    chunks = chunk_decision(sentences, "", HEADER)
    assert len(chunks) > 3
    assert all(sentences[c.char_start : c.char_end] == c.text for c in chunks)
    unbroken = " ".join(f"w{i}" for i in range(1_000))  # no sentence end at all
    chunks = chunk_decision(unbroken, "", HEADER)
    assert len(chunks) >= 5
    assert all(word_count(c.text) <= WINDOW_WORDS + OVERLAP_WORDS for c in chunks)
    assert all(unbroken[c.char_start : c.char_end] == c.text for c in chunks)


def test_a_decision_in_the_new_template_is_split_by_section() -> None:
    sections = {
        "I. DAVA": paragraph(1, 80),
        "II. CEVAP": paragraph(2, 90),
        "V. GEREKÇE": "\n\n".join(paragraph(n, 100) for n in range(8)),  # long: windowed
        "VI. KARAR": paragraph(9, 70),
    }
    text = "\n\n".join(f"{name}\n{body}" for name, body in sections.items())
    chunks = chunk_decision(text, "", HEADER)
    by_section = {name: [c for c in chunks if c.section == name] for name in sections}
    assert len(by_section["I. DAVA"]) == 1
    assert len(by_section["V. GEREKÇE"]) > 1
    assert by_section["I. DAVA"][0].text.startswith("I. DAVA")
    assert by_section["VI. KARAR"][0].header == f"{HEADER} · VI. KARAR"
    assert all(text[c.char_start : c.char_end] == c.text for c in chunks)


def test_short_sections_join_the_next_one_and_a_lone_heading_is_not_a_template() -> None:
    text = "I. DAVA\nKısa.\n\nII. CEVAP\n" + paragraph(2, 450) + "\n\nIII. KARAR\nBitti."
    chunks = chunk_decision(text, "", HEADER)
    assert chunks[0].text.startswith("I. DAVA")
    assert "II. CEVAP" in chunks[0].text
    assert chunks[-1].text.endswith("Bitti.")
    one_heading = "I. DAVA\n" + "\n\n".join(paragraph(n) for n in range(12))
    assert all(c.section is None for c in chunk_decision(one_heading, "", HEADER))
    lowercase = "I. Dava\n" + paragraph(1, 300) + "\n\nII. Karar\n" + paragraph(2, 300)
    assert all(c.section is None for c in chunk_decision(lowercase, "", HEADER))


def test_the_editorial_summary_is_a_chunk_of_its_own() -> None:
    chunks = chunk_decision("Gövde metni.", "  Kıdem tazminatı özeti.  ", HEADER)
    assert [c.kind for c in chunks] == [BODY, EDITORIAL_SUMMARY]
    assert chunks[1].text == "Kıdem tazminatı özeti."
    assert chunks[1].ordinal == 0
    only_summary = chunk_decision("Gövde metni.", "Özet.", HEADER, body=False)
    assert [c.kind for c in only_summary] == [EDITORIAL_SUMMARY]
    assert chunk_decision("", "", HEADER) == []


def test_a_short_article_is_one_chunk_and_a_long_one_splits_by_paragraph() -> None:
    [chunk] = chunk_article("(1) Birinci fıkra.\n(2) İkinci fıkra.", "h")
    assert chunk.text == "(1) Birinci fıkra.\n(2) İkinci fıkra."
    long_article = "\n".join(f"({n}) {paragraph(n, 90)}" for n in range(1, 9))
    chunks = chunk_article(long_article, "h")
    assert len(chunks) > 1
    assert all(long_article[c.char_start : c.char_end] == c.text for c in chunks)
    assert all(c.text.startswith("(") for c in chunks)
    assert chunk_article("  ", "h") == []


def test_headers_and_content_hash() -> None:
    assert (
        decision_header(
            "Yargıtay 9. HD, E. 1", [{"statute": 4857, "articles": ["17", "32"]}], ["kıdem"]
        )
        == "Yargıtay 9. HD, E. 1 · 4857/17,32 · kıdem"
    )
    assert decision_header(None, [{"statute": None, "articles": ["1"]}], []) == ""
    assert (
        statute_header("4857", "18", "Feshin geçerli sebebe dayandırılması", "2018-01-01")
        == "4857 sayılı Kanun · m.18 · Feshin geçerli sebebe dayandırılması · yürürlük 2018-01-01"
    )
    assert embedding_input("", "metin") == "metin"
    assert embedding_input("künye", "metin") == "künye\n\nmetin"
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("a2", "b")
    assert content_hash("a", "b") != content_hash("a", "b2")


@pytest.mark.parametrize("text", ["", "   \n\n  "])
def test_blank_text_gives_no_chunk(text: str) -> None:
    assert chunk_decision(text, text, HEADER) == []


def test_article_labels() -> None:
    assert article_label("18") == "m.18"
    assert article_label("Geçici 4") == "Geçici 4"
    assert article_label("Ek 2") == "Ek 2"
    assert statute_header("4857", "Ek 2", None, "2016-05-13") == (
        "4857 sayılı Kanun · Ek 2 · yürürlük 2016-05-13"
    )
