import itertools

import pytest

from hukuk_ingest.clean import clean_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a-\nb-\nc", "abc"),
        ("kıdem-\ntazminatı", "kıdemtazminatı"),
        ("Kıdem-\ntazminatı", "Kıdemtazminatı"),
        ("kıdem-\nvergi", "kıdemvergi"),  # "ve" prefix is not the conjunction
        ("x-\nve-\nc", "xvec"),
        ("kıdem-\nve ihbar", "kıdem-\nve ihbar"),
        ("kıdem-\nveya ihbar", "kıdem-\nveya ihbar"),
        ("kıdem-\nTazminatı", "kıdem-\nTazminatı"),
        ("4857 s.-\nkanun", "4857 s.-\nkanun"),
        ("İşK-\n18", "İşK-\n18"),
        ("- liste\n- öğe", "- liste\n- öğe"),
    ],
)
def test_clean_text_line_end_hyphen(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_clean_text_normalises_newlines_hyphens_and_bullets() -> None:
    raw = "kıdem-\r\ntazminatı ⚫ bir­lik\r\n• İşK-\n18\r\n"
    assert clean_text(raw) == "kıdemtazminatı • birlik\n• İşK-\n18\n"


def test_clean_text_removes_invisible_characters_and_unifies_spaces() -> None:
    assert clean_text("a​b﻿c⁠d") == "abcd"
    assert clean_text("a b c d") == "a b c d"


def test_clean_text_unifies_only_listed_bullets() -> None:
    assert clean_text("⚫ ▪ •") == "• • •"
    assert clean_text("● ◦ ■ □") == "● ◦ ■ □"


def test_clean_text_composes_to_nfc(turkish_sentence: str) -> None:
    decomposed = "İşçi ğ " + turkish_sentence
    assert clean_text(decomposed).startswith("İşçi ğ ")


def test_clean_text_is_idempotent_on_generated_inputs() -> None:
    alphabet = ["a", "ve", "-", "\n", " ", "İ", "​", "­", "\r\n", "•", "⚫", "7"]
    for n in range(1, 5):
        for combo in itertools.product(alphabet, repeat=n):
            raw = "".join(combo)
            once = clean_text(raw)
            assert clean_text(once) == once, repr(raw)
