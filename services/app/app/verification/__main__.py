"""Check decisions against their official source (task 06).

    LIVE=1 python -m app.verification [--court yargitay|bam|aym|danistay] [--limit N]
        [--dry-run] [--report DIR] [--i-have-permission] [--recheck mismatch]
        [--no-pre2009-skip] [--keys FILE.jsonl]

Without LIVE=1 nothing is sent: the run only prints how many decisions are due. With LIVE=1 a
source gets at most 20 requests (`--limit` lowers that), and only `--i-have-permission` lifts
the cap; the permission for bulk queries is Orhan's (task 06 §8). `--limit` counts requests per
source, robots.txt and the session page included. `--dry-run` queries but writes nothing.

`--keys FILE.jsonl` needs no database: each line names a decision (court, esas_no, karar_no,
optional chamber, decision_date, source_chamber, bam_region, decision_kind, court_level), the
sources are queried and the outcome printed; nothing is stored. The acceptance check of
docs/verify-acceptance.md uses it.

Proxies and the contact address come from the environment (VerifySettings)."""

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path

import httpx

from app.db import make_engine, make_session_factory
from app.settings import VerifySettings, get_settings, get_verify_settings
from app.verification.report import build_summary, write_report
from app.verification.runner import RunOptions, SourceStats, describe, run_court
from app.verification.store import COURTS, Candidate, candidates
from hukuk_verify import DecisionKey
from hukuk_verify.adapters import (
    AymAdapter,
    DanistayAdapter,
    SourceAdapter,
    UyapEmsalAdapter,
    YargitayAdapter,
)
from hukuk_verify.ratelimit import RateLimiter

ADAPTERS: dict[str, type[SourceAdapter]] = {
    "yargitay": YargitayAdapter,
    "bam": UyapEmsalAdapter,
    "aym": AymAdapter,
    "danistay": DanistayAdapter,
}
PROXY_SETTING = {
    "yargitay": "verify_proxy_yargitay",
    "bam": "verify_proxy_emsal",
    "aym": "verify_proxy_aym",
    "danistay": "verify_proxy_danistay",
}
COURT_LEVEL = {"yargitay": "daire", "bam": "bam_bim", "aym": "aym", "danistay": "daire"}
UNPERMITTED_REQUEST_CAP = 20
DRY_RUN_REQUEST_CAP = 20
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def build_client(proxy: str | None, user_agent: str) -> httpx.AsyncClient:
    """The configured client an adapter receives: proxy and identifying User-Agent. The proxy
    comes from `VERIFY_PROXY_*` only; HTTP(S)_PROXY of the environment is not picked up."""
    return httpx.AsyncClient(
        proxy=proxy, headers={"User-Agent": user_agent}, timeout=TIMEOUT, trust_env=False
    )


def user_agent(contact: str) -> str:
    """Identifying, no browser imitation (task 06 §8). ASCII only: a header value must be."""
    return f"hukuk-yz-verify/{version('hukuk-verify')} (iletisim: {contact})"


def request_budget(limit: int | None, dry_run: bool, permission: bool) -> int | None:
    """Requests one source may get: `--limit`, 20 for a dry run, never more than 20 without
    `--i-have-permission`. None is unlimited."""
    if dry_run and limit is None:
        limit = DRY_RUN_REQUEST_CAP
    if not permission:
        return min(limit or UNPERMITTED_REQUEST_CAP, UNPERMITTED_REQUEST_CAP)
    return limit


def read_keys(path: Path) -> dict[str, list[Candidate]]:
    """Candidates by court from a JSONL file of decisions to look up."""
    found: dict[str, list[Candidate]] = defaultdict(list)
    with path.open(encoding="utf-8") as fh:
        for line in filter(str.strip, fh):
            row = json.loads(line)
            court = row["court"]
            if court not in ADAPTERS:
                raise SystemExit(f"--keys: unknown court {court!r} (one of {', '.join(ADAPTERS)})")
            found[court].append(
                Candidate(
                    None,
                    DecisionKey(
                        court=court,
                        court_level=row.get("court_level", COURT_LEVEL[court]),
                        chamber=row.get("chamber", ""),
                        source_chamber=row.get("source_chamber", ""),
                        bam_region=row.get("bam_region", ""),
                        esas_no=row.get("esas_no"),
                        karar_no=row.get("karar_no"),
                        decision_date=date.fromisoformat(row["decision_date"])
                        if row.get("decision_date")
                        else None,
                        decision_kind=row.get("decision_kind", "karar"),
                    ),
                )
            )
    return found


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.verification", description=__doc__)
    p.add_argument("--court", choices=list(ADAPTERS), help="one court only (default: all)")
    p.add_argument("--limit", type=int, help="requests per source (default 20 without permission)")
    p.add_argument("--dry-run", action="store_true", help="query, but write nothing")
    p.add_argument("--report", type=Path, help="directory for verify-summary.md / .json")
    p.add_argument("--i-have-permission", action="store_true", help="lift the 20-request cap")
    p.add_argument("--recheck", choices=["mismatch"], help="also check decisions of this outcome")
    p.add_argument(
        "--no-pre2009-skip", action="store_true", help="query Yargıtay decisions up to 2009"
    )
    p.add_argument("--keys", type=Path, help="JSONL of decisions to look up, no database")
    return p


def _adapter(
    court: str, settings: VerifySettings, budget: int | None
) -> tuple[SourceAdapter, httpx.AsyncClient]:
    agent = user_agent(settings.verify_contact or "")
    client = build_client(getattr(settings, PROXY_SETTING[court]), agent)
    limiter = RateLimiter(interval=settings.verify_min_interval_seconds, max_requests=budget)
    return ADAPTERS[court](client, limiter), client


async def _run(args: argparse.Namespace) -> int:
    settings = get_verify_settings()
    courts = [args.court] if args.court else list(ADAPTERS)
    live = os.environ.get("LIVE") == "1"
    engine = None if args.keys else make_engine(get_settings().database_url)
    factory = make_session_factory(engine) if engine else None
    try:
        if args.keys:
            due = read_keys(args.keys)
        else:
            assert factory is not None
            async with factory() as session:
                due = {
                    c: await candidates(
                        session, COURTS[c], datetime.now(UTC), args.recheck == "mismatch"
                    )
                    for c in courts
                }
        if not live:
            for court in courts:
                print(f"{court}: {len(due.get(court, []))} due; LIVE=1 is needed to query")
            return 0
        if not settings.verify_contact:
            raise SystemExit("VERIFY_CONTACT is required for live runs (goes into the User-Agent)")

        budget = request_budget(args.limit, args.dry_run, args.i_have_permission)
        options = RunOptions(
            dry_run=args.dry_run or bool(args.keys),
            skip_pre_2009=not args.no_pre2009_skip,
            cache_dir=settings.verify_cache_dir,
        )
        all_stats: list[SourceStats] = []
        for court in courts:
            if not due.get(court):
                continue
            adapter, client = _adapter(court, settings, budget)
            async with client:
                stats = await run_court(
                    factory,
                    court,
                    adapter,
                    due[court],
                    options,
                    on_result=lambda c, outcome: print(f"{describe(c.key)} -> {outcome}"),
                )
            all_stats.append(stats)
            print(
                f"{court}: {dict(stats.outcomes)} errors {sum(stats.errors.values())} "
                f"requests {stats.requests} stopped {stats.stopped or 'no'}"
            )
        if args.report:
            write_report(build_summary(all_stats, options.dry_run), args.report)
        return 1 if any(s.stopped for s in all_stats) else 0
    finally:
        if engine:
            await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.keys and args.recheck:
        parser.error("--recheck reads the database; it cannot be combined with --keys")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
