"""The weekly scan of the journal Çalışma ve Toplum (task 20).

    python -m app.journal.scan [--dry-run] [--issue N]

Finds the issues of the site that are newer than the newest one in the archive, downloads their
decision PDFs and puts them into the decision review queue (`app.journal.enqueue`). One run is
one `ingest_job` (kind `crawl`, no user) and one `journal_scan` row with the counters and the
report. Nothing is approved or published.

Safe to repeat: a decision page already downloaded (same post) and a file already stored (same
sha256) are counted as duplicates and not written again, so an interrupted run goes on where it
stopped and a second run of an issue adds nothing. Two runs never overlap (a Postgres advisory
lock); the second one returns `skipped` at once. `--dry-run` writes nothing: it lists the issues,
the decision pages and the PDF addresses it would fetch. `--issue N` scans that issue only,
whether it is new or not (rescue by hand); every duplicate rule still applies.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.files.store import FileStore, LocalFileStore
from app.journal.client import Fetcher, FetchError, PoliteClient
from app.journal.discover import (
    BASE_URL,
    DiscoveryError,
    Issue,
    find_pdf_link,
    list_issues,
    list_posts,
    new_issue_numbers,
)
from app.journal.download import download_pdf
from app.journal.enqueue import JournalPost, enqueue, known_post_ids
from app.loaders.decisions import error_name
from app.logging_setup import configure_logging
from app.models.common import PARSER_NAME, Extraction, IngestJob, IngestKind, IngestStatus
from app.models.journal import JournalScan
from app.settings import get_settings
from hukuk_models.journal import JournalError, JournalIssueReport, JournalReport

logger = logging.getLogger("app.journal")

# Postgres advisory lock key of "a scan is running".
LOCK_KEY = 0x6A6F75726E616C
Status = Literal["skipped", "dry_run", "running", "completed", "completed_with_errors", "failed"]
Factory = async_sessionmaker[AsyncSession]


@dataclass
class Totals:
    discovered: int = 0
    downloaded: int = 0
    duplicates: int = 0
    queued: int = 0
    errors: int = 0


@dataclass
class Outcome:
    status: Status
    scan_id: uuid.UUID | None = None
    new_issues: list[int] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    report: JournalReport = field(default_factory=JournalReport)


async def archive_max_issue(db: AsyncSession) -> int | None:
    """The newest journal issue that has a decision in the review pipeline."""
    return (
        await db.execute(
            select(func.max(Extraction.journal_issue)).where(Extraction.parser_name == PARSER_NAME)
        )
    ).scalar_one()


async def _close_interrupted(db: AsyncSession) -> None:
    """Mark the runs left `running` by a crash as failed (the lock is ours, so none is alive)."""
    now = datetime.now(UTC)
    stale = (
        (await db.execute(select(JournalScan).where(JournalScan.status == "running")))
        .scalars()
        .all()
    )
    for scan in stale:
        scan.status = "failed"
        scan.finished_at = now
        scan.report = {**scan.report, "failure": "interrupted"}
        await db.execute(
            update(IngestJob)
            .where(IngestJob.id == scan.job_id)
            .values(status=IngestStatus.failed, finished_at=now)
        )
    await db.flush()


async def _carried(db: AsyncSession) -> list[int]:
    """The issues the latest run, when it failed, still had to do: the next run does them."""
    latest = (
        await db.execute(select(JournalScan).order_by(JournalScan.started_at.desc()).limit(1))
    ).scalar_one_or_none()
    return list(latest.new_issues) if latest is not None and latest.status == "failed" else []


@dataclass
class _Run:
    factory: Factory
    store: FileStore | None
    fetcher: Fetcher
    base_url: str
    max_bytes: int
    scan_id: uuid.UUID | None
    job_id: uuid.UUID | None
    totals: Totals
    report: JournalReport

    @property
    def dry_run(self) -> bool:
        return self.scan_id is None


async def _save(run: _Run, db: AsyncSession) -> None:
    """The counters and the report of the run, in the transaction of the last decision."""
    if run.scan_id is None:
        return
    await db.execute(
        update(JournalScan)
        .where(JournalScan.id == run.scan_id)
        .values(**vars(run.totals), report=run.report.model_dump(mode="json"))
    )
    await db.commit()


async def _scan_post(
    run: _Run, db: AsyncSession, issue_no: int, post_id: int, link: str, summary: JournalIssueReport
) -> None:
    page = await run.fetcher.get(link)
    pdf_url = find_pdf_link(page.text, link)
    if pdf_url is None:
        raise FetchError(link, "pdf_link_missing")
    summary.pdf_links += 1
    if run.dry_run:
        return
    content = await download_pdf(run.fetcher, pdf_url, run.max_bytes)
    assert run.store is not None and run.job_id is not None  # not a dry run
    candidate = await enqueue(
        db, run.store, run.job_id, content, JournalPost(issue_no, post_id, link, pdf_url)
    )
    if candidate is None:
        summary.duplicates += 1
        run.totals.duplicates += 1
        return
    summary.downloaded += 1
    summary.queued += 1
    summary.duplicate_candidates += candidate
    run.totals.downloaded += 1
    run.totals.queued += 1


async def _scan_issue(run: _Run, issue: Issue) -> None:
    posts = await list_posts(run.fetcher, issue, run.base_url)
    summary = JournalIssueReport(
        issue_no=issue.no,
        site_count=len(posts),
        pdf_links=0,
        downloaded=0,
        duplicates=0,
        queued=0,
        duplicate_candidates=0,
        errors=[],
    )
    run.report.issues.append(summary)
    run.totals.discovered += len(posts)
    async with run.factory() as db:
        known = await known_post_ids(db, issue.no)
        await _save(run, db)
        for post in posts:
            if post.id in known:
                summary.duplicates += 1
                run.totals.duplicates += 1
                await _save(run, db)
                continue
            try:
                await _scan_post(run, db, issue.no, post.id, post.link, summary)
            except FetchError as exc:
                await db.rollback()
                error = JournalError(url=exc.url, reason=exc.reason)
            except DBAPIError as exc:
                await db.rollback()
                error = JournalError(url=post.link, reason=f"db_error:{error_name(exc)}")
            except Exception as exc:  # one bad decision must not stop the scan
                logger.exception("decision page %s failed", post.link)
                await db.rollback()
                error = JournalError(url=post.link, reason=f"error:{type(exc).__name__}")
            else:
                await _save(run, db)
                continue
            summary.errors.append(error)
            run.totals.errors += 1
            logger.warning("%s: %s", error.url, error.reason)
            await _save(run, db)


async def _targets(
    fetcher: Fetcher,
    base_url: str,
    db: AsyncSession,
    only_issue: int | None,
    carried: list[int],
) -> list[Issue]:
    issues = await list_issues(fetcher, base_url)
    if only_issue is not None:
        if only_issue not in issues:
            raise DiscoveryError(f"issue_not_found:{only_issue}")
        return [issues[only_issue]]
    archive_max = await archive_max_issue(db)
    if archive_max is None:
        # An empty archive would make every issue "new"; the scan is for the weekly top-up.
        raise DiscoveryError("archive_empty")
    wanted = set(new_issue_numbers(issues, archive_max)) | set(carried)
    return [issues[no] for no in sorted(wanted) if no in issues]


async def _acquire(db: AsyncSession) -> bool:
    connection = await db.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
    return bool(
        (await connection.execute(select(func.pg_try_advisory_lock(LOCK_KEY)))).scalar_one()
    )


async def scan(
    factory: Factory,
    store: FileStore | None,
    fetcher: Fetcher,
    *,
    only_issue: int | None = None,
    dry_run: bool = False,
    base_url: str = BASE_URL,
    max_bytes: int = 50 * 1024 * 1024,
) -> Outcome:
    """One scan. `store` may be None only for a dry run."""
    if dry_run:
        return await _dry_run(factory, fetcher, only_issue, base_url, max_bytes)
    assert store is not None
    async with factory() as lock:
        if not await _acquire(lock):
            return Outcome("skipped")
        try:
            return await _locked_scan(factory, store, fetcher, only_issue, base_url, max_bytes)
        finally:
            await lock.execute(select(func.pg_advisory_unlock(LOCK_KEY)))


async def _dry_run(
    factory: Factory, fetcher: Fetcher, only_issue: int | None, base_url: str, max_bytes: int
) -> Outcome:
    outcome = Outcome("dry_run")
    run = _Run(
        factory, None, fetcher, base_url, max_bytes, None, None, outcome.totals, outcome.report
    )
    try:
        async with factory() as db:
            carried = [] if only_issue is not None else await _carried(db)
            targets = await _targets(fetcher, base_url, db, only_issue, carried)
        outcome.new_issues = [issue.no for issue in targets]
        for issue in targets:
            await _scan_issue(run, issue)
    except DiscoveryError as exc:
        outcome.status = "failed"
        outcome.report.failure = str(exc)
    return outcome


async def _locked_scan(
    factory: Factory,
    store: FileStore,
    fetcher: Fetcher,
    only_issue: int | None,
    base_url: str,
    max_bytes: int,
) -> Outcome:
    started = datetime.now(UTC)
    async with factory() as db:
        await _close_interrupted(db)
        carried = [] if only_issue is not None else await _carried(db)
        job = IngestJob(kind=IngestKind.crawl, status=IngestStatus.running, started_at=started)
        db.add(job)
        await db.flush()
        row = JournalScan(
            job_id=job.id,
            trigger="manual" if only_issue is not None else "schedule",
            started_at=started,
            status="running",
        )
        db.add(row)
        await db.commit()
        job_id, scan_id = job.id, row.id
    outcome = Outcome("running", scan_id)
    run = _Run(
        factory,
        store,
        fetcher,
        base_url,
        max_bytes,
        scan_id,
        job_id,
        outcome.totals,
        outcome.report,
    )
    try:
        async with factory() as db:
            targets = await _targets(fetcher, base_url, db, only_issue, carried)
            outcome.new_issues = [issue.no for issue in targets]
            await db.execute(
                update(JournalScan)
                .where(JournalScan.id == scan_id)
                .values(new_issues=outcome.new_issues)
            )
            await db.commit()
        for issue in targets:
            await _scan_issue(run, issue)
        outcome.status = "completed_with_errors" if outcome.totals.errors else "completed"
    except DiscoveryError as exc:
        outcome.status = "failed"
        outcome.report.failure = str(exc)
        logger.error("journal scan failed: %s", exc)
    async with factory() as db:
        await db.execute(
            update(JournalScan)
            .where(JournalScan.id == scan_id)
            .values(
                status=outcome.status,
                finished_at=datetime.now(UTC),
                report=outcome.report.model_dump(mode="json"),
                **vars(outcome.totals),
            )
        )
        await db.execute(
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(
                status=IngestStatus.failed
                if outcome.status == "failed"
                else IngestStatus.completed,
                finished_at=datetime.now(UTC),
            )
        )
        await db.commit()
    return outcome


def describe(outcome: Outcome) -> str:
    """The run as text for the console."""
    lines = [f"status: {outcome.status}", f"issues: {outcome.new_issues}"]
    if outcome.report.failure:
        lines.append(f"failure: {outcome.report.failure}")
    for issue in outcome.report.issues:
        lines.append(
            f"issue {issue.issue_no}: {issue.site_count} decisions on the site, "
            f"{issue.pdf_links} PDF links, downloaded {issue.downloaded}, "
            f"duplicates {issue.duplicates}, queued {issue.queued} "
            f"(duplicate candidates {issue.duplicate_candidates}), errors {len(issue.errors)}"
        )
        lines += [f"  error: {e.url}: {e.reason}" for e in issue.errors]
    t = outcome.totals
    lines.append(
        f"discovered {t.discovered}, downloaded {t.downloaded}, duplicates {t.duplicates}, "
        f"queued {t.queued}, errors {t.errors}"
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.journal.scan", description=__doc__)
    p.add_argument(
        "--dry-run", action="store_true", help="write nothing: report what would be done"
    )
    p.add_argument("--issue", type=int, help="scan this issue only, new or not")
    return p


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request is noise
    if not args.dry_run and settings.file_store_root is None:
        print("FILE_STORE_ROOT is not set: nothing to store the PDFs in", file=sys.stderr)
        return 2
    store = LocalFileStore(settings.file_store_root) if settings.file_store_root else None
    engine = make_engine(settings.database_url)
    try:
        async with PoliteClient(settings.journal_scan_delay_seconds) as client:
            outcome = await scan(
                make_session_factory(engine),
                store,
                client,
                only_issue=args.issue,
                dry_run=args.dry_run,
                max_bytes=settings.file_max_bytes,
            )
    finally:
        await engine.dispose()
    print(describe(outcome))
    return 1 if outcome.status == "failed" else 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_run(_parser().parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
