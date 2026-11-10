"""The polite HTTP client of the journal scan (task 20): one connection, one request at a time, a
pause between requests, an explicit User-Agent and a few tries on 429 / 5xx.

The scan talks to the `Fetcher` protocol; tests give it a fake, `PoliteClient` is the real one.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Protocol, Self
from urllib.parse import urljoin, urlsplit

import httpx

USER_AGENT = "hukuk-yz-journal-scan/1.0 (+https://github.com/Siestai/hukuk-yz)"
MAX_RETRIES = 3
MAX_RETRY_AFTER_SECONDS = 300.0
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 30.0

Params = Mapping[str, str | int]


@dataclass(frozen=True)
class Reply:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FetchError(Exception):
    """A request that did not end in a 2xx answer, or an answer that cannot be used (not a PDF,
    too large); `reason` is what the report shows."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


class Fetcher(Protocol):
    async def get(self, url: str, params: Params | None = None) -> Reply:
        """The answer to a GET; a failure (after the tries) raises `FetchError`."""


def _retry_after(header: str) -> float:
    """The seconds a `Retry-After` asks for, in either form (delta-seconds or HTTP date); 0 when
    it is absent or unreadable."""
    header = header.strip()
    if header.isdigit():
        return float(header)
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max((when - datetime.now(UTC)).total_seconds(), 0.0)


class PoliteClient:
    """GETs with at least `delay` seconds between the end of one request and the start of the
    next. A 429 or 5xx (or a connection error) is tried again up to `MAX_RETRIES` times, waiting
    `delay * 2**n` (at least the `Retry-After` of a 429 or 503, seconds or HTTP date; one above
    `MAX_RETRY_AFTER_SECONDS` ends the request); a 4xx otherwise fails at once. Redirects are
    followed by hand and only within the host of the request: the scan fetches from the journal's
    own site only."""

    def __init__(
        self,
        delay: float,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._delay = delay
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None
        self._http = httpx.AsyncClient(
            transport=transport,
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    async def _pause(self) -> None:
        if self._last is not None:
            wait = self._last + self._delay - self._clock()
            if wait > 0:
                await self._sleep(wait)

    async def _fetch(self, url: str, params: Params | None) -> httpx.Response:
        """One GET with its redirects: a hop to another host or to a scheme other than http(s)
        is refused."""
        host, target = urlsplit(url).netloc, url
        for _ in range(MAX_REDIRECTS + 1):
            response = await self._http.get(target, params=params)
            location = response.headers.get("location")
            if not response.is_redirect or location is None:
                return response
            target = urljoin(target, location)
            parts = urlsplit(target)
            if parts.scheme not in ("http", "https") or parts.netloc != host:
                raise FetchError(url, "redirect_refused")
            params = None
            self._last = self._clock()
            await self._pause()
        raise FetchError(url, "too_many_redirects")

    async def get(self, url: str, params: Params | None = None) -> Reply:
        reason = "unknown"
        for attempt in range(MAX_RETRIES + 1):
            await self._pause()
            retry_after = 0.0
            try:
                try:
                    response = await self._fetch(url, params)
                finally:
                    self._last = self._clock()
            except httpx.TimeoutException:
                reason = "timeout"
            except httpx.TransportError:
                reason = "connect_error"
            else:
                if response.is_success:
                    return Reply(response.status_code, dict(response.headers), response.content)
                reason = f"http_{response.status_code}"
                if response.status_code != 429 and response.status_code < 500:
                    raise FetchError(url, reason)
                if response.status_code in (429, 503):
                    retry_after = _retry_after(response.headers.get("retry-after", ""))
                    if retry_after > MAX_RETRY_AFTER_SECONDS:
                        raise FetchError(url, "retry_after_too_long")
            if attempt < MAX_RETRIES:
                await self._sleep(max(self._delay * 2**attempt, retry_after))
        raise FetchError(url, reason)
