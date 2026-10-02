"""What the three BİGM-app adapters (Yargıtay, Emsal, Danıştay) share: request shape, session,
`supports`, answer parsing and the official text."""

import json
from dataclasses import dataclass

import pytest
from fakes import Reply, Site, make_adapter, make_key

from hukuk_verify.adapters import DanistayAdapter, UyapEmsalAdapter, YargitayAdapter
from hukuk_verify.adapters.bigm import BigmAdapter, parse_site_date, split_number
from hukuk_verify.errors import UnexpectedResponse
from hukuk_verify.models import DecisionKey


@dataclass
class Case:
    adapter: type[BigmAdapter]
    key: DecisionKey
    found: str


CASES = {
    "yargitay": Case(YargitayAdapter, make_key(), "yargitay_found.json"),
    "emsal": Case(
        UyapEmsalAdapter,
        make_key(
            court="bam",
            court_level="bam_bim",
            bam_region="Gaziantep",
            esas_no="2022/1258",
            karar_no="2022/1822",
        ),
        "emsal_found.json",
    ),
    "danistay": Case(
        DanistayAdapter,
        make_key(court="danistay", chamber="10. D", esas_no="2026/940", karar_no="2026/402"),
        "danistay_found.json",
    ),
}
EVERY_BIGM = pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())


def site_for(*search: Reply) -> Site:
    return Site(
        {
            "/": Reply(200, "<html></html>", "text/html"),
            "/aramadetaylist": list(search),
            "/getDokuman": Reply(200, '{"data": "<html>FIXTURE TEXT</html>"}'),
        }
    )


def test_numbers_are_split_into_year_and_serial() -> None:
    assert split_number("2017/17327") == ("2017", "17327")
    assert split_number("2017/017327") == ("2017", "17327")
    assert split_number("2024/10-389") == ("2024", "389")
    assert split_number("x") is None
    assert split_number(None) is None


def test_site_dates_are_dd_mm_yyyy() -> None:
    assert str(parse_site_date("09.12.2020")) == "2020-12-09"
    assert parse_site_date("2020-12-09") is None
    assert parse_site_date("") is None


@EVERY_BIGM
async def test_the_session_is_opened_once(case: Case) -> None:
    fake = site_for(Reply.fixture(case.found))
    adapter = make_adapter(case.adapter, fake)
    await adapter.lookup(case.key)
    await adapter.lookup(case.key)
    assert fake.paths().count("GET /") == 1


@EVERY_BIGM
def test_supports_needs_both_numbers(case: Case) -> None:
    adapter = make_adapter(case.adapter, site_for())
    assert adapter.supports(case.key)
    assert not adapter.supports(make_key(karar_no=None))
    assert not adapter.supports(make_key(esas_no="x"))


@EVERY_BIGM
async def test_the_search_body_carries_both_numbers_and_the_paging(case: Case) -> None:
    fake = site_for(Reply.fixture(case.found))
    await make_adapter(case.adapter, fake).lookup(case.key)
    body = fake.bodies("/aramadetaylist")[0]["data"]
    esas, karar = split_number(case.key.esas_no), split_number(case.key.karar_no)
    assert esas and karar
    assert (body["esasYil"], body["esasIlkSiraNo"], body["esasSonSiraNo"]) == (
        esas[0],
        esas[1],
        esas[1],
    )
    assert (body["kararYil"], body["kararIlkSiraNo"], body["kararSonSiraNo"]) == (
        karar[0],
        karar[1],
        karar[1],
    )
    assert (body["pageSize"], body["pageNumber"]) == (10, 1)


@EVERY_BIGM
async def test_the_official_text_is_fetched_by_id(case: Case) -> None:
    fake = site_for()
    text = await make_adapter(case.adapter, fake).fetch_text("100000001")
    assert text is not None
    assert "FIXTURE TEXT" in text.body
    assert fake.requests[-1].url.params["id"] == "100000001"
    assert len(text.sha256) == 64


@EVERY_BIGM
async def test_an_empty_document_has_no_text(case: Case) -> None:
    fake = Site({"/getDokuman": Reply(200, '{"data": ""}')})
    assert await make_adapter(case.adapter, fake).fetch_text("1") is None


@EVERY_BIGM
async def test_an_error_envelope_is_not_an_empty_result(case: Case) -> None:
    fake = site_for(Reply.fixture("error_envelope.json"))
    with pytest.raises(UnexpectedResponse):
        await make_adapter(case.adapter, fake).lookup(case.key)


@EVERY_BIGM
async def test_an_unknown_answer_shape_is_an_error(case: Case) -> None:
    fake = site_for(Reply(200, '{"metadata": {"FMTY": "OK"}, "data": {}}'))
    with pytest.raises(UnexpectedResponse):
        await make_adapter(case.adapter, fake).lookup(case.key)


@EVERY_BIGM
async def test_a_date_the_site_writes_unreadably_comes_back_as_none(case: Case) -> None:
    answer = json.loads(Reply.fixture(case.found).content)
    for raw in answer["data"]["data"]:
        raw["kararTarihi"] = "not a date"
    fake = site_for(Reply(200, json.dumps(answer)))
    result = await make_adapter(case.adapter, fake).lookup(case.key)
    assert [row.decision_date for row in result.rows] == [None]
