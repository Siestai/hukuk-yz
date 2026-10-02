from dataclasses import replace
from datetime import date

from fakes import Reply, Site, make_adapter, make_key

from hukuk_verify import Outcome, verify
from hukuk_verify.adapters import UyapEmsalAdapter

HOME = Reply.fixture("emsal_home.html")
KEY = make_key(
    court="bam",
    court_level="bam_bim",
    chamber="9. HD",
    bam_region="Gaziantep",
    esas_no="2022/1258",
    karar_no="2022/1822",
    decision_date=date(2022, 12, 29),
)


def site(*search: Reply) -> Site:
    return Site(
        {
            "/": HOME,
            "/aramadetaylist": list(search),
            "/getDokuman": Reply(200, '{"data": "<html>FIXTURE TEXT</html>"}'),
        }
    )


async def test_found_is_filtered_by_the_full_chamber_name() -> None:
    fake = site(Reply.fixture("emsal_found.json"))
    result = await make_adapter(UyapEmsalAdapter, fake).lookup(KEY)
    body = fake.bodies("/aramadetaylist")[0]["data"]
    assert body["birimHukukMah"] == "Gaziantep Bölge Adliye Mahkemesi 9. Hukuk Dairesi"
    assert (body["esasYil"], body["esasIlkSiraNo"], body["kararSonSiraNo"]) == (
        "2022",
        "1258",
        "1822",
    )
    [row] = result.rows
    assert row.ref == "853364500"
    assert row.chamber == "Gaziantep Bölge Adliye Mahkemesi 9. Hukuk Dairesi"
    assert row.decision_date == date(2022, 12, 29)


async def test_istanbul_with_or_without_the_dot_finds_the_option() -> None:
    fake = site(Reply.fixture("emsal_found.json"))
    adapter = make_adapter(UyapEmsalAdapter, fake)
    await adapter.lookup(make_key(court="bam", chamber="1. HD", bam_region="İstanbul"))
    await adapter.lookup(make_key(court="bam", chamber="18. HD", bam_region="Istanbul"))
    sent = [b["data"]["birimHukukMah"] for b in fake.bodies("/aramadetaylist")]
    assert sent == [
        "Istanbul Bölge Adliye Mahkemesi 1. Hukuk Dairesi",
        "İstanbul Bölge Adliye Mahkemesi 18. Hukuk Dairesi",
    ]


async def test_a_chamber_missing_from_the_list_is_searched_without_a_filter() -> None:
    fake = site(Reply.fixture("emsal_found.json"))
    unlisted = make_key(court="bam", chamber="61. HD", bam_region="İstanbul")
    await make_adapter(UyapEmsalAdapter, fake).lookup(unlisted)
    assert "birimHukukMah" not in fake.bodies("/aramadetaylist")[0]["data"]
    assert len(fake.bodies("/aramadetaylist")) == 1  # no second, unfiltered search


async def test_found_verifies_as_uyap() -> None:
    result = await verify(
        make_adapter(UyapEmsalAdapter, site(Reply.fixture("emsal_found.json"))), KEY
    )
    assert result.outcome is Outcome.verified_uyap
    assert result.official_url == "https://emsal.uyap.gov.tr/getDokuman?id=853364500"


async def test_not_found_is_not_in_source() -> None:
    result = await verify(
        make_adapter(UyapEmsalAdapter, site(Reply.fixture("emsal_empty.json"))), KEY
    )
    assert result.outcome is Outcome.not_in_source


async def test_the_same_ek_in_another_region_is_a_mismatch() -> None:
    other = replace(KEY, bam_region="Ankara")
    fake = site(Reply.fixture("emsal_found.json"))
    result = await verify(make_adapter(UyapEmsalAdapter, fake), other)
    assert result.outcome is Outcome.mismatch
    assert result.matched["bam_region"] == "mismatch"
