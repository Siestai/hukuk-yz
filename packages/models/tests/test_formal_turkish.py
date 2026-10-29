"""The shared scan for the "-iyor" forms."""

from hukuk_models.formal_turkish import progressive_forms


def test_the_iyor_forms_are_found_once_each_and_sorted() -> None:
    texts = ["Dava açılıyor ve işçi çalışıyor.", "Yine açılıyor.", "Biliyorum"]

    assert progressive_forms(texts) == ["Biliyorum", "açılıyor", "çalışıyor"]


def test_formal_turkish_passes() -> None:
    assert progressive_forms(["Dava açılamamaktadır.", "Hak doğmaktadır, tazminat ödenir."]) == []


def test_the_conditional_past_and_reported_forms_are_found() -> None:
    texts = ["İşçi çalışıyorsa", "İşveren ödüyordu", "Dava açılıyormuş"]

    assert progressive_forms(texts) == ["açılıyormuş", "çalışıyorsa", "ödüyordu"]


def test_compound_progressive_suffixes_are_not_missed() -> None:
    assert progressive_forms(["çalışıyordunuz", "bilmiyorsanız", "ödüyormuşsunuz"]) == [
        "bilmiyorsanız",
        "çalışıyordunuz",
        "ödüyormuşsunuz",
    ]
