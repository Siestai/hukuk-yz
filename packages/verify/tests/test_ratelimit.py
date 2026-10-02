import pytest
from fakes import FakeClock

from hukuk_verify.errors import RateLimitExhausted, RequestBudgetExceeded, SourceStopped
from hukuk_verify.ratelimit import RateLimiter


def limiter(clock: FakeClock, **kwargs: object) -> RateLimiter:
    return RateLimiter(clock=clock, sleep=clock.sleep, **kwargs)  # type: ignore[arg-type]


async def test_requests_are_at_least_ten_seconds_apart() -> None:
    clock = FakeClock()
    rl = limiter(clock)
    stamps = []
    for _ in range(4):
        await rl.wait()
        stamps.append(clock.now)
        clock.now += 1  # the request itself takes a second
    gaps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]
    assert all(gap >= 10 for gap in gaps)
    assert clock.sleeps == [11, 11, 11]  # 12 s interval minus the 1 s the request took


async def test_the_first_request_does_not_wait() -> None:
    clock = FakeClock()
    await limiter(clock).wait()
    assert clock.sleeps == []


def test_settings_below_the_floor_are_rejected() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError, match="at least 10"):
        limiter(clock, interval=9.9)
    with pytest.raises(ValueError, match="at least 10"):
        limiter(clock, backoff=(5.0, 120.0))
    assert limiter(clock, interval=10.0)


async def test_429_backs_off_60_then_120_and_the_third_stops_the_source() -> None:
    clock = FakeClock()
    rl = limiter(clock)
    await rl.on_429()
    await rl.on_429()
    assert clock.sleeps == [60, 120]
    with pytest.raises(RateLimitExhausted):
        await rl.on_429()
    assert (rl.rate_limited, rl.backoff_seconds) == (3, 180)
    with pytest.raises(SourceStopped):
        await rl.wait()


async def test_a_success_resets_the_429_count() -> None:
    clock = FakeClock()
    rl = limiter(clock)
    await rl.on_429()
    await rl.on_429()
    rl.succeeded()
    await rl.on_429()
    assert clock.sleeps == [60, 120, 60]


async def test_request_budget_is_a_hard_stop() -> None:
    clock = FakeClock()
    rl = limiter(clock, max_requests=3)
    for _ in range(3):
        await rl.wait()
    with pytest.raises(RequestBudgetExceeded):
        await rl.wait()
    assert rl.requests == 3
