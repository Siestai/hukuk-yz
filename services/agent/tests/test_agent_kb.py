"""The HTTP client of `/kb/search`: what it sends and how it reads the answer."""

from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from agent.kb import HttpKbClient, KbUnavailable

BODY = {
    "items": [
        {
            "source_id": "statute:4857:m18",
            "category": "statute",
            "title": "4857 sayılı İş Kanunu m.18",
            "ref": "4857 m.18",
            "review_status": "approved",
            "verification": None,
            "valid_from": "2017-01-01",
            "valid_to": None,
            "score": 0.9,
            "matches": [
                {"chunk_id": "c1", "text": "metin", "char_start": 0, "char_end": 5, "extra": 1},
                {"chunk_id": "c2", "text": None},
            ],
        }
    ]
}


def client(handler: httpx.MockTransport) -> HttpKbClient:
    return HttpKbClient("http://app.test", SecretStr("secret-key"), 5.0, transport=handler)


async def test_the_search_sends_the_service_key_and_the_filters() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=BODY)

    hits = await client(httpx.MockTransport(handle)).search(
        "4857 m.18", categories=["statute"], as_of=date(2026, 10, 3), limit=5
    )

    request = seen[0]
    assert request.headers["X-Service-Key"] == "secret-key"
    assert request.url.path == "/kb/search"
    assert request.url.params["q"] == "4857 m.18"
    assert request.url.params["category"] == "statute"
    assert request.url.params["as_of"] == "2026-10-03"
    assert request.url.params["limit"] == "5"
    assert hits[0].valid_from == date(2017, 1, 1)
    assert [m.text for m in hits[0].matches] == ["metin", None]


async def test_no_filter_is_sent_when_none_is_given() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"items": []})

    assert await client(httpx.MockTransport(handle)).search("q") == []
    assert set(seen[0].url.params) == {"q", "limit"}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"hits": []}),
    ],
)
async def test_a_failure_or_an_unexpected_answer_is_kb_unavailable(
    response: httpx.Response,
) -> None:
    kb = client(httpx.MockTransport(lambda request: response))

    with pytest.raises(KbUnavailable):
        await kb.search("q")
