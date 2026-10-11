"""The worker: scans the files that were uploaded (task 12a).

It claims one `queued` file at a time (`FOR UPDATE SKIP LOCKED`, so two workers never take the
same row), detects its type, extracts the text and, where Tesseract is installed, runs OCR, all
through `hukuk_ingest.pipeline.process_file`. The text goes to the file store; the outcome goes
to `ingest_file.scan_status` / `scan_result` and the file's `ingest_job`. A file that cannot be
scanned is marked `failed` with the error and the loop goes on. Files left `running` for more
than `STUCK_AFTER` (a crashed worker) are queued again.

Concurrency is 1: the server is shared.
"""

import asyncio
import hashlib
import logging
import signal
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.files.store import CHUNK_BYTES, FileStore, LocalFileStore
from app.logging_setup import configure_logging
from app.models.common import IngestFile, IngestJob, IngestStatus, ScanStatus
from app.settings import get_settings
from hukuk_ingest.pipeline import process_file

logger = logging.getLogger("app.worker")

HEARTBEAT_SECONDS = 30
POLL_SECONDS = 5
STUCK_AFTER = timedelta(minutes=15)

Factory = async_sessionmaker[AsyncSession]

# `process_file` statuses -> scan status; anything else is a failure.
_SCAN_STATUS = {
    "ok": ScanStatus.done,
    "needs_ocr": ScanStatus.needs_ocr,
    "unsupported": ScanStatus.unsupported,
    "rejected": ScanStatus.unsupported,
    "skipped": ScanStatus.unsupported,
}


@dataclass(frozen=True)
class Claimed:
    id: uuid.UUID
    storage_key: str
    sha256: str


@dataclass(frozen=True)
class Scanned:
    status: ScanStatus
    result: dict[str, Any]
    detected_type: str | None = None
    error: str | None = None


async def requeue_stuck(factory: Factory) -> int:
    """Queue again the files that have been `running` for more than `STUCK_AFTER`."""
    started = IngestFile.scan_result["started_at"].astext.cast(DateTime(timezone=True))
    async with factory() as db:
        ids = (
            await db.execute(
                update(IngestFile)
                .where(
                    IngestFile.scan_status == ScanStatus.running,
                    or_(started.is_(None), started < datetime.now(UTC) - STUCK_AFTER),
                )
                .values(scan_status=ScanStatus.queued)
                .returning(IngestFile.id)
            )
        ).all()
        await db.commit()
    for (file_id,) in ids:
        logger.warning("file %s was running too long; queued again", file_id)
    return len(ids)


async def claim(factory: Factory) -> Claimed | None:
    """Take the oldest queued file: mark it and its job `running`."""
    async with factory() as db:
        file = (
            await db.execute(
                select(IngestFile)
                .where(
                    IngestFile.scan_status == ScanStatus.queued,
                    IngestFile.storage_key.is_not(None),
                )
                .order_by(IngestFile.uploaded_at, IngestFile.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if file is None:
            return None
        assert file.storage_key is not None  # selected as not null
        now = datetime.now(UTC)
        file.scan_status = ScanStatus.running
        file.scan_result = {"started_at": now.isoformat()}
        job = await db.get(IngestJob, file.job_id)
        assert job is not None  # job_id is a foreign key
        job.status = IngestStatus.running
        job.started_at = job.started_at or now
        job.finished_at = None
        await db.commit()
        return Claimed(file.id, file.storage_key, file.sha256)


def scan(store: FileStore, claimed: Claimed) -> Scanned:
    """Detect, extract and (with Tesseract) OCR one stored file. Runs in a thread; a failure of
    any kind is the outcome `failed`, not an exception."""
    try:
        with tempfile.TemporaryDirectory(prefix="scan-") as tmp:
            root = Path(tmp)
            blob = root / "file"
            digest = hashlib.sha256()
            with store.open(claimed.storage_key) as source, blob.open("wb") as out:
                while chunk := source.read(CHUNK_BYTES):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != claimed.sha256:
                return _failed("sha256_mismatch")
            result = process_file(blob, root, root / "cache")
            scan_result: dict[str, Any] = {
                "detected_type": result.detected_type,
                "pages": result.pages,
                "text_chars": result.chars,
                "ocr_used": "ocr" in result.warnings,
                "warnings": result.warnings,
                "reason": result.reason,
                "extractor": result.extractor,
            }
            if result.text_ref:
                text = (root / "cache" / result.text_ref).read_bytes().decode("utf-8")
                scan_result["text_key"] = store.put_text(claimed.sha256, text)
                scan_result["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            status = _SCAN_STATUS.get(result.status, ScanStatus.failed)
            if status is ScanStatus.failed:
                scan_result["error"] = result.error or result.reason
            return Scanned(status, scan_result, result.detected_type, scan_result.get("error"))
    except Exception as exc:
        logger.exception("scanning file %s failed", claimed.id)
        return _failed(f"{type(exc).__name__}: {exc}")


def _failed(error: str) -> Scanned:
    return Scanned(ScanStatus.failed, {"error": error}, error=error)


async def finish(factory: Factory, claimed: Claimed, scanned: Scanned) -> None:
    """Write the outcome to the file and refresh the job's status and counts. A file queued
    again meanwhile (the scan outlived `STUCK_AFTER`) keeps its place: the outcome is dropped."""
    async with factory() as db:
        file = (
            await db.execute(
                select(IngestFile).where(IngestFile.id == claimed.id).with_for_update()
            )
        ).scalar_one()
        if file.scan_status is not ScanStatus.running:
            logger.warning("file %s is no longer running; its scan outcome is dropped", file.id)
            return
        now = datetime.now(UTC)
        file.scan_status = scanned.status
        file.scan_result = {**scanned.result, "scanned_at": now.isoformat()}
        file.detected_type = scanned.detected_type or file.detected_type
        file.error = scanned.error
        await db.flush()
        counts = dict(
            (
                await db.execute(
                    select(IngestFile.scan_status, func.count())
                    .where(IngestFile.job_id == file.job_id)
                    .group_by(IngestFile.scan_status)
                )
            ).all()
        )
        job = await db.get(IngestJob, file.job_id)
        assert job is not None  # job_id is a foreign key
        job.stats = {"files": sum(counts.values()), **{s.value: n for s, n in counts.items()}}
        if counts.get(ScanStatus.queued) or counts.get(ScanStatus.running):
            job.status = IngestStatus.running
        else:
            job.status = (
                IngestStatus.failed if counts.get(ScanStatus.failed) else IngestStatus.completed
            )
            job.finished_at = now
        await db.commit()


async def scan_next(factory: Factory, store: FileStore) -> bool:
    """Scan the oldest queued file; False when there is none."""
    claimed = await claim(factory)
    if claimed is None:
        return False
    scanned = await asyncio.to_thread(scan, store, claimed)
    await finish(factory, claimed, scanned)
    logger.info("file %s scanned: %s", claimed.id, scanned.status.value)
    return True


async def run(stop: asyncio.Event, factory: Factory, store: FileStore | None) -> None:
    """Scan until `stop` is set, logging a heartbeat every `HEARTBEAT_SECONDS`. Without a store
    (`FILE_STORE_ROOT` unset) there is nothing to scan: only the heartbeat runs."""
    if store is None:
        logger.warning("FILE_STORE_ROOT is not set: uploaded files are not scanned")
    loop = asyncio.get_running_loop()
    next_heartbeat = loop.time()
    while not stop.is_set():
        if loop.time() >= next_heartbeat:
            logger.info("worker heartbeat")
            next_heartbeat = loop.time() + HEARTBEAT_SECONDS
        scanned_one = False
        if store is not None:
            try:
                await requeue_stuck(factory)
                scanned_one = await scan_next(factory, store)
            except Exception:
                logger.exception("scan loop error")
        if not scanned_one:
            wait = min(POLL_SECONDS if store else HEARTBEAT_SECONDS, next_heartbeat - loop.time())
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(wait, 0))
            except TimeoutError:
                pass
    logger.info("worker stopped")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    store = LocalFileStore(settings.file_store_root) if settings.file_store_root else None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run(stop, make_session_factory(engine), store)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
