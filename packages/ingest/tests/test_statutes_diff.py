import pytest

from hukuk_ingest.statutes.diff import (
    ADDED,
    CHANGED,
    REMOVED,
    UNCHANGED,
    compare,
    diff_snapshots,
    normalize,
    skeleton,
)
from hukuk_ingest.statutes.split import Article, Snapshot


def _snap(**articles: str) -> Snapshot:
    arts = [Article(no, i, "", text) for i, (no, text) in enumerate(articles.items(), 1)]
    return Snapshot("9001", "", None, None, None, arts)


def test_normalize_ignores_layout_quotes_and_markers() -> None:
    a = "İşçi “kıdem”\ntazminatı alır.(1)\nİkinci   fıkra.12"
    b = 'İşçi "kıdem" tazminatı  alır. İkinci fıkra.'
    assert normalize(a, frozenset({1, 12})) == normalize(b)
    assert normalize("iş- veren") == normalize("iş-veren")
    assert normalize("(Ek:5/12/2019-7194/48 md.)") == normalize("(Ek: 5/12/2019 - 7194/48 md.)")


def test_normalize_keeps_paragraph_numbers_and_statute_numbers() -> None:
    assert normalize("(1) Bu madde 4857/18 md. ile 15 gün") == "(1) Bu madde 4857/18 md. ile 15 gün"


def test_skeleton_folds_case_diacritics_and_punctuation() -> None:
    assert skeleton("Malûl, İŞÇİ.") == skeleton("malul isci")


@pytest.mark.parametrize(
    ("old", "new", "kind", "warnings"),
    [
        ("Bu bir madde.", "Bu  bir\nmadde.(1)", UNCHANGED, []),
        (
            "(3) 5 inci maddenin (4) numaralı",
            "(3) 5 inci maddenin (5) numaralı",
            CHANGED,
            ["uncertain_diff"],
        ),
        (
            "işçi (1) numaralı bent uyarınca",
            "işçi (2) numaralı bent uyarınca",
            CHANGED,
            ["uncertain_diff"],
        ),
        ("madde5 uyarınca", "madde6 uyarınca", CHANGED, ["uncertain_diff"]),
        ("Malûl sayılır, işçi.", "Malul sayılır işçi.", UNCHANGED, ["uncertain_diff"]),
        ("Süre altı iş günüdür.", "Süre otuz iş günüdür.", CHANGED, ["uncertain_diff"]),
        (
            "Süre altı iş günüdür ve işçiye bildirilir.",
            "Süre otuz iş günüdür ve işverene yazılı olarak ayrıca bildirilir.",
            CHANGED,
            [],
        ),
        ("9000 gün", "7200 gün", CHANGED, ["uncertain_diff"]),
    ],
)
def test_compare(old: str, new: str, kind: str, warnings: list[str]) -> None:
    assert compare(old, new, frozenset({1}), frozenset({1})) == (kind, warnings)


def test_compare_strips_only_known_footnote_markers() -> None:
    old, new = "işçi alır.(2) Süre kesilmesi47 durur.", "işçi alır. Süre kesilmesi durur."
    assert compare(old, new, frozenset({2, 47}), frozenset()) == (UNCHANGED, [])
    # a number the splitter did not take for a footnote is text
    assert compare(old, new, frozenset(), frozenset())[0] == CHANGED
    assert compare("işçi (1) bent", "işçi (2) bent", frozenset({1}), frozenset())[0] == CHANGED


@pytest.mark.parametrize(
    ("old", "new", "old_markers", "new_markers"),
    [
        # a marker on a line of its own, or in another place of the line, is still a marker
        ("Süre dolar,\n(1)\n8) Ek süre.", "Süre dolar, (1)\n8) Ek süre.", {1}, {1}),
        ("Süre dolar. 8 e) Ek süre.", "Süre dolar. e) Ek süre.", {8}, set()),
        # footnotes the older snapshot did not read: its markers follow the other snapshot's
        ("Süre dolar. (2)(3) Ek süre.", "Süre dolar. Ek süre.", set(), {2, 3}),
        # a `(n)` closing a line after punctuation is a marker whatever its number
        ("Süre dolar. (2)\nEk süre.", "Süre dolar.\nEk süre.", set(), set()),
    ],
)
def test_compare_reads_marker_layouts_as_unchanged(
    old: str, new: str, old_markers: set[int], new_markers: set[int]
) -> None:
    kind, _ = compare(old, new, frozenset(old_markers), frozenset(new_markers))
    assert kind == UNCHANGED


def test_compare_ignores_the_space_after_a_percent_sign() -> None:
    assert compare("Faiz % 70'i ödenir.", "Faiz %70'i ödenir.") == (UNCHANGED, [])


def test_compare_keeps_paragraph_numbers_and_unknown_numbers_as_text() -> None:
    # a paragraph number opens its line; a number no snapshot knows as a footnote is text
    assert compare("Süre dolar.\n(2) Ek süre.", "Süre dolar.\n(3) Ek süre.")[0] == CHANGED
    assert (
        compare("Süre dolar. (2) Ek", "Süre dolar. Ek", frozenset(), frozenset({3}))[0] == CHANGED
    )
    assert compare("Süre 8 e) dolar.", "Süre e) dolar.", frozenset(), frozenset({3}))[0] == CHANGED


def test_diff_snapshots_classifies_each_article() -> None:
    old = _snap(
        **{"1": "Aynı metin.", "2": "Eski metin burada duruyor ve değişecek.", "3": "Kalkar."}
    )
    new = _snap(**{"1": "Aynı  metin.", "2": "Yeni ve farklı bir metin yazıldı.", "4": "Eklenir."})
    kinds = {d.article_no: d.kind for d in diff_snapshots(old, new)}
    assert kinds == {"1": UNCHANGED, "2": CHANGED, "4": ADDED, "3": REMOVED}


def test_compare_warns_when_an_unknown_line_end_number_is_dropped() -> None:
    # no snapshot knows 2 as a footnote: the text is equal only if it is dropped, so it is flagged
    assert compare("Süre dolar. (2)\nEk süre.", "Süre dolar.\nEk süre.") == (
        UNCHANGED,
        ["uncertain_diff"],
    )
    # a known number is dropped silently
    assert compare("Süre dolar. (2)\nEk süre.", "Süre dolar.\nEk süre.", frozenset({2})) == (
        UNCHANGED,
        [],
    )


def test_compare_keeps_different_unknown_line_end_numbers_as_a_change() -> None:
    kind, warnings = compare("Süre dolar. (2)\nEk süre.", "Süre dolar. (3)\nEk süre.")
    assert kind == CHANGED and warnings == ["uncertain_diff"]


def test_compare_borrowed_markers_keep_a_real_number_change() -> None:
    # 30 is in no snapshot's marker set, so removing it from the new text is a change
    kind, _ = compare("Süre 30 gün (2) olur.", "Süre gün olur.", frozenset(), frozenset({2}))
    assert kind == CHANGED


def test_compare_keeps_a_changed_percentage() -> None:
    assert compare("Faiz % 70'i ödenir.", "Faiz % 7'si ödenir.")[0] == CHANGED
    assert compare("Faiz % 70 ödenir.", "Faiz % 7 ödenir.")[0] == CHANGED
