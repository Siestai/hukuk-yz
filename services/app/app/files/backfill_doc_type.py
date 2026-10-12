"""One-off backfill of `ingest_file.doc_type` for rows that have none (task 12d).

    python -m app.files.backfill_doc_type [--dry-run]

The rows of the decision archive (task 05 load) were typed only if the import (12c) added them
as new rows. Every `ingest_file` with a NULL `doc_type` gets the type of its Drive folder, by
the same rule as the import (`doc_type_of`), from `scan_result.import_path` when there is one,
else from `path` (relative to the Drive copy, e.g. `Yargi_Kararlari_Arsivi/...`). A path that
matches no folder is `diger`; a row with an empty path stays NULL and is counted. A type that is
set is never touched by that pass. A second pass retypes `diger` to `gorus` on rows of the system
import (`uploaded_by` NULL and `scan_result.import_path` set) whose folder is Görüş: the import
before migration 0011 had no such folder and typed them `diger`. A `diger` chosen on an upload
(`uploaded_by` set) is never touched. The run can be repeated (a second run updates and retypes
0) and does not race with an upload. `--dry-run` counts and writes nothing. This is a command
and not an Alembic step: migrations are schema only (docs/decisions.md). Prints a JSON summary.
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import defaultdict
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.files.import_dir import doc_type_of
from app.files.scan_result import IMPORT_PATH
from app.models.common import DocumentType, IngestFile
from app.settings import get_settings

BATCH = 1000


def _path_of(path: str, scan_result: dict[str, Any] | None) -> str:
    imported = (scan_result or {}).get(IMPORT_PATH)
    return imported if isinstance(imported, str) and imported.strip() else path


async def backfill(factory: async_sessionmaker[AsyncSession], *, dry_run: bool) -> dict[str, Any]:
    """Type every untyped row; returns the summary. Rows changed meanwhile are not counted."""
    ids: dict[str, list[uuid.UUID]] = defaultdict(list)
    left_null = 0
    async with factory() as db:
        found = await db.execute(
            select(IngestFile.id, IngestFile.path, IngestFile.scan_result).where(
                IngestFile.doc_type.is_(None)
            )
        )
        for file_id, path, scan_result in found:
            parts = tuple(p for p in _path_of(path or "", scan_result).split("/") if p.strip())
            if not parts:
                left_null += 1
                continue
            ids[doc_type_of(parts).value].append(file_id)
        updated: dict[str, int] = {}
        for value, found_ids in sorted(ids.items()):
            if dry_run:
                updated[value] = len(found_ids)
                continue
            count = 0
            for start in range(0, len(found_ids), BATCH):
                result = await db.execute(
                    update(IngestFile)
                    .where(
                        IngestFile.id.in_(found_ids[start : start + BATCH]),
                        IngestFile.doc_type.is_(None),
                    )
                    .values(doc_type=value)
                )
                count += cast(CursorResult[Any], result).rowcount
            updated[value] = count
        retyped = await _retype_gorus(db, dry_run=dry_run)
        await db.commit()
    return {"dry_run": dry_run, "updated": updated, "retyped": retyped, "left_null": left_null}


async def _retype_gorus(db: AsyncSession, *, dry_run: bool) -> dict[str, int]:
    """`diger` -> `gorus` on system-imported rows under a Görüş folder; {} when none."""
    found = await db.execute(
        select(IngestFile.id, IngestFile.scan_result).where(
            IngestFile.doc_type == DocumentType.diger, IngestFile.uploaded_by.is_(None)
        )
    )
    gorus_ids: list[uuid.UUID] = []
    for file_id, scan_result in found:
        imported = (scan_result or {}).get(IMPORT_PATH)
        if not isinstance(imported, str):
            continue
        parts = tuple(p for p in imported.split("/") if p.strip())
        if parts and doc_type_of(parts) is DocumentType.gorus:
            gorus_ids.append(file_id)
    if dry_run:
        count = len(gorus_ids)
    else:
        count = 0
        for start in range(0, len(gorus_ids), BATCH):
            result = await db.execute(
                update(IngestFile)
                .where(
                    IngestFile.id.in_(gorus_ids[start : start + BATCH]),
                    IngestFile.doc_type == DocumentType.diger,
                    IngestFile.uploaded_by.is_(None),
                )
                .values(doc_type=DocumentType.gorus)
            )
            count += cast(CursorResult[Any], result).rowcount
    return {"gorus": count} if count else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.files.backfill_doc_type", description=__doc__
    )
    parser.add_argument("--dry-run", action="store_true", help="count only, write nothing")
    args = parser.parse_args(argv)
    summary = asyncio.run(_run(get_settings().database_url, args.dry_run))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


async def _run(database_url: str, dry_run: bool) -> dict[str, Any]:
    engine = make_engine(database_url)
    try:
        return await backfill(make_session_factory(engine), dry_run=dry_run)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
