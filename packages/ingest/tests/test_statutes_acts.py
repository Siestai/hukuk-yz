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
