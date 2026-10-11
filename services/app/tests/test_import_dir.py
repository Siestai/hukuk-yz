"""The archive import (task 12c). The database tests are skipped when DATABASE_URL is unset."""

import asyncio
import io
import json
import shutil
import unicodedata
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import settings, worker
from app.files import import_dir as import_dir_module
from app.files.import_dir import Report, _link, doc_type_of, fold, import_dir, main, stem_key
from app.files.store import LocalFileStore, StoredFile
from app.loaders.decisions import load, prepare, read_files, read_rows
from app.loaders.report import LoadCounts
from app.models.common import DocumentType, IngestFile, IngestJob, IngestKind, ScanStatus

Factory = async_sessionmaker[AsyncSession]
DEMO = Path(__file__).parents[3] / "infra" / "demo"
DEMO_FILES = 12


@pytest.fixture
def store(tmp_path: Path) -> LocalFileStore:
    return LocalFileStore(tmp_path / "store")


def write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


async def rows(factory: Factory) -> dict[str, IngestFile]:
    async with factory() as session:
        found = (await session.execute(select(IngestFile))).scalars().all()
    return {f.path: f for f in found}


async def load_demo(factory: Factory) -> None:
    prepared, _ = prepare(
        *(read_rows(DEMO / "decisions.jsonl")[:1]), read_files(DEMO / "files.jsonl")
    )
    await load(factory, prepared, LoadCounts(total=len(prepared)))


# --- names and types, no database ---


def test_fold_ignores_case_accents_and_the_unicode_form() -> None:
    assert fold("Yönetmelik (+İSG)") == fold(unicodedata.normalize("NFD", "YÖNETMELİK (+isg)"))
    assert fold("Tebliğ") == fold("TEBLİĞ") == fold("Teblig")
    assert stem_key("5510  Sayılı-Kanun.PDF") == stem_key("5510 sayili kanun.udf")
    assert stem_key("5510 tarih 17.07.2024.pdf") != stem_key("5510.pdf")


@pytest.mark.parametrize(
    ("rel", "expected"),
    [
        ("Mevzuat/Kanunlar/5510.pdf", DocumentType.kanun),
        ("Mevzuat/Kanunlar/Eskiler/5510 tarih 2020.pdf", DocumentType.kanun),
        ("Mevzuat/Genelge/2020-39.pdf", DocumentType.genelge),
        ("Mevzuat/Genelge/2020-39 ekleri/ek.pdf", DocumentType.genelge),
        ("Mevzuat/Genel Yazı/x.udf", DocumentType.genel_yazi),
        ("Mevzuat/Yönetmelik/y.pdf", DocumentType.yonetmelik),
        ("Mevzuat/Yönetmelik/İSG/y.pdf", DocumentType.yonetmelik),
        ("Mevzuat/Tebliğ/t.pdf", DocumentType.teblig),
        ("Mevzuat/Yargı Kararları/k.pdf", DocumentType.karar),
        ("Yargi_Kararlari_Arsivi/90. Sayi/k.pdf", DocumentType.karar),
        ("Mevzuat/Görüş/g.pdf", DocumentType.diger),
        ("Mevzuat/Diğer mevzuat/d.pdf", DocumentType.diger),
        ("Bordro hesaplama.xlsm", DocumentType.hesap_tablosu),
        ("Net Brüt.XLSX", DocumentType.hesap_tablosu),
        ("MANIFEST.txt", DocumentType.diger),
        ("Mevzuat/Kanunlar/hesap.xlsx", DocumentType.kanun),
    ],
)
def test_the_folder_gives_the_document_type(rel: str, expected: DocumentType) -> None:
    for spelling in (rel, unicodedata.normalize("NFD", rel), rel.swapcase()):
        assert doc_type_of(tuple(spelling.split("/"))) is expected


# --- the import ---


async def test_the_demo_archive_is_imported_once(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    first = await import_dir(DEMO / "archive", kb_factory, store)
    assert (first.added, first.matched, first.skipped, first.errors) == (DEMO_FILES, 0, 0, [])
    stored = await rows(kb_factory)
    assert len(stored) == DEMO_FILES
    for row in stored.values():
        assert row.storage_key and store.exists(row.storage_key)
        assert (row.doc_type, row.uploaded_by) == (DocumentType.karar, None)
        assert row.scan_status is ScanStatus.queued
        assert row.scan_result == {"import_path": row.path}
        assert row.original_name == row.path.rsplit("/", 1)[1]
    second = await import_dir(DEMO / "archive", kb_factory, store)
    assert (second.added, second.matched, second.skipped) == (0, 0, DEMO_FILES)
    assert len(await rows(kb_factory)) == DEMO_FILES
    async with kb_factory() as session:
        jobs = (await session.execute(select(IngestJob))).scalars().all()
    assert [(j.kind, j.stats["added"]) for j in jobs] == [(IngestKind.bulk, DEMO_FILES)]


async def test_rows_of_the_decision_load_get_their_file_and_no_new_row(
    kb_factory: Factory, store: LocalFileStore
) -> None:
    await load_demo(kb_factory)
    before = await rows(kb_factory)
    assert before and all(r.storage_key is None for r in before.values())
    report = await import_dir(DEMO / "archive", kb_factory, store)
    assert (report.added, report.matched, report.errors) == (0, len(before), [])
    assert report.skipped == DEMO_FILES - len(before)  # the same content under two names
    after = await rows(kb_factory)
    assert {r.id for r in after.values()} == {r.id for r in before.values()}
    for path, row in after.items():
        assert row.storage_key and store.exists(row.storage_key)
        assert row.original_name == path.rsplit("/", 1)[1]
        assert row.doc_type is None  # only the file is filled in
        assert row.scan_status is before[path].scan_status is ScanStatus.done
        assert row.scan_result is None
    async with kb_factory() as session:
        assert (await session.execute(select(func.count(IngestJob.id)))).scalar_one() == 1
    again = await import_dir(DEMO / "archive", kb_factory, store)
    assert (again.added, again.matched, again.skipped) == (0, 0, DEMO_FILES)


async def test_a_loader_row_keeps_the_original_name_it_has(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    await load_demo(kb_factory)
    async with kb_factory() as session:
        row = (await session.execute(select(IngestFile).limit(1))).scalar_one()
        row.original_name = "Kept.pdf"
        path = row.path
        await session.commit()
    await import_dir(DEMO / "archive", kb_factory, store)
    assert (await rows(kb_factory))[path].original_name == "Kept.pdf"


async def test_new_files_get_the_type_of_their_folder_whatever_the_unicode_form(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    names = {
        "Mevzuat/Tebliğ/a.txt": DocumentType.teblig,
        "Mevzuat/YÖNETMELİK/İSG/b.txt": DocumentType.yonetmelik,
        "Mevzuat/Genel Yazı/c.txt": DocumentType.genel_yazi,
        "Hesap.xlsx": DocumentType.hesap_tablosu,
        "Başka/d.txt": DocumentType.diger,
    }
    for i, (rel, _) in enumerate(names.items()):
        write(tree, unicodedata.normalize("NFD", rel), f"içerik {i}".encode())
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.errors) == (len(names), [])
    got = {unicodedata.normalize("NFC", p): r.doc_type for p, r in (await rows(kb_factory)).items()}
    assert got == names


async def test_the_same_content_twice_in_the_tree_is_one_row(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Mevzuat/Kanunlar/a.txt", b"same")
    write(tree, "Mevzuat/Genelge/b.txt", b"same")
    write(tree, "c.txt", b"other")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.skipped, report.errors) == (2, 1, [])
    assert len(await rows(kb_factory)) == 2


async def test_a_file_that_cannot_be_stored_is_an_error_and_the_run_goes_on(
    kb_factory: Factory, tmp_path: Path
) -> None:
    class Failing(LocalFileStore):
        def put(self, stream: BinaryIO) -> StoredFile:
            data = stream.read()
            if b"corrupt" in data:
                raise OSError("input/output error")
            return super().put(io.BytesIO(data))

    tree = tmp_path / "tree"
    write(tree, "a.txt", b"fine a")
    write(tree, "b.txt", b"corrupt")
    write(tree, "c.txt", b"fine c")
    report = await import_dir(tree, kb_factory, Failing(tmp_path / "store"))
    assert (report.added, len(report.errors)) == (2, 1)
    assert report.errors[0]["path"] == "b.txt"
    assert "OSError" in report.errors[0]["reason"]
    assert set(await rows(kb_factory)) == {"a.txt", "c.txt"}


async def test_symlinks_are_not_followed(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "a.txt", b"a")
    (tree / "link.txt").symlink_to(write(tmp_path, "outside.txt", b"outside"))
    (tree / "broken.txt").symlink_to(tmp_path / "nowhere")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.errors) == (1, [])


# --- Eskiler ---


async def chain(factory: Factory) -> dict[str, str | None]:
    """File path -> path of the file it supersedes."""
    stored = await rows(factory)
    by_id = {r.id: p for p, r in stored.items()}
    return {p: by_id.get(r.supersedes_id) if r.supersedes_id else None for p, r in stored.items()}


@pytest.mark.parametrize("current", ["Aaa Kanun.pdf", "Zzz Kanun.pdf"])
async def test_an_eskiler_file_is_the_previous_version_of_the_current_one_in_either_order(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path, current: str
) -> None:
    # "Aaa" is walked before Eskiler/, "Zzz" after it.
    tree = tmp_path / "tree"
    old = f"Mevzuat/Kanunlar/Eskiler/{current.lower().replace('.pdf', '.udf')}"
    write(tree, f"Mevzuat/Kanunlar/{current}", b"new text")
    write(tree, old, b"old text")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.linked, report.unmatched_eskiler) == (2, 1, [])
    assert await chain(kb_factory) == {f"Mevzuat/Kanunlar/{current}": old, old: None}
    again = await import_dir(tree, kb_factory, store)
    assert (again.added, again.linked, again.unmatched_eskiler) == (0, 0, [])


async def test_the_current_file_may_come_in_an_earlier_run_than_its_eskiler_file(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/2020-39.pdf", b"current")
    await import_dir(tree, kb_factory, store)
    write(tree, "Genelge/Eskiler/2020 39.pdf", b"old")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.linked) == (1, 1)
    assert (await chain(kb_factory))["Genelge/2020-39.pdf"] == "Genelge/Eskiler/2020 39.pdf"


async def test_an_eskiler_file_that_matches_no_current_file_is_listed(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Kanunlar/5510.pdf", b"current")
    write(tree, "Kanunlar/Eskiler/5510 tarih 17.07.2024.pdf", b"old, other name")
    write(tree, "Kanunlar/Eskiler/4857.pdf", b"old, no current")
    write(tree, "Genelge/Eskiler/2013_05.pdf", b"old, no folder above")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.linked) == (4, 0)
    assert {u["path"] for u in report.unmatched_eskiler} == {
        "Kanunlar/Eskiler/5510 tarih 17.07.2024.pdf",
        "Kanunlar/Eskiler/4857.pdf",
        "Genelge/Eskiler/2013_05.pdf",
    }
    assert set((await chain(kb_factory)).values()) == {None}
    # Listed again in a later run: the list is the work still to do.
    again = await import_dir(tree, kb_factory, store)
    assert len(again.unmatched_eskiler) == 3


async def test_the_chain_never_branches(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/G.pdf", b"current")
    write(tree, "Genelge/Eskiler/G.pdf", b"old 1")
    write(tree, "Genelge/Eskiler/G.udf", b"old 2")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.linked, len(report.unmatched_eskiler)) == (3, 1, 1)
    assert list((await chain(kb_factory)).values()).count(None) == 2


async def test_an_eskiler_file_with_the_content_of_the_current_one_is_listed(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/G.pdf", b"same")
    write(tree, "Genelge/Eskiler/G.pdf", b"same")
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.skipped, report.linked) == (1, 1, 0)
    assert len(report.unmatched_eskiler) == 1


async def test_an_eskiler_file_with_the_content_of_another_current_file_is_listed(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/A.pdf", b"text of a")
    write(tree, "Genelge/B.pdf", b"text of b")
    write(tree, "Genelge/Eskiler/A.pdf", b"text of b")  # B's content under A's name
    report = await import_dir(tree, kb_factory, store)
    assert (report.linked, report.unmatched_eskiler) == (
        0,
        [{"path": "Genelge/Eskiler/A.pdf", "reason": "same content as a current file"}],
    )
    assert set((await chain(kb_factory)).values()) == {None}


async def test_a_link_that_would_make_a_cycle_is_listed(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/G.pdf", b"current")
    write(tree, "Genelge/Eskiler/G.pdf", b"old")
    await import_dir(tree, kb_factory, store)
    stored = await rows(kb_factory)
    new, old = stored["Genelge/G.pdf"], stored["Genelge/Eskiler/G.pdf"]
    async with kb_factory() as db:
        assert await _link(db, old.id, new.id) == "would make a cycle"


async def test_a_failing_link_is_an_error_and_the_run_goes_on_and_writes_its_stats(
    kb_factory: Factory,
    store: LocalFileStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Genelge/G.pdf", b"current g")
    write(tree, "Genelge/Eskiler/G.pdf", b"old g")
    write(tree, "Kanunlar/K.pdf", b"current k")
    write(tree, "Kanunlar/Eskiler/K.pdf", b"old k")
    real = import_dir_module._link

    async def flaky(db: AsyncSession, new_id: uuid.UUID, old_id: uuid.UUID) -> str | None:
        if (await db.get(IngestFile, old_id)).path.startswith("Genelge"):  # type: ignore[union-attr]
            raise IntegrityError("update", {}, Exception("unique"))
        return await real(db, new_id, old_id)

    monkeypatch.setattr(import_dir_module, "_link", flaky)
    report = await import_dir(tree, kb_factory, store)
    assert (report.added, report.linked) == (4, 1)
    assert [e["path"] for e in report.errors] == ["Genelge/Eskiler/G.pdf"]
    async with kb_factory() as db:
        (job,) = (await db.execute(select(IngestJob))).scalars().all()
    assert job.stats and job.stats["linked"] == 1 and len(job.stats["errors"]) == 1


# --- scan queue and worker ---


async def test_only_new_files_are_queued_and_the_scan_keeps_the_import_path(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path, make_pdf: Callable[..., bytes]
) -> None:
    await load_demo(kb_factory)
    tree = tmp_path / "tree"
    shutil.copytree(DEMO / "archive", tree)
    write(tree, "Mevzuat/Genelge/G.pdf", make_pdf())
    report = await import_dir(tree, kb_factory, store)
    assert report.added == 1
    stored = await rows(kb_factory)
    assert {r.scan_status for p, r in stored.items() if p != "Mevzuat/Genelge/G.pdf"} == {
        ScanStatus.done
    }
    assert stored["Mevzuat/Genelge/G.pdf"].scan_status is ScanStatus.queued
    assert await worker.scan_next(kb_factory, store)
    assert not await worker.scan_next(kb_factory, store)
    scanned = (await rows(kb_factory))["Mevzuat/Genelge/G.pdf"]
    assert scanned.scan_status is ScanStatus.done
    assert scanned.scan_result and scanned.scan_result["import_path"] == "Mevzuat/Genelge/G.pdf"


async def test_requeue_stuck_keeps_the_import_path(
    kb_factory: Factory, store: LocalFileStore, tmp_path: Path, make_pdf: Callable[..., bytes]
) -> None:
    tree = tmp_path / "tree"
    write(tree, "Mevzuat/Genelge/G.pdf", make_pdf())
    await import_dir(tree, kb_factory, store)
    old = (datetime.now(UTC) - worker.STUCK_AFTER - timedelta(minutes=1)).isoformat()
    for attempts, expected in ((1, ScanStatus.queued), (worker.MAX_ATTEMPTS, ScanStatus.failed)):
        async with kb_factory() as db:
            file = (await db.execute(select(IngestFile))).scalar_one()
            file.scan_status = ScanStatus.running
            file.scan_result = {**(file.scan_result or {}), "started_at": old, "attempts": attempts}
            await db.commit()
        assert await worker.requeue_stuck(kb_factory) == 1
        handled = (await rows(kb_factory))["Mevzuat/Genelge/G.pdf"]
        assert handled.scan_status is expected
        assert (handled.scan_result or {})["import_path"] == "Mevzuat/Genelge/G.pdf"


# --- the command line ---


def test_without_a_file_store_root_the_command_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FILE_STORE_ROOT", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused")
    settings.get_settings.cache_clear()
    try:
        assert main([str(tmp_path), "--uploaded-by-system"]) == 2
    finally:
        settings.get_settings.cache_clear()
    assert "FILE_STORE_ROOT" in capsys.readouterr().err


def test_the_command_needs_the_system_flag(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([str(tmp_path)])


async def test_the_command_prints_and_writes_the_report(
    kb_factory: Factory,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tree = tmp_path / "tree"
    write(tree, "a.txt", b"a")
    write(tree, "Kanunlar/Eskiler/old.txt", b"old")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("FILE_STORE_ROOT", str(tmp_path / "store"))
    settings.get_settings.cache_clear()
    report = tmp_path / "report.json"
    try:
        code = await asyncio.to_thread(
            main, [str(tree), "--uploaded-by-system", "--report", str(report)]
        )
    finally:
        settings.get_settings.cache_clear()
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert json.loads(report.read_text(encoding="utf-8")) == printed
    assert (printed["added"], printed["matched"], printed["skipped"]) == (2, 0, 0)
    assert printed["unmatched_eskiler"] == [
        {"path": "Kanunlar/Eskiler/old.txt", "reason": "no current file of this name"}
    ]


def test_the_report_summary_has_the_counts_and_the_lists() -> None:
    summary = Report(added=1, errors=[{"path": "x", "reason": "y"}]).summary()
    assert summary == {
        "added": 1,
        "matched": 0,
        "skipped": 0,
        "linked": 0,
        "errors": [{"path": "x", "reason": "y"}],
        "unmatched_eskiler": [],
    }
