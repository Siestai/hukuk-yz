"""The worker's scan loop (task 12a). The database tests are skipped when DATABASE_URL is unset;
the OCR test is skipped without Tesseract and its Turkish model."""

import asyncio
import hashlib
import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import worker
from app.files.store import LocalFileStore
from app.models.common import (
    DocumentType,
    Extraction,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    ReviewStatus,
    ScanStatus,
)
from hukuk_ingest import ocr
from hukuk_ingest.classify.llm import DetectorError, DetectRequest, DetectResult

Factory = async_sessionmaker[AsyncSession]


@pytest.fixture
def store(tmp_path: Path) -> LocalFileStore:
    return LocalFileStore(tmp_path / "store")


async def enqueue(
    factory: Factory,
    store: LocalFileStore,
    data: bytes,
    *,
    job_id: uuid.UUID | None = None,
    **fields: Any,
) -> tuple[uuid.UUID, uuid.UUID]:
    """A stored, queued upload; returns (file id, job id). `fields` are columns of the row."""
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
            **fields,
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
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
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
    kb_factory: Factory, store: LocalFileStore, scan_png: bytes
) -> None:
    ocr.default_engine.cache_clear()
    if ocr.default_engine() is None:
        pytest.skip("tesseract with the tur model is not available")
    file_id, _ = await enqueue(kb_factory, store, scan_png)
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    assert (file.scan_result or {})["ocr_used"] is True
    with store.open((file.scan_result or {})["text_key"]) as fh:
        assert "tazminat" in fh.read().decode()


async def test_an_image_without_tesseract_needs_ocr(
    kb_factory: Factory, store: LocalFileStore, monkeypatch: pytest.MonkeyPatch, scan_png: bytes
) -> None:
    monkeypatch.setenv("HUKUK_TESSERACT", "/nonexistent/tesseract")
    ocr.default_engine.cache_clear()
    file_id, _ = await enqueue(kb_factory, store, scan_png)
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.needs_ocr
    assert "ocr_unavailable" in (file.scan_result or {})["warnings"]
    ocr.default_engine.cache_clear()


async def test_a_corrupt_file_fails_and_the_loop_goes_on(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
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
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path, make_pdf: Callable[..., bytes]
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
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path, make_pdf: Callable[..., bytes]
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    file = await load(kb_factory, file_id)
    assert file.storage_key is not None
    (tmp_path / "store" / file.storage_key).unlink()
    await worker.scan_next(kb_factory, store)
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.failed


async def test_a_file_stuck_running_is_queued_again(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
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


async def test_a_file_stuck_too_often_is_marked_failed(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
) -> None:
    file_id, job_id = await enqueue(kb_factory, store, make_pdf())
    for attempt in range(1, worker.MAX_ATTEMPTS + 1):
        claimed = await worker.claim(kb_factory)
        assert claimed is not None
        assert (await load(kb_factory, file_id)).scan_result["attempts"] == attempt  # type: ignore[index]
        async with kb_factory() as session:
            file = await session.get(IngestFile, file_id)
            assert file is not None
            old = datetime.now(UTC) - worker.STUCK_AFTER - timedelta(minutes=1)
            file.scan_result = {**(file.scan_result or {}), "started_at": old.isoformat()}
            await session.commit()
        assert await worker.requeue_stuck(kb_factory) == 1
        expected = ScanStatus.queued if attempt < worker.MAX_ATTEMPTS else ScanStatus.failed
        assert (await load(kb_factory, file_id)).scan_status is expected
    failed = await load(kb_factory, file_id)
    assert (failed.error, (failed.scan_result or {})["error"]) == ("stuck", "stuck")
    assert await worker.claim(kb_factory) is None
    async with kb_factory() as session:
        job = await session.get(IngestJob, job_id)
        assert job is not None
        assert (job.status, job.stats["failed"]) == (IngestStatus.failed, 1)


async def test_two_claimers_never_take_the_same_file(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
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
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    claimed = await worker.claim(kb_factory)
    assert claimed is not None
    async with kb_factory() as session:
        file = await session.get(IngestFile, file_id)
        assert file is not None
        file.scan_status = ScanStatus.queued
        await session.commit()
    await worker.finish(
        kb_factory, store, claimed, await asyncio.to_thread(worker.scan, store, claimed)
    )
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.queued


async def test_an_outcome_of_an_earlier_claim_is_dropped_when_the_file_runs_again(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    first = await worker.claim(kb_factory)
    assert first is not None
    async with kb_factory() as session:  # requeued, then claimed again by another attempt
        file = await session.get(IngestFile, file_id)
        assert file is not None
        file.scan_status = ScanStatus.queued
        await session.commit()
    second = await worker.claim(kb_factory)
    assert second is not None and second.token != first.token
    await worker.finish(
        kb_factory, store, first, await asyncio.to_thread(worker.scan, store, first)
    )
    running = await load(kb_factory, file_id)
    assert running.scan_status is ScanStatus.running
    assert (running.scan_result or {})["claim"] == second.token
    await worker.finish(
        kb_factory, store, second, await asyncio.to_thread(worker.scan, store, second)
    )
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.done


async def test_a_rescan_scans_again(
    kb_factory: Factory, store: LocalFileStore, make_pdf: Callable[..., bytes]
) -> None:
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
    kb_factory: Factory,
    store: LocalFileStore,
    caplog: pytest.LogCaptureFixture,
    make_pdf: Callable[..., bytes],
) -> None:
    file_id, _ = await enqueue(kb_factory, store, make_pdf())
    stop = asyncio.Event()
    caplog.set_level("INFO", logger="app.worker")
    asyncio.get_running_loop().call_later(0.2, stop.set)
    await asyncio.wait_for(worker.run(stop, kb_factory, None), 5)
    assert "worker heartbeat" in caplog.text
    assert "worker stopped" in caplog.text
    assert (await load(kb_factory, file_id)).scan_status is ScanStatus.queued


# --- detection and matching (task 13a) -----------------------------------------------------------

GENELGE = """T.C.
SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI
Sayı : E-69053920-010.06.01-24043199 16.04.2021
Konu : Yapı Ruhsatı Başvurularında Tescil İşlemleri
GENELGE
2021/11
Bilindiği üzere, yapı ruhsatı başvurularında sigortalıların tescili yapılır.
"""
UNCLEAR = (
    "Başlıksız belge\nSayfa 1\n15 Mart 2021 tarihinde toplanan kurul, 2021/7 sayılı kararı aldı.\n"
)
DECISION_BODY = " ".join(
    f"{n}. maddeye göre davacı işçi {n} numaralı işyerinde çalışmaya devam etmiştir"
    for n in range(80)
)


def decision(body: str = DECISION_BODY, extra: str = "") -> bytes:
    return (
        "T.C\nYARGITAY\n9. HUKUK DAİRESİ\nEsas No. 2021/5329\nKarar No. 2021/9588\n"
        f"Tarihi: 26.05.2021\n{extra}ÖZETİ: Özet metni.\nDAVA: {body}\n"
    ).encode()


class FakeDetector:
    def __init__(self, answer: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.answer = answer or {}
        self.fail = fail
        self.requests: list[DetectRequest] = []

    def detect(self, request: DetectRequest) -> DetectResult:
        self.requests.append(request)
        if self.fail:
            raise DetectorError("HTTP 429")
        return DetectResult(self.answer, "fake", 10, 5)


async def test_a_scan_writes_suggestions_and_leaves_the_fields_of_the_file_alone(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, _ = await enqueue(
        kb_factory, store, GENELGE.encode(), review_status=ReviewStatus.pending
    )
    detector = FakeDetector()
    await worker.scan_next(kb_factory, store, detector)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    suggestions = file.suggestions or {}
    assert suggestions["doc_type"]["value"] == "genelge"
    assert suggestions["doc_type"]["source"] == "rule"
    assert suggestions["official_ref"]["value"] == "2021/11"
    assert suggestions["doc_date"] == {
        "value": "2021-04-16",
        "source": "rule",
        "evidence": {"page": 1, "quote": "16.04.2021"},
    }
    assert (file.doc_type, file.doc_date, file.official_ref, file.title) == (None,) * 4
    assert (file.review_status, file.approved_by) == (ReviewStatus.pending, None)
    assert file.matches == {"previous_version": None, "similar": []}
    assert detector.requests == []  # the rules found every field the model could add


async def test_without_a_detector_the_scan_is_done_and_the_fields_stay_empty(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, _ = await enqueue(kb_factory, store, UNCLEAR.encode())
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    assert file.suggestions == {}
    assert (file.scan_result or {})["warnings"] == []


async def test_the_model_fills_what_the_rules_left_and_its_invented_quotes_are_dropped(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, _ = await enqueue(kb_factory, store, UNCLEAR.encode(), original_name="kurul.txt")
    detector = FakeDetector(
        {
            "doc_date": {"value": "2021-03-15", "quote": "15 Mart 2021"},
            "official_ref": {"value": "2099/1", "quote": "2099/1 sayılı"},
        }
    )
    await worker.scan_next(kb_factory, store, detector)
    suggestions = (await load(kb_factory, file_id)).suggestions or {}
    assert suggestions["doc_date"]["source"] == "llm"
    assert suggestions["doc_date"]["evidence"]["quote"] == "15 Mart 2021"
    assert "official_ref" not in suggestions
    assert detector.requests[0].file_name == "kurul.txt"
    assert detector.requests[0].text.startswith("Başlıksız belge")


async def test_a_failing_model_leaves_a_warning_and_the_scan_stays_done(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    file_id, _ = await enqueue(kb_factory, store, UNCLEAR.encode())
    await worker.scan_next(kb_factory, store, FakeDetector(fail=True))
    file = await load(kb_factory, file_id)
    assert file.scan_status is ScanStatus.done
    assert (file.scan_result or {})["warnings"] == ["detector_failed"]
    assert file.suggestions == {}


async def test_what_the_user_typed_survives_the_detection_and_a_rescan_detects_again(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    typed = {"doc_type": {"value": "kanun", "source": "user", "evidence": None}}
    file_id, _ = await enqueue(
        kb_factory, store, GENELGE.encode(), doc_type=DocumentType.kanun, suggestions=typed
    )
    await worker.scan_next(kb_factory, store)
    first = (await load(kb_factory, file_id)).suggestions or {}
    # shown as typed, with what the text says beside it
    assert first["doc_type"]["value"] == "kanun"
    assert first["doc_type"]["source"] == "user"
    assert first["doc_type"]["detected"]["value"] == "genelge"
    assert first["doc_type"]["detected"]["source"] == "rule"
    assert first["official_ref"]["value"] == "2021/11"
    stale = {"value": "eski", "source": "rule", "evidence": None}
    async with kb_factory() as session:  # what a rescan does: the file is queued again
        file = await session.get(IngestFile, file_id)
        assert file is not None
        file.scan_status, file.suggestions = ScanStatus.queued, {**first, "title": stale}
        await session.commit()
    await worker.scan_next(kb_factory, store)
    again = (await load(kb_factory, file_id)).suggestions or {}
    assert again == first  # detected again: the stale title is gone, the user's type stays


async def test_the_previous_version_is_found_by_the_reference_and_by_the_name(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    older, _ = await enqueue(
        kb_factory,
        store,
        b"eski surum metni " * 20,
        doc_type=DocumentType.genelge,
        official_ref="2021-11",
        original_name="Eski Ad.pdf",
    )
    by_name, _ = await enqueue(
        kb_factory, store, b"ayni adli baska dosya " * 20, original_name="ESKİ AD (1).txt"
    )
    by_ref, _ = await enqueue(
        kb_factory, store, GENELGE.encode(), review_status=ReviewStatus.pending
    )
    for _ in range(3):
        await worker.scan_next(kb_factory, store)
    assert (await load(kb_factory, by_ref)).matches == {
        "previous_version": {"file_id": str(older), "reason": "same_ref"},
        "similar": [],
    }
    # "Eski Ad.pdf" and "ESKİ AD (1).txt" are different names; an exact name match is found
    exact, _ = await enqueue(
        kb_factory, store, b"yine baska icerik " * 20, original_name="eski ad.TXT"
    )
    await worker.scan_next(kb_factory, store)
    assert ((await load(kb_factory, exact)).matches or {})["previous_version"] == {
        "file_id": str(older),
        "reason": "same_name",
    }
    assert ((await load(kb_factory, by_name)).matches or {})["previous_version"] is None


async def archive_decision(
    factory: Factory, store: LocalFileStore, name: str, body: str = DECISION_BODY
) -> uuid.UUID:
    """A decision of the archive as the import of task 12c leaves it: typed by its folder, with
    the extraction the loader wrote, scanned."""
    file_id, _ = await enqueue(
        factory, store, decision(body), doc_type=DocumentType.karar, original_name=name
    )
    async with factory() as session:
        session.add(
            Extraction(
                file_id=file_id,
                parser_name="decisions",
                parser_version="1",
                fields={"esas_no": "2021/5329", "karar_no": "2021/9588"},
            )
        )
        await session.commit()
    await worker.scan_next(factory, store)
    return file_id


OTHER_RENDERING = DECISION_BODY.replace(" davacı ", "\ndavacı\n").replace("etmiştir", "etmistir")


async def test_the_same_decision_as_another_pdf_is_similar_under_another_name(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    """Orhan's case (2026-10-12): the archive has the decision; another file of it, with other
    layout and a few other characters, comes in with a different name. The Esas / Karar numbers
    of the text find the archive row."""
    archive = await archive_decision(kb_factory, store, "HİZMET TESPİTİ.pdf")
    new, _ = await enqueue(
        kb_factory,
        store,
        decision(OTHER_RENDERING, "Karar özeti\n"),
        review_status=ReviewStatus.pending,
        original_name="indirilen.txt",
        doc_type=DocumentType.kanun,  # Orhan typed "kanun"; the text says karar
    )
    await worker.scan_next(kb_factory, store)
    file = await load(kb_factory, new)
    assert (file.suggestions or {})["doc_type"]["value"] == "karar"
    assert file.doc_type is DocumentType.kanun  # the detection does not touch the field
    matches = file.matches or {}
    assert [m["file_id"] for m in matches["similar"]] == [str(archive)]
    assert matches["similar"][0]["score"] >= 0.5  # every sentence has a changed word
    assert matches["similar"][0]["reason"] == "same_case"
    assert matches["previous_version"] == {"file_id": str(archive), "reason": "same_case"}


async def test_the_same_decision_under_the_same_name_is_found_by_the_name(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    archive, _ = await enqueue(
        kb_factory,
        store,
        decision(),
        doc_type=DocumentType.karar,
        original_name="HİZMET TESPİTİ.pdf",
    )
    await worker.scan_next(kb_factory, store)
    new, _ = await enqueue(
        kb_factory,
        store,
        decision(OTHER_RENDERING),
        review_status=ReviewStatus.pending,
        original_name="hizmet tespiti.txt",
    )
    await worker.scan_next(kb_factory, store)
    matches = (await load(kb_factory, new)).matches or {}
    assert matches["previous_version"] == {"file_id": str(archive), "reason": "same_name"}
    assert [m["file_id"] for m in matches["similar"]] == [str(archive)]


async def test_another_decision_with_the_same_numbers_is_not_similar(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    await archive_decision(kb_factory, store, "A.pdf")
    stranger = " ".join(f"başka {n} tamamen farklı gerekçe {n} sigorta" for n in range(80))
    new, _ = await enqueue(kb_factory, store, decision(stranger), original_name="b.txt")
    await worker.scan_next(kb_factory, store)
    matches = (await load(kb_factory, new)).matches or {}
    assert matches["similar"] == []
    assert matches["previous_version"] is not None  # same E/K: offered as a version, not "similar"


async def test_pending_and_archived_files_are_never_offered_as_the_previous_version(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    pending, _ = await enqueue(
        kb_factory,
        store,
        b"bir " * 40,
        original_name="Aynı Ad.txt",
        review_status=ReviewStatus.pending,
    )
    archived, _ = await enqueue(kb_factory, store, b"iki " * 40, original_name="Aynı Ad.pdf")
    async with kb_factory() as session:
        file = await session.get(IngestFile, archived)
        assert file is not None
        file.archived_at = datetime.now(UTC)
        await session.commit()
    new, _ = await enqueue(kb_factory, store, b"uc " * 40, original_name="aynı ad.docx")
    for _ in range(3):
        await worker.scan_next(kb_factory, store)
    assert ((await load(kb_factory, new)).matches or {})["previous_version"] is None
    assert pending  # the pending one only counts for the text comparison
