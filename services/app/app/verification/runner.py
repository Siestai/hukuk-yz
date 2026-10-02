"""Check the candidates of one court against its source (task 06 §6-§7).

Per decision: `verify`, then (unless a dry run) its own transaction. A failed lookup is recorded
as an `error` attempt and the run goes on; a stopped source ends the run for that court."""

import json
import random
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.verification.store import Candidate, apply_error, apply_result
from hukuk_verify import DecisionKey, Outcome, VerifyResult, verify
from hukuk_verify.adapters import SourceAdapter
from hukuk_verify.errors import RecordError, SourceStopped, SourceUnavailable, SourceUnreachable
from hukuk_verify.verify import is_pre_2009

SAMPLE_SIZE = 20
MAX_CONSECUTIVE_NETWORK_ERRORS = 3
YEAR_BANDS = ("<=2009", "2010-14", "2015+", "no date")
_UNSAFE = re.compile(r"[^\w-]")


def year_band(key: DecisionKey) -> str:
    if key.decision_date is None:
        return "no date"
    year = key.decision_date.year
    return "<=2009" if year <= 2009 else "2010-14" if year <= 2014 else "2015+"


def describe(key: DecisionKey) -> str:
    """How a decision is named in output: court, chamber and E/K, never text or parties."""
    chamber = " ".join(p for p in (key.bam_region, key.chamber) if p)
    return " ".join(
        p for p in (key.court, chamber, f"E. {key.esas_no}", f"K. {key.karar_no or '-'}") if p
    )


@dataclass
class SourceStats:
    court: str
    source: str
    candidates: int = 0
    unsupported: int = 0
    outcomes: Counter[str] = field(default_factory=Counter)
    by_band: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    fuzzy: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    skipped_pre_2009: int = 0
    # {"checked": n, "found": n, "heuristic_disabled": bool}; None when no sample was due
    sample: dict[str, int | bool] | None = None
    stopped: str | None = None
    downgrades: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)
    requests: int = 0
    rate_limited: int = 0
    backoff_seconds: float = 0.0


@dataclass(frozen=True)
class RunOptions:
    dry_run: bool = False
    skip_pre_2009: bool = True
    cache_dir: Path | None = None
    rng: random.Random = field(default_factory=random.Random)


def write_official_cache(cache_dir: Path, result: VerifyResult) -> None:
    """The raw official answer, outside the database and git (KVKK, copyright; task 06 §5)."""
    if result.official_text is None or result.official_ref is None:
        return
    target = cache_dir / result.source / f"{_UNSAFE.sub('_', result.official_ref)}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result.official_text.payload, ensure_ascii=False), encoding="utf-8"
    )


async def run_court(
    factory: async_sessionmaker[AsyncSession] | None,
    court: str,
    adapter: SourceAdapter,
    todo: list[Candidate],
    options: RunOptions,
    on_result: Callable[[Candidate, str], None] = lambda candidate, outcome: None,
) -> SourceStats:
    """`factory` None means nothing is written (`--keys`)."""
    stats = SourceStats(court, adapter.SOURCE)
    supported = [c for c in todo if adapter.supports(c.key)]
    stats.unsupported = len(todo) - len(supported)
    stats.candidates = len(supported)
    write = factory is not None and not options.dry_run
    network_errors = 0  # consecutive

    async def check(candidate: Candidate, skip_pre_2009: bool) -> str:
        """The outcome written, or `error`. Raises `SourceUnreachable` on the third network error
        in a row, after recording it."""
        nonlocal network_errors
        key = candidate.key
        try:
            result = await verify(adapter, key, skip_pre_2009=skip_pre_2009)
        except RecordError as exc:
            stats.errors[type(exc).__name__] += 1
            on_result(candidate, f"error ({type(exc).__name__}: {exc})")
            if write and candidate.id:
                assert factory is not None
                async with factory() as session, session.begin():
                    await apply_error(session, candidate.id, adapter.SOURCE, str(exc)[:200], _now())
            if isinstance(exc, SourceUnavailable):
                network_errors += 1
                if network_errors >= MAX_CONSECUTIVE_NETWORK_ERRORS:
                    raise SourceUnreachable(
                        f"{MAX_CONSECUTIVE_NETWORK_ERRORS} consecutive network errors"
                    ) from exc
            else:
                network_errors = 0
            return "error"
        network_errors = 0
        outcome = result.outcome.value
        if write and candidate.id:
            assert factory is not None
            async with factory() as session, session.begin():
                applied = await apply_result(session, candidate.id, result, _now())
            if applied.downgraded:
                outcome = applied.outcome
                stats.downgrades.append(describe(key))
        if write and options.cache_dir:
            write_official_cache(options.cache_dir, result)
        stats.outcomes[outcome] += 1
        stats.by_band[year_band(key)][outcome] += 1
        stats.fuzzy.update(result.matched.get("fuzzy", []))
        if result.matched.get("skipped"):
            stats.skipped_pre_2009 += 1
        if outcome == Outcome.mismatch.value:
            stats.mismatches.append(describe(key))
        on_result(candidate, outcome)
        return outcome

    try:
        skipping = options.skip_pre_2009 and adapter.PRE_2009_SKIP
        if skipping:
            old = [c for c in supported if is_pre_2009(adapter, c.key)]
            # The coverage check comes first: if the site does hold a skipped decision, the
            # heuristic is off for the rest of the run.
            sampled = options.rng.sample(old, min(SAMPLE_SIZE, len(old)))
            if sampled:
                answers = [await check(c, skip_pre_2009=False) for c in sampled]
                found = sum(a not in ("not_in_source", "error") for a in answers)
                stats.sample = {
                    "checked": len(sampled),
                    "found": found,
                    "heuristic_disabled": found > 0,
                }
                skipping = found == 0
            taken = {id(c) for c in sampled}
            supported = [c for c in supported if id(c) not in taken]
        for candidate in supported:
            await check(candidate, skip_pre_2009=skipping)
    except SourceStopped as exc:
        stats.stopped = f"{type(exc).__name__}: {exc}"

    limiter = adapter.limiter
    stats.requests = limiter.requests
    stats.rate_limited = limiter.rate_limited
    stats.backoff_seconds = limiter.backoff_seconds
    return stats


def _now() -> datetime:
    return datetime.now(UTC)
