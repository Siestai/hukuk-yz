"""Journal scans for the demo database (SYNTHETIC; see README.md).

Run inside the `app` container after the decisions are loaded (`make demo-data` does):
`python /demo/journal_scans.py`. It writes two `journal_scan` rows (a finished one with one
error row per kind of reason, and a failed one), and turns two of the loaded demo decisions into
records of the first scan: their file moves to its `crawl` job with an address and the journal
block, exactly what `python -m app.journal.scan` writes. No network, no real journal data.
The two rows have fixed ids, so running it again does nothing, and scans that are really there do
not stop it. The loader's job keeps its load summary (a record of the load, which no screen
counts); only the two files change jobs. Everything is one transaction."""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db import make_engine, make_session_factory
from app.models.common import IngestFile, IngestJob, IngestKind, IngestStatus
from app.models.journal import JournalScan
from app.settings import get_settings

# Records of the demo set that no e2e spec approves or rejects (the scan's records must stay in
# the queue for the screens to show them) and that are not in the high band (bulk approval skips
# a scan's records, which would break its count).
SCANNED = ("Demo 09 ", "Demo 10 ")
RAN_ID = uuid.UUID("5ca00000-0000-4000-8000-000000000091")
FAILED_ID = uuid.UUID("5ca00000-0000-4000-8000-000000000090")
SITE = "https://journal.example.test"
RAN = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)  # a Saturday 11:00 in Istanbul
FAILED = datetime(2026, 11, 7, 8, 0, tzinfo=UTC)

REPORT = {
    "issues": [
        {
            "issue_no": 91,
            "site_count": 5,
            "pdf_links": 4,
            "downloaded": 3,
            "duplicates": 1,
            "queued": len(SCANNED),
            "duplicate_candidates": 1,
            "errors": [
                {"url": f"{SITE}/karar-4/", "reason": "pdf_link_missing"},
                {"url": f"{SITE}/karar-5/", "reason": "http_503"},
            ],
        }
    ],
    "failure": None,
    "archive_max": 90,
    "warnings": [],
}


async def main() -> int:
    engine = make_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        async with factory() as db:
            if await db.get(JournalScan, RAN_ID) is not None:
                print("journal scans are already there")
                return 0
            jobs = [
                IngestJob(
                    kind=IngestKind.crawl,
                    status=status,
                    started_at=started,
                    finished_at=started.replace(minute=12),
                )
                for started, status in (
                    (RAN, IngestStatus.completed),
                    (FAILED, IngestStatus.failed),
                )
            ]
            db.add_all(jobs)
            await db.flush()
            ran, failed = jobs
            db.add_all(
                [
                    JournalScan(
                        id=RAN_ID,
                        job_id=ran.id,
                        trigger="schedule",
                        started_at=RAN,
                        finished_at=RAN.replace(minute=12),
                        status="completed_with_errors",
                        new_issues=[91],
                        discovered=5,
                        downloaded=3,
                        duplicates=1,
                        queued=len(SCANNED),
                        errors=2,
                        report=REPORT,
                    ),
                    JournalScan(
                        id=FAILED_ID,
                        job_id=failed.id,
                        trigger="manual",
                        started_at=FAILED,
                        finished_at=FAILED.replace(minute=1),
                        status="failed",
                        report={
                            "issues": [],
                            "failure": f"{SITE}/wp-json/wp/v2/categories: http_503",
                            "warnings": [],
                        },
                    ),
                ]
            )
            for number, prefix in enumerate(SCANNED, start=1):
                path = f"%/{prefix}%"
                file_id = (
                    await db.execute(
                        select(IngestFile.id).where(IngestFile.path.like(path)).limit(1)
                    )
                ).scalar_one_or_none()
                if file_id is None:
                    print(f"no demo file named {prefix.strip()}: load the demo decisions first")
                    return 1
                await db.execute(
                    update(IngestFile)
                    .where(IngestFile.id == file_id)
                    .values(
                        job_id=ran.id,
                        origin_url=f"{SITE}/pdf/{number}.pdf",
                        uploaded_at=RAN.replace(minute=2 + number),
                        scan_result={
                            "journal": {
                                "issue_no": 91,
                                "post_id": number,
                                "page_url": f"{SITE}/karar-{number}/",
                                "pdf_url": f"{SITE}/pdf/{number}.pdf",
                            }
                        },
                    )
                )
            await db.commit()
    finally:
        await engine.dispose()
    print("two journal scans written")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
