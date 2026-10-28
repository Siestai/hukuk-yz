"""The shared scan for the "-iyor" forms."""

from hukuk_models.formal_turkish import progressive_forms


def test_the_iyor_forms_are_found_once_each_and_sorted() -> None:
    texts = ["Dava açılıyor ve işçi çalışıyor.", "Yine açılıyor.", "Biliyorum"]

    assert progressive_forms(texts) == ["Biliyorum", "açılıyor", "çalışıyor"]


def test_formal_turkish_passes() -> None:
    assert progressive_forms(["Dava açılamamaktadır.", "Hak doğmaktadır, tazminat ödenir."]) == []
