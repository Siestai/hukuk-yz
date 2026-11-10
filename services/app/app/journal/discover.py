"""What the site of the journal offers (task 20): its issues, the decision pages of an issue and
the PDF address on a decision page.

The site is a WordPress. An issue is a category (`91-sayi-yargi-kararlari`), a decision a post.
The REST API lists both; the PDF address is not in its content, only in the HTML of the decision
page (a JetEngine link). When the API does not answer there is no fallback to HTML pages: the
scan fails and says why.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from app.journal.client import Fetcher, FetchError

BASE_URL = "https://yargi.calismatoplum.org"
PER_PAGE = 100
_SLUG_ISSUE = re.compile(r"(\d+)-sayi")
_PDF_LINK_CLASS = "jet-listing-dynamic-link__link"


class DiscoveryError(Exception):
    """The site's API did not give a usable answer; the message is the reason in the report."""


@dataclass
class Issue:
    no: int
    category_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Post:
    id: int
    link: str


async def _json_pages(fetcher: Fetcher, url: str, params: dict[str, str | int]) -> list[Any]:
    """The items of every page of a WordPress list (`X-WP-TotalPages`)."""
    items: list[Any] = []
    page, pages = 1, 1
    while page <= pages:
        try:
            reply = await fetcher.get(url, {**params, "per_page": PER_PAGE, "page": page})
            body = json.loads(reply.content)
        except FetchError as exc:
            raise DiscoveryError(f"{exc.url}: {exc.reason}") from exc
        except ValueError as exc:
            raise DiscoveryError(f"{url}: not_json") from exc
        if not isinstance(body, list):
            raise DiscoveryError(f"{url}: unexpected_answer")
        items += body
        total = {k.lower(): v for k, v in reply.headers.items()}.get("x-wp-totalpages", "1")
        pages = int(total) if total.isdigit() else 1
        page += 1
    return items


async def list_issues(fetcher: Fetcher, base_url: str = BASE_URL) -> dict[int, Issue]:
    """Every issue of the site by number. The number is the digits at the start of the category
    slug; two categories of one number (`82-sayi-yargi-kararlari-genel`) make one issue."""
    categories = await _json_pages(
        fetcher,
        f"{base_url}/wp-json/wp/v2/categories",
        {"search": "sayi", "_fields": "id,slug"},
    )
    issues: dict[int, Issue] = {}
    for category in categories:
        try:
            match = _SLUG_ISSUE.match(category["slug"])
            category_id = int(category["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DiscoveryError(f"{base_url}: unexpected_category") from exc
        if match:
            no = int(match[1])
            issues.setdefault(no, Issue(no)).category_ids.append(category_id)
    return issues


async def list_posts(fetcher: Fetcher, issue: Issue, base_url: str = BASE_URL) -> list[Post]:
    """The decision pages of an issue, oldest first, each once. A page whose address is not on
    the site's own host (or not http/https) is left out: the scan fetches from the journal only."""
    site = urlsplit(base_url)
    posts: dict[int, Post] = {}
    for category_id in issue.category_ids:
        items = await _json_pages(
            fetcher,
            f"{base_url}/wp-json/wp/v2/posts",
            {"categories": category_id, "_fields": "id,link"},
        )
        for item in items:
            try:
                post = Post(int(item["id"]), str(item["link"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise DiscoveryError(f"{base_url}: unexpected_post") from exc
            link = urlsplit(post.link)
            if link.scheme in ("http", "https") and link.netloc == site.netloc:
                posts[post.id] = post
    return sorted(posts.values(), key=lambda p: p.id)


def new_issue_numbers(issues: Iterable[int], archive_max: int) -> list[int]:
    """The issues of the site after the newest one the archive has, oldest first."""
    return sorted(no for no in issues if no > archive_max)


class _PdfLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        href = (values.get("href") or "").strip()
        classes = (values.get("class") or "").split()
        if _PDF_LINK_CLASS in classes and urlsplit(href).path.lower().endswith(".pdf"):
            self.hrefs.append(href)


def find_pdf_link(html: str, page_url: str) -> str | None:
    """The PDF address of a decision page (`a.jet-listing-dynamic-link__link` ending in `.pdf`),
    made absolute. A link to another host is not followed: the scan fetches from the journal's
    own site only."""
    parser = _PdfLinks()
    parser.feed(html)
    for href in parser.hrefs:
        url = urljoin(page_url, href)
        if urlsplit(url).netloc == urlsplit(page_url).netloc:
            return url
    return None
