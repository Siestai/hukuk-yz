"""Behaviour every adapter shares: 429, captcha, robots, request budget and failures that must
never turn into `not_in_source`. Run over all four sources."""

from dataclasses import dataclass

import httpx
import pytest
from fakes import NO_ROBOTS, RATE_PAGE, TOO_MANY, FakeClock, Reply, Site, make_adapter, make_key

from hukuk_verify.adapters import (
    AymAdapter,
    DanistayAdapter,
    SourceAdapter,
    UyapEmsalAdapter,
    YargitayAdapter,
)
from hukuk_verify.errors import (
    CaptchaRequired,
    RateLimitExhausted,
    RequestBudgetExceeded,
    RobotsDisallowed,
    SourceUnavailable,
    UnexpectedResponse,
)
from hukuk_verify.models import DecisionKey


@dataclass
class Case:
    adapter: type[SourceAdapter]
    key: DecisionKey
    search_path: str
    found: str  # fixture served for a successful search


CASES = {
    "yargitay": Case(YargitayAdapter, make_key(), "/aramadetaylist", "yargitay_found.json"),
    "emsal": Case(
        UyapEmsalAdapter,
        make_key(
            court="bam",
            court_level="bam_bim",
            chamber="9. HD",
            bam_region="Gaziantep",
            esas_no="2022/1258",
            karar_no="2022/1822",
        ),
        "/aramadetaylist",
        "emsal_found.json",
    ),
    "danistay": Case(
        DanistayAdapter,
        make_key(court="danistay", chamber="10. D", esas_no="2026/940", karar_no="2026/402"),
        "/aramadetaylist",
        "danistay_found.json",
    ),
    "aym": Case(
        AymAdapter,
        make_key(
            court="aym",
            court_level="aym",
            chamber="",
            esas_no="2024/157",
            karar_no="2025/121",
            decision_kind="norm_denetimi",
        ),
        "/api/core/public/search",
        "aym_search_found.json",
    ),
}
EVERY_SOURCE = pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())


def site_for(case: Case, *search: Reply) -> Site:
    return Site({"/": Reply(200, "<html></html>", "text/html"), case.search_path: list(search)})


@EVERY_SOURCE
async def test_429_backs_off_and_retries(case: Case) -> None:
    site = site_for(case, TOO_MANY, Reply.fixture(case.found))
    clock = FakeClock()
    adapter = make_adapter(case.adapter, site, clock)
    result = await adapter.lookup(case.key)
    assert len(result.rows) == 1
    assert 60 in clock.sleeps
    assert adapter.limiter.rate_limited == 1


@EVERY_SOURCE
async def test_the_rate_limit_page_counts_as_429(case: Case) -> None:
    site = site_for(case, RATE_PAGE, Reply.fixture(case.found))
    clock = FakeClock()
    adapter = make_adapter(case.adapter, site, clock)
    assert len((await adapter.lookup(case.key)).rows) == 1
    assert 60 in clock.sleeps


@EVERY_SOURCE
async def test_three_429s_in_a_row_stop_the_source(case: Case) -> None:
    site = site_for(case, TOO_MANY)
    adapter = make_adapter(case.adapter, site)
    with pytest.raises(RateLimitExhausted):
        await adapter.lookup(case.key)
    sent = len(site.requests)
    with pytest.raises(RateLimitExhausted):
        await adapter.lookup(case.key)
    assert len(site.requests) == sent


@EVERY_SOURCE
async def test_a_captcha_demand_stops_the_source(case: Case) -> None:
    site = site_for(case, Reply(200, '{"metadata": {"FMC": "DisplayCaptcha"}}'))
    adapter = make_adapter(case.adapter, site)
    with pytest.raises(CaptchaRequired):
        await adapter.lookup(case.key)
    sent = len(site.requests)
    with pytest.raises(CaptchaRequired):
        await adapter.lookup(case.key)
    assert len(site.requests) == sent


@EVERY_SOURCE
async def test_robots_disallow_blocks_the_request(case: Case) -> None:
    site = Site(
        {
            "/robots.txt": Reply(200, "User-agent: *\nDisallow: /\n", "text/plain"),
            "/": Reply(200, "<html></html>", "text/html"),
        }
    )
    adapter = make_adapter(case.adapter, site)
    with pytest.raises(RobotsDisallowed):
        await adapter.lookup(case.key)
    assert site.paths() == ["GET /robots.txt"]


@EVERY_SOURCE
async def test_robots_is_read_once_and_a_json_error_is_no_rule(case: Case) -> None:
    site = site_for(case, Reply.fixture(case.found))
    site._routes["/robots.txt"] = NO_ROBOTS
    adapter = make_adapter(case.adapter, site)
    await adapter.lookup(case.key)
    await adapter.lookup(case.key)
    assert site.paths().count("GET /robots.txt") == 1


@EVERY_SOURCE
async def test_a_network_error_is_an_exception_not_an_empty_result(case: Case) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    adapter = case.adapter(
        httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
        make_adapter(case.adapter, Site({})).limiter,
    )
    with pytest.raises(SourceUnavailable):
        await adapter.lookup(case.key)


@EVERY_SOURCE
async def test_a_server_error_is_an_exception(case: Case) -> None:
    site = site_for(case, Reply(503, "<html>down</html>", "text/html"))
    with pytest.raises(SourceUnavailable):
        await make_adapter(case.adapter, site).lookup(case.key)


@EVERY_SOURCE
async def test_the_request_budget_is_never_exceeded(case: Case) -> None:
    site = site_for(case, Reply.fixture(case.found))
    adapter = make_adapter(case.adapter, site, max_requests=20)
    with pytest.raises(RequestBudgetExceeded):
        for _ in range(30):
            await adapter.lookup(case.key)
    assert len(site.requests) == 20


@pytest.mark.parametrize("name", ["yargitay", "emsal", "danistay"])
async def test_an_error_envelope_is_not_an_empty_result(name: str) -> None:
    case = CASES[name]
    site = site_for(case, Reply.fixture("error_envelope.json"))
    with pytest.raises(UnexpectedResponse):
        await make_adapter(case.adapter, site).lookup(case.key)
