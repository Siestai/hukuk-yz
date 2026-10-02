"""Test doubles for the adapters: a scripted site behind `httpx.MockTransport` and a fake clock.
Nothing here touches the network."""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from hukuk_verify.adapters.base import SourceAdapter
from hukuk_verify.models import DecisionKey
from hukuk_verify.ratelimit import RateLimiter

FIXTURES = Path(__file__).parent / "fixtures"


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> Any:
    return json.loads(load_text(name))


@dataclass
class Reply:
    status: int = 200
    content: str = ""
    content_type: str = "application/json"

    @classmethod
    def fixture(cls, name: str, status: int = 200) -> "Reply":
        ctype = "text/html" if name.endswith(".html") else "application/json"
        return cls(status, load_text(name), ctype)


TOO_MANY = Reply(429, "", "text/plain")
RATE_PAGE = Reply(200, "<html>Erişim Sınırı Aşıldı</html>", "text/html")
NO_ROBOTS = Reply(404, '{"error": "No static resource robots.txt"}', "application/json")


class Site:
    """Answers by URL path. A list of replies is served in order, the last one repeating; a path
    that is not scripted answers 404 (robots.txt included, which means no rules)."""

    def __init__(self, routes: dict[str, Reply | list[Reply]]) -> None:
        self._routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self._routes.get(request.url.path, NO_ROBOTS)
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        return httpx.Response(
            reply.status,
            content=reply.content.encode(),
            headers={"content-type": reply.content_type},
        )

    def paths(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.requests]

    def bodies(self, path: str) -> list[dict[str, Any]]:
        """JSON bodies posted to `path`."""
        return [json.loads(r.content) for r in self.requests if r.url.path == path and r.content]


@dataclass
class FakeClock:
    now: float = 1000.0
    sleeps: list[float] = field(default_factory=list)

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_adapter[A: SourceAdapter](
    cls: type[A], site: Site, clock: FakeClock | None = None, max_requests: int | None = None
) -> A:
    clock = clock or FakeClock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep, max_requests=max_requests)
    client = httpx.AsyncClient(transport=httpx.MockTransport(site))
    return cls(client, limiter)


def make_key(**overrides: Any) -> DecisionKey:
    """A Yargıtay 9. HD decision; override what a test needs."""
    fields: dict[str, Any] = {
        "court": "yargitay",
        "court_level": "daire",
        "chamber": "9. HD",
        "source_chamber": "",
        "bam_region": "",
        "esas_no": "2017/17327",
        "karar_no": "2020/14291",
        "decision_date": date(2020, 12, 9),
        "decision_kind": "karar",
    }
    return DecisionKey(**{**fields, **overrides})
