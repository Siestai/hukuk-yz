"""Per-source request pacing (task 06 §7). One limiter per source; concurrency is 1."""

import asyncio
import time
from collections.abc import Awaitable, Callable

from hukuk_verify.errors import RateLimitExhausted, RequestBudgetExceeded, SourceStopped

MIN_INTERVAL_SECONDS = 10.0
DEFAULT_INTERVAL_SECONDS = 12.0
DEFAULT_BACKOFF_SECONDS = (60.0, 120.0)
MAX_CONSECUTIVE_429 = 3


class RateLimiter:
    """Keeps `interval` seconds between two requests, backs off on 429 and stops the source on the
    third consecutive one (the third 429 stops instead of waiting a third time, so the backoff
    list has two steps). Neither the interval nor a backoff step may be below 10 seconds.

    `clock` and `sleep` are injectable so tests run on a fake clock."""

    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL_SECONDS,
        backoff: tuple[float, ...] = DEFAULT_BACKOFF_SECONDS,
        max_requests: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval < MIN_INTERVAL_SECONDS or any(b < MIN_INTERVAL_SECONDS for b in backoff):
            raise ValueError(f"interval and backoff must be at least {MIN_INTERVAL_SECONDS:g} s")
        if len(backoff) < MAX_CONSECUTIVE_429 - 1:
            raise ValueError("backoff needs a step for every 429 before the stopping one")
        self._interval = interval
        self._backoff = backoff
        self._max_requests = max_requests
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._consecutive_429 = 0
        self._stopped: SourceStopped | None = None
        self.requests = 0
        self.rate_limited = 0
        self.backoff_seconds = 0.0

    async def wait(self) -> None:
        """Call before every request: raises when the source is stopped or the budget is spent."""
        if self._stopped:
            raise self._stopped
        if self._max_requests is not None and self.requests >= self._max_requests:
            raise RequestBudgetExceeded(f"request budget of {self._max_requests} spent")
        if self._last is not None:
            delay = self._last + self._interval - self._clock()
            if delay > 0:
                await self._sleep(delay)
        self._last = self._clock()
        self.requests += 1

    def succeeded(self) -> None:
        self._consecutive_429 = 0

    async def on_429(self) -> None:
        """Back off before the retry, or stop the source on the third consecutive 429."""
        self.rate_limited += 1
        self._consecutive_429 += 1
        if self._consecutive_429 >= MAX_CONSECUTIVE_429:
            self._stopped = RateLimitExhausted("three consecutive 429 answers")
            raise self._stopped
        wait = self._backoff[self._consecutive_429 - 1]
        self.backoff_seconds += wait
        await self._sleep(wait)

    def stop(self, reason: SourceStopped) -> None:
        self._stopped = reason
