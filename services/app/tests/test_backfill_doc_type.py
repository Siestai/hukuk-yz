"""The doc_type backfill of the archive rows (task 12d)."""

import asyncio
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import settings
from app.files import backfill_doc_type
from app.files.backfill_doc_type import backfill
from app.files.scan_result import IMPORT_PATH
from app.loaders.decisions import load, prepare, read_files, read_rows
from app.loaders.report import LoadCounts
from app.models.common import DocumentType, IngestFile
from app.models.user import AppUser, UserRole

Factory = async_sessionmaker[AsyncSession]
DEMO = Path(__file__).parents[3] / "infra" / "demo"


async def load_demo(factory: Factory) -> int:
    prepared, _ = prepare(
        *(read_rows(DEMO / "decisions.jsonl")[:1]), read_files(DEMO / "files.jsonl")
    )
    await load(factory, prepared, LoadCounts(total=len(prepared)))
    async with factory() as session:
        return len((await session.execute(select(IngestFile.id))).all())


async def types(factory: Factory) -> list[DocumentType | None]:
    async with factory() as session:
        return list((await session.execute(select(IngestFile.doc_type))).scalars())


async def test_the_demo_decision_rows_all_become_karar_and_a_second_run_updates_nothing(
    kb_factory: Factory,
) -> None:
    total = await load_demo(kb_factory)
    assert total and set(await types(kb_factory)) == {None}
    first = await backfill(kb_factory, dry_run=False)
    assert first == {"dry_run": False, "updated": {"karar": total}, "retyped": {}, "left_null": 0}
    assert set(await types(kb_factory)) == {DocumentType.karar}
    second = await backfill(kb_factory, dry_run=False)
    assert second == {"dry_run": False, "updated": {}, "retyped": {}, "left_null": 0}


async def test_a_dry_run_counts_and_writes_nothing(kb_factory: Factory) -> None:
    total = await load_demo(kb_factory)
    summary = await backfill(kb_factory, dry_run=True)
    assert summary == {"dry_run": True, "updated": {"karar": total}, "retyped": {}, "left_null": 0}
    assert set(await types(kb_factory)) == {None}


async def test_the_import_path_wins_a_set_type_is_kept_and_an_empty_path_stays_null(
    kb_factory: Factory,
) -> None:
    await load_demo(kb_factory)
    async with kb_factory() as session:
        rows = list((await session.execute(select(IngestFile))).scalars())
        rows[0].path = ""
        rows[1].path = "Mevzuat/Genelge/x.pdf"
        rows[2].path = "Mevzuat/Görüş/y.pdf"
        rows[2].scan_result = {IMPORT_PATH: "Mevzuat/Tebliğ/y.pdf"}
        rows[3].path = "elsewhere/z.pdf"
        rows[4].doc_type = DocumentType.kitap  # set on upload
        ids = [r.id for r in rows[:5]]
        await session.commit()
    summary = await backfill(kb_factory, dry_run=False)
    async with kb_factory() as session:
        got = {r.id: r.doc_type for r in (await session.execute(select(IngestFile))).scalars()}
    assert [got[i] for i in ids] == [
        None,
        DocumentType.genelge,
        DocumentType.teblig,
        DocumentType.diger,
        DocumentType.kitap,
    ]
    assert summary["left_null"] == 1
    assert summary["updated"]["genelge"] == summary["updated"]["teblig"] == 1
    assert summary["updated"]["diger"] == 1
    assert "kitap" not in summary["updated"]


async def retype_setup(factory: Factory) -> list[uuid.UUID]:
    """Four `diger` rows: system Görüş, user-picked Görüş path, system Diğer mevzuat, system Görüş
    without import_path."""
    await load_demo(factory)
    async with factory() as session:
        user = AppUser(
            email="u@x.test", display_name="u", role=UserRole.reviewer, password_hash="x"
        )
        session.add(user)
        await session.flush()
        rows = list((await session.execute(select(IngestFile))).scalars())[:4]
        for row in rows:
            row.doc_type = DocumentType.diger
            row.uploaded_by = None
        rows[0].scan_result = {IMPORT_PATH: "Mevzuat/Görüş/a.pdf"}
        rows[1].scan_result = {IMPORT_PATH: "Mevzuat/Görüş/b.pdf"}
        rows[1].uploaded_by = user.id
        rows[2].scan_result = {IMPORT_PATH: "Mevzuat/Diğer mevzuat/c.pdf"}
        rows[3].path = "Mevzuat/Görüş/d.pdf"
        rows[3].scan_result = None
        ids = [r.id for r in rows]
        await session.commit()
    return ids


async def test_a_system_diger_under_gorus_is_retyped_a_user_pick_is_kept_and_a_rerun_is_0(
    kb_factory: Factory,
) -> None:
    ids = await retype_setup(kb_factory)
    summary = await backfill(kb_factory, dry_run=False)
    async with kb_factory() as session:
        got = {r.id: r.doc_type for r in (await session.execute(select(IngestFile))).scalars()}
    assert [got[i] for i in ids] == [DocumentType.gorus] + [DocumentType.diger] * 3
    assert summary["retyped"] == {"gorus": 1}
    again = await backfill(kb_factory, dry_run=False)
    assert again["retyped"] == {} and again["updated"] == {}


async def test_a_dry_run_counts_the_retype_and_writes_nothing(kb_factory: Factory) -> None:
    ids = await retype_setup(kb_factory)
    summary = await backfill(kb_factory, dry_run=True)
    assert summary["retyped"] == {"gorus": 1}
    async with kb_factory() as session:
        got = {r.id: r.doc_type for r in (await session.execute(select(IngestFile))).scalars()}
    assert [got[i] for i in ids] == [DocumentType.diger] * 4


async def test_the_command_prints_the_summary(
    kb_factory: Factory,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    total = await load_demo(kb_factory)
    monkeypatch.setenv("DATABASE_URL", database_url)
    settings.get_settings.cache_clear()
    try:
        # main() runs its own event loop, so it is called from a thread.
        code = await asyncio.to_thread(backfill_doc_type.main, ["--dry-run"])
    finally:
        settings.get_settings.cache_clear()
    assert code == 0
    assert json.loads(capsys.readouterr().out)["updated"] == {"karar": total}
