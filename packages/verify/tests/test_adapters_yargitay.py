import json
from datetime import date

from fakes import Reply, Site, make_adapter, make_key

from hukuk_verify import Outcome, verify
from hukuk_verify.adapters import YargitayAdapter

HOME = Reply(200, "<html></html>", "text/html")


def site(*search: Reply) -> Site:
    return Site(
        {
            "/": HOME,
            "/aramadetaylist": list(search),
            "/getDokuman": Reply.fixture("yargitay_document.json"),
        }
    )


async def test_found_follows_the_spike_contract() -> None:
    fake = site(Reply.fixture("yargitay_found.json"))
    result = await make_adapter(YargitayAdapter, fake).lookup(make_key())

    assert fake.paths() == ["GET /robots.txt", "GET /", "POST /aramadetaylist"]
    search = fake.requests[2]
    assert search.headers["content-type"] == "application/json; charset=utf-8"
    assert search.headers["x-requested-with"] == "XMLHttpRequest"
    assert search.headers["referer"] == "https://karararama.yargitay.gov.tr/"
    assert fake.bodies("/aramadetaylist")[0] == {
        "data": {
            "arananKelime": "",
            "birimYrgHukukDaire": "9. Hukuk Dairesi",
            "esasYil": "2017",
            "esasIlkSiraNo": "17327",
            "esasSonSiraNo": "17327",
            "kararYil": "2020",
            "kararIlkSiraNo": "14291",
            "kararSonSiraNo": "14291",
            "siralama": "1",
            "siralamaDirection": "desc",
            "pageSize": 10,
            "pageNumber": 1,
        }
    }
    [row] = result.rows
    assert (row.ref, row.chamber, row.esas_no, row.karar_no) == (
        "100000001",
        "9. Hukuk Dairesi",
        "2017/17327",
        "2020/14291",
    )
    assert row.decision_date == date(2020, 12, 9)
    assert row.url == "https://karararama.yargitay.gov.tr/getDokuman?id=100000001"


async def test_an_empty_filtered_search_is_repeated_without_the_chamber() -> None:
    fake = site(Reply.fixture("yargitay_empty.json"), Reply.fixture("yargitay_found.json"))
    result = await make_adapter(YargitayAdapter, fake).lookup(make_key())
    first, second = fake.bodies("/aramadetaylist")
    assert "birimYrgHukukDaire" in first["data"]
    assert "birimYrgHukukDaire" not in second["data"]
    assert len(result.rows) == 1


async def test_hgk_is_searched_by_the_genel_kurul_name() -> None:
    fake = site(Reply.fixture("yargitay_found.json"))
    hgk = make_key(court_level="hgk_iddk", chamber="", source_chamber="10", esas_no="2024/389")
    await make_adapter(YargitayAdapter, fake).lookup(hgk)
    body = fake.bodies("/aramadetaylist")[0]["data"]
    assert body["birimYrgKurulDaire"] == "Hukuk Genel Kurulu"
    assert (body["esasYil"], body["esasIlkSiraNo"]) == ("2024", "389")


async def test_a_ceza_dairesi_is_searched_by_its_full_name() -> None:
    fake = site(Reply.fixture("yargitay_found.json"))
    await make_adapter(YargitayAdapter, fake).lookup(make_key(chamber="9. CD"))
    body = fake.bodies("/aramadetaylist")[0]["data"]
    assert body["birimYrgCezaDaire"] == "9. Ceza Dairesi"
    assert "birimYrgHukukDaire" not in body


async def test_a_chamber_without_a_known_filter_is_searched_by_ek_alone() -> None:
    fake = site(Reply.fixture("yargitay_found.json"))
    ibk = make_key(chamber="İçtihadı Birleştirme Büyük Genel Kurulu")
    await make_adapter(YargitayAdapter, fake).lookup(ibk)
    body = fake.bodies("/aramadetaylist")[0]["data"]
    assert not {"birimYrgHukukDaire", "birimYrgCezaDaire", "birimYrgKurulDaire"} & body.keys()


async def test_found_verifies() -> None:
    result = await verify(
        make_adapter(YargitayAdapter, site(Reply.fixture("yargitay_found.json"))), make_key()
    )
    assert result.outcome is Outcome.verified_official
    assert result.official_ref == "100000001"
    assert result.official_text is not None


async def test_not_found_is_not_in_source() -> None:
    fake = site(Reply.fixture("yargitay_empty.json"))
    result = await verify(make_adapter(YargitayAdapter, fake), make_key())
    assert result.outcome is Outcome.not_in_source
    assert len(fake.bodies("/aramadetaylist")) == 2  # filtered, then unfiltered


async def test_a_different_date_is_a_mismatch() -> None:
    fake = site(Reply.fixture("yargitay_found.json"))
    result = await verify(
        make_adapter(YargitayAdapter, fake), make_key(decision_date=date(2020, 11, 1))
    )
    assert result.outcome is Outcome.mismatch
    assert result.matched["decision_date"] == "mismatch"
    assert json.dumps(result.matched)  # plain data
    assert "/getDokuman" not in [r.url.path for r in fake.requests]
