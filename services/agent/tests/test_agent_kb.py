"""The HTTP client of `/kb/search`: what it sends and how it reads the answer."""

from datetime import date
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from agent.kb import HttpKbClient, KbHit, KbUnavailable, Unreadable, UnreadableReason

BODY = {
    "results": [
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
    ],
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
        return httpx.Response(200, json={"results": []})

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


async def test_full_article_read_has_neighboring_paragraphs_and_stable_version_id() -> None:
    text = "(1) Birinci fıkra.\n(2) İkinci fıkra."
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "found",
                "review_status": "approved",
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
    assert (hits[0].review_status, hits[0].band) == ("approved", None)


async def test_an_unreviewed_article_read_keeps_its_status_and_band() -> None:
    body = {
        "status": "found",
        "review_status": "analyzed",
        "band": "medium",
        "extraction_id": "extraction-18",
        "version": {"text": "(1) Birinci fıkra.", "valid_from": "2003-06-10", "valid_to": None},
    }
    kb = client(httpx.MockTransport(lambda request: httpx.Response(200, json=body)))

    hits = await kb.read_article("4857 m.18", date(2026, 10, 3))

    assert (hits[0].review_status, hits[0].band) == ("analyzed", "medium")
    assert hits[0].complete
    # No published row to name: the extraction is the record, as it is for a search hit.
    assert hits[0].source_id == "extraction-18"


async def test_an_article_read_that_does_not_say_its_review_status_is_not_trusted() -> None:
    body = {"status": "found", "version": {"id": "version-18", "text": "(1) Birinci fıkra."}}
    kb = client(httpx.MockTransport(lambda request: httpx.Response(200, json=body)))

    with pytest.raises(KbUnavailable):
        await kb.read_article("4857 m.18", date(2026, 10, 3))


async def test_an_unreviewed_search_hit_keeps_its_band() -> None:
    unreviewed = {**BODY["results"][0], "review_status": "analyzed", "band": "high"}
    body = {"results": [unreviewed, BODY["results"][0]]}
    kb = client(httpx.MockTransport(lambda request: httpx.Response(200, json=body)))

    hits = await kb.search("4857")

    assert [(h.review_status, h.band) for h in hits] == [("analyzed", "high"), ("approved", None)]


@pytest.mark.parametrize(
    "body",
    [
        {"status": "gap"},
        {"status": "unknown_article"},
        {"status": "found", "review_status": "approved", "version": {"text": ""}},
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
    assert await _read_ref(
        kb, SourceRef(category="statute", ref="4857 m.18"), date(2026, 10, 3)
    ) == ([], [{"ref": "4857 m.18", "reason": "not_found"}])
    assert seen == ["/statutes/4857/articles/18"]


async def test_search_uses_read_unit_identity_instead_of_collapsing_articles() -> None:
    a = {
        **BODY["results"][0],
        "source_id": "same-statute",
        "parent_id": "article-18",
        "version_id": "version-18",
    }
    b = {**a, "parent_id": "article-19", "version_id": "version-19", "ref": "4857 m.19"}
    kb = client(httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [a, b]})))
    hits = await kb.search("4857")
    assert [h.source_id for h in hits] == ["version-18", "version-19"]


SECTION = {
    "status": "found",
    "ref": "2020/8",
    "section_no": "2.6.2.5",
    "citation": "2020/8 m.2.6.2.5",
    "title": "İdari Para Cezaları Genelgesi",
    "version": {
        "text": "Peşin ödeme indirimi",
        "heading": "Peşin ödeme",
        "valid_from": "2020-03-20",
        "valid_to": None,
    },
    "review_status": "analyzed",
    "band": "high",
    "extraction_id": "extraction-1",
    "source_id": "file-1",
}


async def test_a_genelge_section_is_read_whole_with_its_status_and_band() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=SECTION)

    read = await client(httpx.MockTransport(handle)).read_section(
        "2020/8 m.2.6.2.5", date(2026, 10, 3)
    )

    assert seen[0].url.path == "/admin-acts/2020-8/sections/2.6.2.5"
    assert seen[0].url.params["as_of"] == "2026-10-03"
    assert seen[0].headers["x-service-key"] == "secret-key"
    assert isinstance(read, KbHit)
    assert (read.source_id, read.category, read.ref) == (
        "extraction-1",
        "admin_act",
        "2020/8 m.2.6.2.5",
    )
    assert (read.review_status, read.band, read.complete) == ("analyzed", "high", True)
    assert read.valid_from == date(2020, 3, 20)
    assert [(m.text, m.char_start) for m in read.matches] == [("Peşin ödeme indirimi", 0)]


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(404, json={"code": "not_found"}), "not_found"),
        (
            httpx.Response(200, json={"status": "unknown_section", "reason": "not_published"}),
            "not_found",
        ),
        (httpx.Response(200, json={**SECTION, "status": "gap", "version": None}), "gap"),
        (
            httpx.Response(200, json={**SECTION, "status": "not_in_force", "reason": "repealed"}),
            "not_in_force",
        ),
    ],
)
async def test_only_a_found_section_is_read_and_the_rest_say_why(
    response: httpx.Response, reason: UnreadableReason
) -> None:
    kb = client(httpx.MockTransport(lambda request: response))

    assert await kb.read_section("2020/8 m.2.6.2.5", date(2026, 10, 3)) == Unreadable(reason)


async def test_a_section_read_that_fails_is_kb_unavailable() -> None:
    kb = client(httpx.MockTransport(lambda request: httpx.Response(503)))

    with pytest.raises(KbUnavailable):
        await kb.read_section("2020/8 m.2.6.2.5", date(2026, 10, 3))
