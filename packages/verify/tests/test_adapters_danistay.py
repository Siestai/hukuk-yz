from dataclasses import replace
from datetime import date

from fakes import Reply, Site, make_adapter, make_key

from hukuk_verify import Outcome, verify
from hukuk_verify.adapters import DanistayAdapter

KEY = make_key(
    court="danistay",
    chamber="10. D",
    esas_no="2026/940",
    karar_no="2026/402",
    decision_date=date(2026, 2, 5),
)


def site(*search: Reply) -> Site:
    return Site(
        {
            "/": Reply(200, "<html></html>", "text/html"),
            "/aramadetaylist": list(search),
            "/getDokuman": Reply(200, '{"data": "<html>FIXTURE TEXT</html>"}'),
        }
    )


async def test_found_reads_the_chamber_from_daire_kurul() -> None:
    fake = site(Reply.fixture("danistay_found.json"))
    result = await make_adapter(DanistayAdapter, fake).lookup(KEY)
    body = fake.bodies("/aramadetaylist")[0]["data"]
    assert body["daire"] == "10. Daire"
    assert (body["esasYil"], body["esasIlkSiraNo"]) == ("2026", "940")
    [row] = result.rows
    assert (row.ref, row.chamber, row.decision_date) == (
        "1226554300",
        "10. Daire",
        date(2026, 2, 5),
    )


async def test_a_kurul_is_searched_without_a_chamber_filter() -> None:
    fake = site(Reply.fixture("danistay_found.json"))
    iddk = make_key(court="danistay", court_level="hgk_iddk", chamber="")
    await make_adapter(DanistayAdapter, fake).lookup(iddk)
    assert "daire" not in fake.bodies("/aramadetaylist")[0]["data"]


async def test_found_verifies_as_official() -> None:
    result = await verify(
        make_adapter(DanistayAdapter, site(Reply.fixture("danistay_found.json"))), KEY
    )
    assert result.outcome is Outcome.verified_official
    assert result.official_ref == "1226554300"


async def test_not_found_is_not_in_source() -> None:
    result = await verify(
        make_adapter(DanistayAdapter, site(Reply.fixture("danistay_empty.json"))), KEY
    )
    assert result.outcome is Outcome.not_in_source


async def test_another_chamber_is_a_mismatch() -> None:
    other = replace(KEY, chamber="3. D")
    fake = site(Reply.fixture("danistay_found.json"))
    result = await verify(make_adapter(DanistayAdapter, fake), other)
    assert result.outcome is Outcome.mismatch
