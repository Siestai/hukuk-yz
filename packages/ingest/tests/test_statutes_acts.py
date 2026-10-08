import tomllib
from datetime import date
from pathlib import Path

import pytest

from hukuk_ingest.statutes.acts import load_acts, parse_acts

FIXTURE = """
[[act]]
law = "6552"
kabul_tarihi = 2014-09-10
rg_tarihi = 2014-09-11
rg_sayisi = "29116"
yururluk = 2014-09-11
source_url = "https://example.test/6552"

[[act.exception]]
statute = "5510"
article = "Geçici 4"
scope = "birinci fıkra"
yururluk = 2015-04-01
source = "dipnot"

[[act]]
law = "6552"
kabul_tarihi = 2014-09-16
yururluk = 2014-09-17
source_url = "https://example.test/6552-b"

[[act]]
law = "KHK-665"
kabul_tarihi = 2011-10-11
"""


def test_registry_lookup_by_law_and_kabul_date(tmp_path: Path) -> None:
    path = tmp_path / "acts.toml"
    path.write_text(FIXTURE, encoding="utf-8")
    reg = load_acts(path)
    assert len(reg.acts) == 3  # one law with two kabul dates keeps both entries
    assert reg.get("6552", date(2014, 9, 10)).yururluk == date(2014, 9, 11)  # type: ignore[union-attr]
    assert reg.get("6552", date(2014, 9, 16)).yururluk == date(2014, 9, 17)  # type: ignore[union-attr]
    assert reg.get("6552", date(2000, 1, 1)) is None
    assert [a.law for a in reg.without_yururluk()] == ["KHK-665"]


def test_effective_dates_prefer_the_article_exception(tmp_path: Path) -> None:
    reg = parse_acts(tomllib.loads(FIXTURE))
    kabul = date(2014, 9, 10)
    assert reg.effective_dates("6552", kabul, "5510", "Geçici 4") == (
        {date(2015, 4, 1)},
        "exception",
    )
    assert reg.effective_dates("6552", kabul, "5510", "18") == ({date(2014, 9, 11)}, "act")
    assert reg.effective_dates("6552", kabul, "4857", "Geçici 4") == ({date(2014, 9, 11)}, "act")
    assert reg.effective_dates("KHK-665", date(2011, 10, 11), "4857", "1") is None
    assert reg.effective_dates("1111", kabul, "4857", "1") is None


@pytest.mark.parametrize(
    "toml",
    [
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-10\nyururluk = 2014-09-11\n',  # no source_url
        "[[act]]\nkabul_tarihi = 2014-09-10\n",  # no law
        '[[act]]\nlaw = "1"\nkabul_tarihi = "2014-09-10"\n',  # not a TOML date
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-10\n' * 2,
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-10\nsource_url = "x"\n'
        '[[act.exception]]\nstatute = "1"\narticle = "2"\nyururluk = 2015-01-01\n',  # no source
    ],
)
def test_invalid_registry_is_rejected(toml: str) -> None:
    with pytest.raises(ValueError):
        parse_acts(tomllib.loads(toml))


PARTIAL = """
[[act]]
law = "6552"
kabul_tarihi = 2014-09-10
rg_tarihi = 2014-09-11
yururluk = 2014-09-11
source_url = "https://example.test/6552"

[[act.exception]]
statute = "4857"
article = "41"
scope = "onuncu fıkra"
yururluk = 2015-01-01
partial = true
source = "tablo"

[[act.exception]]
statute = "5510"
article = "6"
scope = "ödeme dönemi başında"
source = "tablo"

[[act]]
law = "6552"
kabul_tarihi = 2014-09-16
alias_of = 2014-09-10
"""


def test_partial_exception_adds_its_date_to_the_acts() -> None:
    reg = parse_acts(tomllib.loads(PARTIAL))
    assert reg.effective_dates("6552", date(2014, 9, 10), "4857", "41") == (
        {date(2014, 9, 11), date(2015, 1, 1)},
        "partial",
    )


def test_exception_without_a_date_makes_the_article_unknown() -> None:
    reg = parse_acts(tomllib.loads(PARTIAL))
    assert reg.effective_dates("6552", date(2014, 9, 10), "5510", "6") is None
    assert reg.effective_dates("6552", date(2014, 9, 10), "5510", "7") == (
        {date(2014, 9, 11)},
        "act",
    )


def test_alias_takes_everything_from_its_target() -> None:
    reg = parse_acts(tomllib.loads(PARTIAL))
    alias = reg.get("6552", date(2014, 9, 16))
    assert alias is not None and alias.yururluk == date(2014, 9, 11)
    assert reg.effective_dates("6552", date(2014, 9, 16), "4857", "41") == reg.effective_dates(
        "6552", date(2014, 9, 10), "4857", "41"
    )


@pytest.mark.parametrize(
    "extra",
    [
        # kabul after the Resmî Gazete date and not an alias
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-16\nrg_tarihi = 2014-09-11\n',
        # alias of something that does not exist
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-16\nalias_of = 2014-09-10\n',
        # alias with data of its own
        '[[act]]\nlaw = "6552"\nkabul_tarihi = 2014-09-17\nalias_of = 2014-09-10\n'
        'yururluk = 2014-09-12\nsource_url = "u"\n',
        # partial without a scope
        '[[act]]\nlaw = "1"\nkabul_tarihi = 2014-09-01\nyururluk = 2014-09-02\n'
        'source_url = "u"\n[[act.exception]]\nstatute = "1"\narticle = "2"\n'
        'yururluk = 2015-01-01\npartial = true\nsource = "s"\n',
    ],
)
def test_registry_rejects_inconsistent_entries(extra: str) -> None:
    with pytest.raises(ValueError):
        parse_acts(tomllib.loads(PARTIAL + extra))
