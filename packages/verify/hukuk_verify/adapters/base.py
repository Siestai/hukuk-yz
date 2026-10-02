"""What every source adapter shares: the pacing, the 429 / captcha / robots handling and the
rule that a network failure is an exception, never "not in the source" (task 06 §3, §7, §8)."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from hukuk_verify.errors import (
    CaptchaRequired,
    RobotsDisallowed,
    SourceUnavailable,
)
from hukuk_verify.models import DecisionKey, LookupResult, OfficialText, Outcome
from hukuk_verify.ratelimit import RateLimiter
from hukuk_verify.robots import Robots, parse_robots

RATE_LIMIT_PAGE = "Erişim Sınırı Aşıldı"
CAPTCHA_MARKERS = ("DisplayCaptcha", "reCaptchaTimeout")


class SourceAdapter(ABC):
    SOURCE: ClassVar[str]  # `decision.verification_source`
    VERIFIED: ClassVar[Outcome]  # outcome of a found decision
    ORIGIN: ClassVar[str]
    # Yargıtay only: nothing up to 2009 is on the site (task 06 §7).
    PRE_2009_SKIP: ClassVar[bool] = False

    def __init__(self, client: httpx.AsyncClient, limiter: RateLimiter) -> None:
        """`client` arrives configured (proxy, user agent, timeouts); this package builds none."""
        self._client = client
        self.limiter = limiter
        self._robots: Robots | None = None

    @abstractmethod
    def supports(self, key: DecisionKey) -> bool:
        """Whether the decision carries what this source's query needs."""

    @abstractmethod
    async def lookup(self, key: DecisionKey) -> LookupResult: ...

    @abstractmethod
    async def fetch_text(self, ref: str) -> OfficialText | None: ...

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One paced request. A 429 (or the "Erişim Sınırı Aşıldı" page) backs off and retries;
        the limiter stops the source on the third in a row."""
        if self._robots is None and not url.endswith("/robots.txt"):
            await self._read_robots()
        if self._robots is not None and not self._robots.allows(url):
            stop = RobotsDisallowed(f"robots.txt disallows {url.split('?')[0]}")
            self.limiter.stop(stop)
            raise stop
        while True:
            await self.limiter.wait()
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                raise SourceUnavailable(type(exc).__name__) from exc
            if response.status_code == 429 or (
                "html" in response.headers.get("content-type", "")
                and RATE_LIMIT_PAGE in response.text
            ):
                await self.limiter.on_429()
                continue
            self.limiter.succeeded()
            return response

    async def _read_robots(self) -> None:
        response = await self._request("GET", f"{self.ORIGIN}/robots.txt")
        self._robots = parse_robots(
            response.status_code, response.headers.get("content-type", ""), response.text
        )

    def _json(self, response: httpx.Response) -> Any:
        """The body of an API answer. A captcha demand stops the source; it is never solved."""
        if any(marker in response.text for marker in CAPTCHA_MARKERS):
            stop = CaptchaRequired("the site asks for a captcha")
            self.limiter.stop(stop)
            raise stop
        if response.status_code != 200:
            raise SourceUnavailable(f"HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceUnavailable("answer is not JSON") from exc
