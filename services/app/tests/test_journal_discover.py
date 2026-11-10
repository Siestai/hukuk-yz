"""Discovery on the journal's site (task 20): issues, decision pages, the PDF address."""

import json

import pytest

from app.journal.client import FetchError, Params, Reply
from app.journal.discover import (
    DiscoveryError,
    Issue,
    find_pdf_link,
    list_issues,
    list_posts,
    new_issue_numbers,
)

BASE = "https://yargi.calismatoplum.org"


class Wp:
    """The REST lists of a WordPress: rows by route, `per_page` rows to a page."""

    def __init__(
        self, categories: list[int] | None = None, posts: int = 0, per_page: int = 100
    ) -> None:
        self.categories = categories or []
        self.posts = posts
        self.per_page = per_page
        self.requests: list[str] = []

    async def get(self, url: str, params: Params | None = None) -> Reply:
        self.requests.append(url)
        params = params or {}
        if url.endswith("/categories"):
            rows = [{"id": 6000 + n, "slug": f"{n}-sayi-yargi-kararlari"} for n in self.categories]
        else:
            rows = [{"id": 1000 + n, "link": f"{BASE}/karar-{n}/"} for n in range(self.posts)]
        page, size = int(params["page"]), min(int(params["per_page"]), self.per_page)
        pages = max(-(-len(rows) // size), 1)
        headers = {"X-WP-TotalPages": str(pages)}
        return Reply(200, headers, json.dumps(rows[(page - 1) * size : page * size]).encode())


class Down:
    async def get(self, url: str, params: Params | None = None) -> Reply:
        raise FetchError(url, "http_503")


async def test_the_issues_are_numbered_by_their_category_slug() -> None:
    issues = await list_issues(Wp(categories=[89, 90, 91]))
    assert sorted(issues) == [89, 90, 91]
    assert issues[91].category_ids == [6091]


async def test_two_categories_of_one_number_are_one_issue() -> None:
    class TwoCategories:
        async def get(self, url: str, params: Params | None = None) -> Reply:
            rows = [
                {"id": 1, "slug": "82-sayi-yargi-kararlari"},
                {"id": 2, "slug": "82-sayi-yargi-kararlari-genel"},
                {"id": 3, "slug": "sayi-yok"},
            ]
            return Reply(200, {}, json.dumps(rows).encode())

    issues = await list_issues(TwoCategories())
    assert {no: i.category_ids for no, i in issues.items()} == {82: [1, 2]}


async def test_every_page_of_the_posts_is_read() -> None:
    site = Wp(posts=5, per_page=2)
    found = await list_posts(site, Issue(91, [6091]))
    assert [p.id for p in found] == [1000, 1001, 1002, 1003, 1004]
    assert len(site.requests) == 3  # 2 + 2 + 1


async def test_a_post_link_to_another_host_or_scheme_is_skipped() -> None:
    class Foreign:
        async def get(self, url: str, params: Params | None = None) -> Reply:
            links = [
                f"{BASE}/ok/",
                "http://169.254.169.254/latest/",
                "https://elsewhere.test/karar/",
                "file:///etc/passwd",
            ]
            rows = [{"id": n, "link": link} for n, link in enumerate(links)]
            return Reply(200, {}, json.dumps(rows).encode())

    assert [p.link for p in await list_posts(Foreign(), Issue(91, [6091]))] == [f"{BASE}/ok/"]


async def test_the_issues_list_follows_its_pages_too() -> None:
    site = Wp(categories=[1, 2, 3, 4, 5], per_page=2)
    assert sorted(await list_issues(site)) == [1, 2, 3, 4, 5]


async def test_an_api_that_does_not_answer_is_a_discovery_error_not_a_guess() -> None:
    with pytest.raises(DiscoveryError, match="http_503"):
        await list_issues(Down())


async def test_an_answer_that_is_not_json_is_a_discovery_error() -> None:
    class Html:
        async def get(self, url: str, params: Params | None = None) -> Reply:
            return Reply(200, {}, b"<html>maintenance</html>")

    with pytest.raises(DiscoveryError, match="not_json"):
        await list_issues(Html())


def test_only_issues_after_the_archive_are_new() -> None:
    assert new_issue_numbers([88, 89, 90, 92, 91], 90) == [91, 92]
    assert new_issue_numbers([88, 89, 90], 90) == []


def test_the_pdf_link_is_the_jetengine_link_that_ends_in_pdf() -> None:
    url = f"{BASE}/wp-content/uploads/2026/10/70.pdf"
    html = (
        f'<a href="{BASE}/other.pdf" class="menu">Eski</a><div class="jet-listing-dynamic-link">'
        f'<a href="{url}" class="jet-listing-dynamic-link__link" target="_blank">PDF</a></div>'
    )
    assert find_pdf_link(html, f"{BASE}/karar/") == url


def test_a_relative_pdf_link_is_made_absolute() -> None:
    html = '<a class="x jet-listing-dynamic-link__link" href="/wp-content/a.PDF">PDF</a>'
    assert find_pdf_link(html, f"{BASE}/karar/") == f"{BASE}/wp-content/a.PDF"


@pytest.mark.parametrize(
    "html",
    [
        "<html></html>",
        f'<a class="menu" href="{BASE}/a.pdf">other link</a>',
        f'<a class="jet-listing-dynamic-link__link" href="{BASE}/page/">not a pdf</a>',
        '<a class="jet-listing-dynamic-link__link" href="https://elsewhere.test/a.pdf">x</a>',
    ],
)
def test_a_page_without_a_pdf_link_of_the_site_has_none(html: str) -> None:
    assert find_pdf_link(html, f"{BASE}/karar/") is None
