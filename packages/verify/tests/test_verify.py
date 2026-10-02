from datetime import date

import httpx
import pytest
from fakes import FakeClock, Reply, Site, make_adapter, make_key

from hukuk_verify import Outcome, verify
from hukuk_verify.adapters import UyapEmsalAdapter, YargitayAdapter
from hukuk_verify.errors import SourceUnavailable
from hukuk_verify.ratelimit import RateLimiter


def yargitay_site(*search: Reply, document: Reply | None = None) -> Site:
    return Site(
        {
            "/": Reply(200, "<html></html>", "text/html"),
            "/aramadetaylist": list(search),
            "/getDokuman": document or Reply.fixture("yargitay_document.json"),
        }
    )


async def test_up_to_2009_is_not_in_source_without_a_query() -> None:
    fake = yargitay_site()
    result = await verify(
        make_adapter(YargitayAdapter, fake), make_key(decision_date=date(2009, 12, 31))
    )
    assert result.outcome is Outcome.not_in_source
    assert result.matched == {"skipped": "pre_2009_heuristic"}
    assert fake.requests == []


async def test_2010_is_queried() -> None:
    fake = yargitay_site(Reply.fixture("yargitay_empty.json"))
    await verify(make_adapter(YargitayAdapter, fake), make_key(decision_date=date(2010, 1, 1)))
    assert fake.bodies("/aramadetaylist")


async def test_the_skip_can_be_switched_off() -> None:
    fake = yargitay_site(Reply.fixture("yargitay_empty.json"))
    result = await verify(
        make_adapter(YargitayAdapter, fake),
        make_key(decision_date=date(2005, 1, 1)),
        skip_pre_2009=False,
    )
    assert "skipped" not in result.matched
    assert fake.bodies("/aramadetaylist")


async def test_other_sources_do_not_skip_old_decisions() -> None:
    fake = Site(
        {"/": Reply(200, "", "text/html"), "/aramadetaylist": Reply.fixture("emsal_empty.json")}
    )
    await verify(
        make_adapter(UyapEmsalAdapter, fake), make_key(court="bam", decision_date=date(2001, 1, 1))
    )
    assert fake.bodies("/aramadetaylist")


async def test_a_network_error_raises_instead_of_not_in_source() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    clock = FakeClock()
    adapter = YargitayAdapter(
        httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
        RateLimiter(clock=clock, sleep=clock.sleep),
    )
    with pytest.raises(SourceUnavailable):
        await verify(adapter, make_key())


async def test_a_found_decision_carries_the_hash_of_the_official_text() -> None:
    result = await verify(
        make_adapter(YargitayAdapter, yargitay_site(Reply.fixture("yargitay_found.json"))),
        make_key(),
    )
    assert result.official_text is not None
    assert len(result.official_text.sha256) == 64
    assert result.official_text.payload["data"].startswith("<html>")


async def test_hgk_source_chamber_found_in_the_heading_matches() -> None:
    heading = Reply(
        200, '{"data": "<html><p>Hukuk Genel Kurulu 2024/10-389 E. , 2025/12 K.</p></html>"}'
    )
    found = Reply(
        200,
        '{"data": {"data": [{"id": "7", "daire": "Hukuk Genel Kurulu", "esasNo": "2024/389",'
        ' "kararNo": "2025/12", "kararTarihi": "05.03.2025"}]}, "metadata": {"FMTY": "SUCCESS"}}',
    )
    key = make_key(
        court_level="hgk_iddk",
        chamber="",
        source_chamber="10",
        esas_no="2024/389",
        karar_no="2025/12",
        decision_date=date(2025, 3, 5),
    )
    result = await verify(
        make_adapter(YargitayAdapter, yargitay_site(found, document=heading)), key
    )
    assert result.outcome is Outcome.verified_official
    assert result.matched["source_chamber"] == "match"

    plain = Reply(
        200, '{"data": "<html><p>Hukuk Genel Kurulu 2024/389 E. , 2025/12 K.</p></html>"}'
    )
    result = await verify(make_adapter(YargitayAdapter, yargitay_site(found, document=plain)), key)
    assert result.outcome is Outcome.verified_official
    assert result.matched["source_chamber"] == "fuzzy"
    assert result.matched["fuzzy"] == ["source_chamber"]
