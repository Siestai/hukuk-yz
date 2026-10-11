"""The worker's scan loop (task 12a). The database tests are skipped when DATABASE_URL is unset;
the OCR test is skipped without Tesseract and its Turkish model."""

import asyncio
import hashlib
import io
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from filedata import SCAN_PNG, make_pdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import worker
from app.files.store import LocalFileStore
from app.models.common import IngestFile, IngestJob, IngestKind, IngestStatus, ScanStatus
from hukuk_ingest import ocr

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture
def store(tmp_path: Path) -> LocalFileStore:
    return LocalFileStore(tmp_path / "store")


async def enqueue(
    factory: Factory, store: LocalFileStore, data: bytes, *, job_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """A stored, queued upload; returns (file id, job id)."""
    stored = store.put(io.BytesIO(data))
    async with factory() as session:
        if job_id is None:
            job = IngestJob(kind=IngestKind.upload, stats={"files": 1})
            session.add(job)
            await session.flush()
            job_id = job.id
        file = IngestFile(
            job_id=job_id,
            path=stored.key,
            sha256=stored.sha256,
            size=stored.size,
            storage_key=stored.key,
            scan_status=ScanStatus.queued,
        )
        session.add(file)
        await session.commit()
        return file.id, job_id


async def load(factory: Factory, file_id: uuid.UUID) -> IngestFile:
    async with factory() as session:
        return (
            await session.execute(select(IngestFile).where(IngestFile.id == file_id))
        ).scalar_one()


async def test_a_text_pdf_is_scanned_to_done_and_its_text_stored(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, job_id = await enqueue(kb_factory, store, make_pdf())
    assert await worker.scan_next(kb_factory, store) is True
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    result = file.scan_result or {}
    assert result["detected_type"] == "pdf"
    assert result["pages"] == 1
    assert result["text_chars"] > 100
    assert result["ocr_used"] is False
    assert result["text_key"] == f"text/{file.sha256}.txt"
    with store.open(result["text_key"]) as fh:
        text = fh.read()
    assert b"kidem tazminatina" in text
    assert hashlib.sha256(text).hexdigest() == result["text_sha256"]
    assert file.detected_type == "pdf"
    async with kb_factory() as session:
        job = await session.get(IngestJob, job_id)
    assert job is not None
    assert (job.status, job.stats) == (IngestStatus.completed, {"files": 1, "done": 1})
    assert job.finished_at is not None
    assert await worker.scan_next(kb_factory, store) is False


async def test_an_image_is_read_by_ocr_when_tesseract_is_present(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    ocr.default_engine.cache_clear()
    if ocr.default_engine() is None:
        pytest.skip("tesseract with the tur model is not available")
    file_id, _ = await enqueue(kb_factory, store, SCAN_PNG.read_bytes())
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    assert (file.scan_result or {})["ocr_used"] is True
    with store.open((file.scan_result or {})["text_key"]) as fh:
        assert "tazminat" in fh.read().decode()


async def test_an_image_without_tesseract_needs_ocr(
    kb_factory: Factory, store: LocalFileStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUKUK_TESSERACT", "/nonexistent/tesseract")
    ocr.default_engine.cache_clear()
    file_id, _ = await enqueue(kb_factory, store, SCAN_PNG.read_bytes())
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.needs_ocr
    assert "ocr_unavailable" in (file.scan_result or {})["warnings"]
    ocr.default_engine.cache_clear()


async def test_a_corrupt_file_fails_and_the_loop_goes_on(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    bad_id, job_id = await enqueue(kb_factory, store, b"%PDF-1.4\n" + b"\x00garbage" * 50)
    good_id, _ = await enqueue(kb_factory, store, make_pdf(), job_id=job_id)
    stop = asyncio.Event()

    async def stop_when_idle() -> None:
        while True:
            statuses = {(await load(kb_factory, i)).scan_status for i in (bad_id, good_id)}
            if not statuses & {ScanStatus.queued, ScanStatus.running}:
                stop.set()
                return
            await asyncio.sleep(0.05)

    await asyncio.wait_for(
        asyncio.gather(worker.run(stop, kb_factory, store), stop_when_idle()), 60
    )
    bad, good = await load(kb_factory, bad_id), await load(kb_factory, good_id)
    assert bad.scan_status is ScanStatus.failed
    assert (bad.scan_result or {}).get("error")
    assert bad.error == (bad.scan_result or {})["error"]
    assert good.scan_status is ScanStatus.done
    async with kb_factory() as session:
        job = await session.get(IngestJob, job_id)
    assert job is not None
    assert (job.status, job.stats) == (IngestStatus.failed, {"files": 2, "done": 1, "failed": 1})


async def test_a_file_whose_stored_bytes_changed_fails(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    file = await load(kb_factory, file_id)
    assert file.storage_key is not None
    (tmp_path / "store" / file.storage_key).write_bytes(b"%PDF-1.4 other")
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert (file.scan_status, (file.scan_result or {})["error"]) == (
        ScanStatus.failed,
        "sha256_mismatch",
    )


async def test_a_missing_blob_fails_without_stopping(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    file = await load(kb_factory, file_id)
    assert file.storage_key is not None
    (tmp_path / "store" / file.storage_key).unlink()
    await worker.scan_next(kb_factory, store)
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.failed


async def test_a_file_stuck_running_is_queued_again(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    stuck, _ = await enqueue(kb_factory, store, make_pdf("a " * 300))
    fresh, _ = await enqueue(kb_factory, store, make_pdf("b " * 300))
    legacy, _ = await enqueue(kb_factory, store, make_pdf("c " * 300))
    old = datetime.now(UTC) - worker.STUCK_AFTER - timedelta(minutes=1)
    async with kb_factory() as session:
        for file_id, started in (
            (stuck, old),
            (fresh, datetime.now(UTC)),
            (legacy, None),
        ):
            file = await session.get(IngestFile, file_id)
            assert file is not None
            file.scan_status = ScanStatus.running
            file.scan_result = {"started_at": started.isoformat()} if started else None
        await session.commit()
    assert await worker.requeue_stuck(kb_factory) == 2
    assert (await load(kb_factory, stuck)).scan_status is ScanStatus.queued
    assert (await load(kb_factory, legacy)).scan_status is ScanStatus.queued
    assert (await load(kb_factory, fresh)).scan_status is ScanStatus.running


async def test_two_claimers_never_take_the_same_file(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    ids = {(await enqueue(kb_factory, store, make_pdf(f"{n} " * 300)))[0] for n in range(6)}
    claims = await asyncio.gather(*(worker.claim(kb_factory) for _ in range(6)))
    taken = [c.id for c in claims if c is not None]
    assert len(taken) == len(set(taken)) == 6
    assert set(taken) == ids
    assert await worker.claim(kb_factory) is None
    for file_id in ids:
        assert (await load(kb_factory, file_id)).scan_status is ScanStatus.running


async def test_an_outcome_is_dropped_when_the_file_was_queued_again_meanwhile(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    claimed = await worker.claim(kb_factory)
    assert claimed is not None
    async with kb_factory() as session:
        file = await session.get(IngestFile, file_id)
        assert file is not None
        file.scan_status = ScanStatus.queued
        await session.commit()
    await worker.finish(kb_factory, claimed, await asyncio.to_thread(worker.scan, store, claimed))
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.queued


async def test_a_rescan_scans_again(kb_factory: Factory, store: LocalFileStore) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    await worker.scan_next(kb_factory, store)
    async with kb_factory() as session:
        file = await session.get(IngestFile, file_id)
        assert file is not None
        file.scan_status = ScanStatus.queued
        await session.commit()
    assert await worker.scan_next(kb_factory, store) is True
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.done


async def test_the_loop_stops_on_the_event_and_without_a_store_only_beats(
    kb_factory: Factory, store: LocalFileStore, caplog: pytest.LogCaptureFixture
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    stop = asyncio.Event()
    caplog.set_level("INFO", logger="app.worker")
    asyncio.get_running_loop().call_later(0.2, stop.set)
    await asyncio.wait_for(worker.run(stop, kb_factory, None), 5)
    assert "worker heartbeat" in caplog.text
    assert "worker stopped" in caplog.text
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.queued
