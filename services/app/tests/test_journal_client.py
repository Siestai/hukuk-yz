"""The polite client of the journal scan (task 20): pauses, User-Agent, retries."""

import httpx
import pytest

from app.journal.client import MAX_RETRIES, USER_AGENT, FetchError, PoliteClient


class Clock:
    """A clock the fake `sleep` moves, so that the tests wait for nothing."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def client(clock: Clock, handler: httpx.MockTransport, delay: float = 2.0) -> PoliteClient:
    return PoliteClient(delay, transport=handler, sleep=clock.sleep, clock=clock)


async def test_requests_carry_the_user_agent_and_keep_the_pause() -> None:
    clock, seen = Clock(), []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, content=b"ok")

    async with client(clock, httpx.MockTransport(handle)) as c:
        for _ in range(3):
            assert (await c.get("https://x.test/a")).content == b"ok"
    assert seen == [USER_AGENT] * 3
    assert clock.sleeps == [2.0, 2.0]


async def test_the_pause_counts_from_the_end_of_a_slow_request() -> None:
    clock = Clock()

    def handle(request: httpx.Request) -> httpx.Response:
        clock.now += 10.0  # the server took its time
        return httpx.Response(200)

    async with client(clock, httpx.MockTransport(handle)) as c:
        await c.get("https://x.test/a")
        await c.get("https://x.test/b")
    assert clock.sleeps == [2.0]


async def test_a_429_is_tried_again_and_then_succeeds() -> None:
    clock, answers = Clock(), [429, 503, 200]

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(answers.pop(0), content=b"body")

    async with client(clock, httpx.MockTransport(handle), delay=0) as c:
        reply = await c.get("https://x.test/a")
    assert (reply.status, reply.content, answers) == (200, b"body", [])


async def test_after_the_third_retry_the_error_is_final() -> None:
    clock, calls = Clock(), []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"})

    async with client(clock, httpx.MockTransport(handle), delay=0) as c:
        with pytest.raises(FetchError) as caught:
            await c.get("https://x.test/a")
    assert (caught.value.url, caught.value.reason) == ("https://x.test/a", "http_429")
    assert len(calls) == MAX_RETRIES + 1
    assert clock.sleeps == [7.0] * MAX_RETRIES  # Retry-After is the least wait


async def test_the_wait_between_tries_grows() -> None:
    clock = Clock()

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with client(clock, httpx.MockTransport(handle), delay=1.0) as c:
        with pytest.raises(FetchError) as caught:
            await c.get("https://x.test/a")
    assert caught.value.reason == "http_500"
    backoff = [s for s in clock.sleeps if s >= 1.0]
    assert backoff[:MAX_RETRIES] == [1.0, 2.0, 4.0]


async def test_a_404_is_not_tried_again() -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    async with client(Clock(), httpx.MockTransport(handle), delay=0) as c:
        with pytest.raises(FetchError) as caught:
            await c.get("https://x.test/a")
    assert (caught.value.reason, len(calls)) == ("http_404", 1)


async def test_a_dropped_connection_is_tried_again_then_reported() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    async with client(Clock(), httpx.MockTransport(handle), delay=0) as c:
        with pytest.raises(FetchError) as caught:
            await c.get("https://x.test/a")
    assert caught.value.reason == "connect_error"
