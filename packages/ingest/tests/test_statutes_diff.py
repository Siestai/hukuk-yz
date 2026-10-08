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


def test_diff_snapshots_classifies_each_article() -> None:
    old = _snap(
        **{"1": "Aynı metin.", "2": "Eski metin burada duruyor ve değişecek.", "3": "Kalkar."}
    )
    new = _snap(**{"1": "Aynı  metin.", "2": "Yeni ve farklı bir metin yazıldı.", "4": "Eklenir."})
    kinds = {d.article_no: d.kind for d in diff_snapshots(old, new)}
    assert kinds == {"1": UNCHANGED, "2": CHANGED, "4": ADDED, "3": REMOVED}
