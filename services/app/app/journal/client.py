"""The polite HTTP client of the journal scan (task 20): one connection, one request at a time, a
pause between requests, an explicit User-Agent and a few tries on 429 / 5xx.

The scan talks to the `Fetcher` protocol; tests give it a fake, `PoliteClient` is the real one.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Protocol, Self

import httpx

USER_AGENT = "hukuk-yz-journal-scan/1.0 (+https://github.com/Siestai/hukuk-yz)"
MAX_RETRIES = 3
MAX_RETRY_AFTER_SECONDS = 60.0
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


class PoliteClient:
    """GETs with at least `delay` seconds between the end of one request and the start of the
    next. A 429 or 5xx (or a connection error) is tried again up to `MAX_RETRIES` times, waiting
    `delay * 2**n` (at least the `Retry-After` of a 429, capped); a 4xx otherwise fails at once."""

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
            follow_redirects=True,
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

    async def get(self, url: str, params: Params | None = None) -> Reply:
        reason = "unknown"
        for attempt in range(MAX_RETRIES + 1):
            await self._pause()
            retry_after = 0.0
            try:
                try:
                    response = await self._http.get(url, params=params)
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
                header = response.headers.get("retry-after", "")
                if response.status_code == 429 and header.isdigit():
                    retry_after = min(float(header), MAX_RETRY_AFTER_SECONDS)
            if attempt < MAX_RETRIES:
                await self._sleep(max(self._delay * 2**attempt, retry_after))
        raise FetchError(url, reason)
