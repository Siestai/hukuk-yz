from datetime import date

import pytest

from hukuk_ingest.statutes.annotations import parse_annotations


def _one(text: str) -> tuple[str, str, date, str, str]:
    notes, unparsed = parse_annotations(text)
    assert not unparsed
    assert len(notes) == 1
    n = notes[0]
    return n.kind, n.scope, n.date, n.law, n.law_article


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "(Değişik birinci fıkra: 12/10/2017-7036/11 md.) Metin",
            ("degisik", "birinci fıkra", date(2017, 10, 12), "7036", "11"),
        ),
        (
            "(Ek cümle: 10/9/2014-6552/2 md.) Yer altı işlerinde",
            ("ek", "cümle", date(2014, 9, 10), "6552", "2"),
        ),
        (
            "(Değişik yedinci fıkra: 11/10/2011-KHK-665/28 md.)",
            ("degisik", "yedinci fıkra", date(2011, 10, 11), "KHK-665", "28"),
        ),
        ("(Mülga: 20/6/2012-6331/37 md.)", ("mulga", "", date(2012, 6, 20), "6331", "37")),
        ("(Ek:5/12/2019-7194/48 md.)", ("ek", "", date(2019, 12, 5), "7194", "48")),
        ("(Ek: 10/9/2014-6552/ 49 md.)", ("ek", "", date(2014, 9, 10), "6552", "49")),
        ("(Değişik: 23/1/2008 – 5728/500 md.)", ("degisik", "", date(2008, 1, 23), "5728", "500")),
        ("(Ek: 2/1/2017-KHK681/80 md.)", ("ek", "", date(2017, 1, 2), "KHK-681", "80")),
        (
            "(Mülga ikinci fıkra: 2/7/2018-KHK/700/145 md.)",
            ("mulga", "ikinci fıkra", date(2018, 7, 2), "KHK-700", "145"),
        ),
        (
            "(Yeniden düzenleme:11/11/2020-7256/32 md.)",
            ("degisik", "düzenleme", date(2020, 11, 11), "7256", "32"),
        ),
        (
            "(Başlığı ile Birlikte Değişik:20/7/2025-7555/23 md.)",
            ("degisik", "başlık", date(2025, 7, 20), "7555", "23"),
        ),
        (
            "(İptal dördüncü fıkra: Anayasa Mahkemesinin 19/10/2005 tarihli ve E.:2003/66, "
            "K.:2005/72 sayılı Kararı ile.)",
            ("iptal", "dördüncü fıkra", date(2005, 10, 19), "AYM", ""),
        ),
    ],
)
def test_single_note_forms(text: str, expected: tuple[str, str, date, str, str]) -> None:
    assert _one(text) == expected


def test_two_items_in_one_parenthesis() -> None:
    text = "(Ek fıkra: 23/7/2010-6009/48 md.; Mülga dördüncü fıkra: 20/6/2012-6331/37 md.) İşveren"
    notes, unparsed = parse_annotations(text)
    assert not unparsed
    assert [(n.kind, n.scope, n.law) for n in notes] == [
        ("ek", "fıkra", "6009"),
        ("mulga", "dördüncü fıkra", "6331"),
    ]
    assert notes[0].raw == notes[1].raw


def test_comma_between_items_and_court_decision_item() -> None:
    notes, unparsed = parse_annotations(
        "(Ek cümle: 13/2/2011-6111/37 md., Değişik üçüncü cümle: 23/2/2017-6824/14 md.)"
    )
    assert not unparsed and [n.law for n in notes] == ["6111", "6824"]
    notes, unparsed = parse_annotations(
        "(Ek cümle: 17/4/2008-5754/66 md.; İptal cümle: Anayasa Mahkemesi’nin 25/12/2014 "
        "tarihli ve E.: 2014/74, K.: 2014/201 sayılı Kararı ile.)"
    )
    assert not unparsed and [(n.kind, n.law) for n in notes] == [("ek", "5754"), ("iptal", "AYM")]


def test_confirmation_notes_are_their_own_kind() -> None:
    notes, _ = parse_annotations(
        "(Ek fıkra: 2/1/2017-KHK-681/74 md.; Aynen kabul: 1/2/2018-7073/73 md.)"
    )
    assert [n.kind for n in notes] == ["ek", "kabul"]
    notes, _ = parse_annotations("(Değiştirilerek kabul: 1/2/2018-7073/73 md.)")
    assert (notes[0].kind, notes[0].scope) == ("degisik", "değiştirilerek kabul")


def test_wrapped_note_and_offset() -> None:
    notes, _ = parse_annotations("(Değişik birinci fıkra:\n 12/10/2017-7036/11 md.) Metin")
    assert len(notes) == 1 and notes[0].offset == 0


def test_unparseable_note_stays_raw() -> None:
    text = "(Ek: 32/13/2017-7036/11 md.) ve (Değişik: tarihsiz) ve (Değişik: 1/1/2010-5000/1 md.)"
    notes, unparsed = parse_annotations(text)
    assert [n.law for n in notes] == ["5000"]
    assert unparsed == ["(Ek: 32/13/2017-7036/11 md.)", "(Değişik: tarihsiz)"]


def test_body_parentheses_are_not_notes() -> None:
    notes, unparsed = parse_annotations(
        "İşveren (ek 5 inci madde) ve (a) bendi ile (Ek) bölüm; 4857/18 md. dışında"
    )
    assert notes == [] and unparsed == []


def test_note_that_starts_unknown_but_looks_like_one_is_reported() -> None:
    _, unparsed = parse_annotations("(Birleştirilmiş: 1/1/2010-5000/1 md.)")
    assert unparsed == ["(Birleştirilmiş: 1/1/2010-5000/1 md.)"]
