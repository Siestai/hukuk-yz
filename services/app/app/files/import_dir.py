"""Import of an archive directory into the file store (task 12c).

    python -m app.files.import_dir <dir> --uploaded-by-system [--report report.json]

Every regular file below `<dir>` is put into the `FileStore` (`FILE_STORE_ROOT`). A file whose
sha256 is already the `ingest_file` of the decision archive (task 05 load) only gives that row
its `storage_key` and `original_name`; any other new content gets a row (`doc_type` from the
Drive folder, `uploaded_by` NULL, queued for the worker's scan, original relative path in `path`
and `scan_result.import_path`). A file under `Eskiler/` becomes the previous version of the
current file of the same name (`supersedes_id`: the newer row points at the older one).

The run can be repeated: what is stored is skipped, so a second run adds nothing. A file that
cannot be read or written is an error in the report; the run goes on. The size limit of uploads
(`FILE_MAX_BYTES`) does not apply: the import is run by an admin on the server, and the archive
holds files bigger than an upload through the dashboard may be.
"""

import argparse
import asyncio
import json
import sys
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.files.scan_result import IMPORT_PATH
from app.files.store import FileStore, LocalFileStore
from app.models.common import (
    DocumentType,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    ScanStatus,
)
from app.settings import get_settings

ESKILER = "eskiler"
_SHEETS = {".xls", ".xlsx", ".xlsm"}
# Drive folder (folded, see `fold`) -> document type; the first folder on the path that is
# listed decides, so the subfolders (`Yönetmelik/İSG`, `Genelge/... ekleri`) follow their parent.
_FOLDERS = {
    "kanunlar": DocumentType.kanun,
    "genelge": DocumentType.genelge,
    "genel yazi": DocumentType.genel_yazi,
    "yonetmelik": DocumentType.yonetmelik,
    "teblig": DocumentType.teblig,
    "yargi kararlari": DocumentType.karar,
    "yargi_kararlari_arsivi": DocumentType.karar,
    "gorus": DocumentType.gorus,
    "diger mevzuat": DocumentType.diger,
    "diger": DocumentType.diger,
}


def fold(name: str) -> str:
    """A name for comparison: no accents (so NFC and NFD spellings agree), no case, `ı` and `İ`
    as `i`."""
    decomposed = unicodedata.normalize("NFD", name)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return plain.lower().replace("ı", "i")


def name_key(text: str) -> str:
    """`text` folded, with every run of other characters than letters and digits as one space:
    what makes two titles or file stems the same name."""
    folded = fold(text)
    return " ".join("".join(c if c.isalnum() else " " for c in folded).split())


def stem_key(name: str) -> str:
    """What makes two file names the same name for the `Eskiler/` link: the stem without the
    extension, folded, with every run of other characters than letters and digits as one
    space. `Kanun.pdf` and `KANUN.udf` agree; `5510 tarih 17.07.2024` does not match `5510`."""
    return name_key(PurePosixPath(name).stem)


def doc_type_of(parts: tuple[str, ...]) -> DocumentType:
    """The document type of a file by its path below the imported directory."""
    for folder in parts[:-1]:
        if (found := _FOLDERS.get(fold(folder))) is not None:
            return found
    if len(parts) == 1 and PurePosixPath(parts[0]).suffix.lower() in _SHEETS:
        return DocumentType.hesap_tablosu
    return DocumentType.diger


@dataclass
class Entry:
    """A file of the tree and the row it ended up on."""

    parts: tuple[str, ...]
    file_id: uuid.UUID

    @property
    def eskiler(self) -> bool:
        return len(self.parts) > 1 and fold(self.parts[-2]) == ESKILER

    @property
    def folder(self) -> tuple[str, ...]:
        return self.parts[: -2 if self.eskiler else -1]


@dataclass
class Report:
    added: int = 0
    matched: int = 0
    skipped: int = 0
    linked: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    unmatched_eskiler: list[dict[str, str]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if isinstance(v, int)},
            "errors": self.errors,
            "unmatched_eskiler": self.unmatched_eskiler,
        }


def _walk(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())


async def _import_one(
    factory: async_sessionmaker[AsyncSession],
    store: FileStore,
    path: Path,
    parts: tuple[str, ...],
    job: list[uuid.UUID],
    report: Report,
) -> uuid.UUID:
    """Store one file and write or fill its row; returns the row it is on. `job` holds the id of
    the run's job once the first row needs one."""

    def put() -> Any:
        with path.open("rb") as fh:
            return store.put(fh)

    stored = await asyncio.to_thread(put)
    name = parts[-1]
    rel = "/".join(parts)
    async with factory() as db:
        rows = (
            (
                await db.execute(
                    select(IngestFile)
                    .where(IngestFile.sha256 == stored.sha256)
                    .order_by(
                        IngestFile.storage_key.is_(None), IngestFile.uploaded_at, IngestFile.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if rows and rows[0].storage_key is not None:  # imported before, or twice in this tree
            report.skipped += 1
            return rows[0].id
        if rows:  # a row of the decision archive: it only gets the file
            row = rows[0]
            row.storage_key = stored.key
            row.original_name = row.original_name or name
            if row.doc_type is None:  # never over a type a user set on upload
                row.doc_type = doc_type_of(parts)
            await db.commit()
            report.matched += 1
            return row.id
        job_id = job[0] if job else None
        if job_id is None:
            new_job = IngestJob(
                kind=IngestKind.bulk, status=IngestStatus.running, started_at=datetime.now(UTC)
            )
            db.add(new_job)
            await db.flush()
            job_id = new_job.id
        file = IngestFile(
            job_id=job_id,
            path=rel,
            sha256=stored.sha256,
            size=stored.size,
            storage_key=stored.key,
            original_name=name,
            doc_type=doc_type_of(parts),
            scan_status=ScanStatus.queued,
            scan_result={IMPORT_PATH: rel},
        )
        db.add(file)
        await db.commit()
        job[:] = [job_id]
        report.added += 1
        return file.id


async def _link_eskiler(
    factory: async_sessionmaker[AsyncSession], entries: list[Entry], report: Report
) -> None:
    """Link each `Eskiler/` file to the current file of the same name in the parent folder. The
    links are made after all files are in, so the order in which the two were imported does not
    matter, and a repeated run finds them made."""
    current: dict[tuple[tuple[str, ...], str], list[Entry]] = {}
    for entry in entries:
        if not entry.eskiler:
            current.setdefault((entry.folder, stem_key(entry.parts[-1])), []).append(entry)
    current_ids = {e.file_id for e in entries if not e.eskiler}
    for old in (e for e in entries if e.eskiler):
        rel = "/".join(old.parts)
        candidates = current.get((old.folder, stem_key(old.parts[-1])), [])
        if len(candidates) != 1:
            reason = "no current file of this name" if not candidates else "several current files"
            report.unmatched_eskiler.append({"path": rel, "reason": reason})
            continue
        new = candidates[0]
        if old.file_id in current_ids:  # its content is that of a current file, maybe of another
            report.unmatched_eskiler.append(
                {"path": rel, "reason": "same content as a current file"}
            )
            continue
        try:
            async with factory() as db:
                outcome = await _link(db, new.file_id, old.file_id)
                await db.commit()
        except SQLAlchemyError as exc:
            report.errors.append({"path": rel, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        if outcome == "linked":
            report.linked += 1
        elif outcome:
            report.unmatched_eskiler.append({"path": rel, "reason": outcome})


async def _link(db: AsyncSession, new_id: uuid.UUID, old_id: uuid.UUID) -> str | None:
    """Make `old_id` the previous version of `new_id`. Returns `linked`, None when that was
    already so, else why it cannot be done (the chain never branches and has no cycle)."""
    if new_id == old_id:
        return "same content as the current file"
    ahead: uuid.UUID | None = old_id
    while ahead is not None:  # `old` must not lead back to `new`
        if ahead == new_id:
            return "would make a cycle"
        ahead = (
            await db.execute(select(IngestFile.supersedes_id).where(IngestFile.id == ahead))
        ).scalar_one_or_none()
    new = await db.get(IngestFile, new_id, with_for_update=True)
    assert new is not None  # the id was just written or read
    if new.supersedes_id == old_id:
        return None
    if new.supersedes_id is not None:
        return "the current file already has a previous version"
    taken = (
        await db.execute(select(IngestFile.id).where(IngestFile.supersedes_id == old_id))
    ).first()
    if taken:
        return "already the previous version of another file"
    await db.execute(update(IngestFile).where(IngestFile.id == new_id).values(supersedes_id=old_id))
    return "linked"


async def import_dir(
    root: Path, factory: async_sessionmaker[AsyncSession], store: FileStore
) -> Report:
    report = Report()
    entries: list[Entry] = []
    job: list[uuid.UUID] = []
    for path in _walk(root):
        parts = path.relative_to(root).parts
        try:
            file_id = await _import_one(factory, store, path, parts, job, report)
        except (OSError, SQLAlchemyError) as exc:
            report.errors.append(
                {"path": "/".join(parts), "reason": f"{type(exc).__name__}: {exc}"}
            )
            continue
        entries.append(Entry(parts, file_id))
    await _link_eskiler(factory, entries, report)
    if job:
        async with factory() as db:
            await db.execute(
                update(IngestJob).where(IngestJob.id == job[0]).values(stats=report.summary())
            )
            await db.commit()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.files.import_dir", description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--uploaded-by-system",
        action="store_true",
        required=True,
        help="the rows get no uploader (uploaded_by NULL): a bulk import by the system",
    )
    parser.add_argument("--report", type=Path, help="write the summary as JSON to this file")
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.file_store_root is None:
        print("FILE_STORE_ROOT is not set", file=sys.stderr)
        return 2
    if not args.directory.is_dir():
        print(f"not a directory: {args.directory}", file=sys.stderr)
        return 2
    report = asyncio.run(_run(args.directory, settings.database_url, settings.file_store_root))
    summary = report.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if report.errors else 0


async def _run(directory: Path, database_url: str, store_root: Path) -> Report:
    engine = make_engine(database_url)
    try:
        return await import_dir(directory, make_session_factory(engine), LocalFileStore(store_root))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
