"""The HTTP client of `/kb/search`: what it sends and how it reads the answer."""

from datetime import date
from typing import Any

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


async def test_real_search_contract_uses_results() -> None:
    body = {"mode": "fulltext", "results": BODY["items"]}
    hits = await client(httpx.MockTransport(lambda request: httpx.Response(200, json=body))).search(
        "q"
    )
    assert hits[0].ref == "4857 m.18"
    assert not hits[0].complete


async def test_full_article_read_has_neighboring_paragraphs_and_stable_version_id() -> None:
    text = "(1) Birinci fıkra.\n(2) İkinci fıkra."
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "found",
                "version": {
                    "id": "version-18",
                    "text": text,
                    "valid_from": "2003-06-10",
                    "valid_to": None,
                },
            },
        )

    hits = await client(httpx.MockTransport(handle)).read_article("4857 m.18", date(2026, 10, 3))
    assert seen[0].url.path == "/statutes/4857/articles/18"
    assert seen[0].headers["x-service-key"] == "secret-key"
    assert hits[0].complete
    assert hits[0].source_id == "version-18"
    assert hits[0].matches[0].text == text
    assert hits[0].matches[0].char_start == 0
    assert hits[0].matches[0].char_end == len(text)


@pytest.mark.parametrize(
    "body",
    [
        {"status": "gap"},
        {"status": "unknown_article"},
        {"status": "found", "version": {"text": ""}},
    ],
)
async def test_missing_article_never_falls_back_to_search_excerpts(body: dict[str, Any]) -> None:
    from agent.nodes import _read_ref
    from agent.topics import SourceRef

    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=body)

    kb = client(httpx.MockTransport(handle))
    assert (
        await _read_ref(kb, SourceRef(category="statute", ref="4857 m.18"), date(2026, 10, 3))
        is None
    )
    assert seen == ["/statutes/4857/articles/18"]


async def test_search_uses_read_unit_identity_instead_of_collapsing_articles() -> None:
    a = {
        **BODY["items"][0],
        "source_id": "same-statute",
        "parent_id": "article-18",
        "version_id": "version-18",
    }
    b = {**a, "parent_id": "article-19", "version_id": "version-19", "ref": "4857 m.19"}
    kb = client(httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [a, b]})))
    hits = await kb.search("4857")
    assert [h.source_id for h in hits] == ["version-18", "version-19"]
