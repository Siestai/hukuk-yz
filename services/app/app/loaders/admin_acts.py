"""Load genelge sections (`hukuk-ingest admin-acts` -> admin-acts.jsonl) into the KB review queue
(handoff 2026-11-22, A3).

    python -m app.loaders.admin_acts admin-acts.jsonl

The file of a genelge becomes an `ingest_file` (one per sha256), the genelge one `source`
(category `admin_act`, `official_secondary`, `public`, status `analyzed`) and every section one
`extraction` (parser `admin_acts`) with its confidence band, all under one bulk `ingest_job`. The
review unit is the section. No `admin_act` row is written: that belongs to approval, which the
sections have no screen for yet, so every section stays unreviewed.

Idempotency: a section is loaded once per (parser version, section number, sha256 of the file,
content hash); the content hash is the sha256 of the canonical JSON of its `fields`
(`app.loaders.statutes.content_hash`). A rerun adds nothing; a new parser version, a new file or
a changed section adds an extraction and leaves the old ones alone. A record without sections
(the scan left the file as `needs_ocr`, or the file names another genelge) is reported as an
error and loads nothing. As in the statute loader it is a read-then-insert: concurrent runs are
not supported.
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import make_engine, make_session_factory
from app.loaders.decisions import error_name, finish_job, is_row_error
from app.loaders.report import BANDS
from app.loaders.statutes import content_hash
from app.models.common import (
    ADMIN_ACT_PARSER_NAME,
    Extraction,
    IngestFile,
    IngestJob,
    IngestKind,
    IngestStatus,
    License,
    RecordStatus,
    ReviewStatus,
    Source,
    SourceCategory,
    SourceRank,
)
from app.settings import get_settings
from hukuk_ingest.admin_acts import confidence as band_rules
from hukuk_ingest.admin_acts.citation import act_label
from hukuk_ingest.statutes.confidence import HIGH, code

REQUIRED_KEYS = frozenset({"ref", "parser_version", "status", "file", "sections"})
# (parser version, section number, sha256 of the file, content hash)
Key = tuple[str, str, str, str | None]


@dataclass
class PreparedSection:
    section_no: str
    fields: dict[str, Any]
    warnings: list[str]
    confidence: dict[str, Any]


@dataclass
class PreparedAct:
    ref: str
    parser_version: str
    title: str
    official_ref: str
    file: dict[str, Any]
    sections: list[PreparedSection]


@dataclass
class Counts:
    new: int = 0
    skipped_existing: int = 0
    sources_new: int = 0
    files_new: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


def read_records(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Usable genelge records (all keys, sections with a known band) and error refs."""
    records: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append({"ref": f"satır {number}", "error": "invalid JSON"})
                continue
            if not isinstance(row, dict) or not REQUIRED_KEYS <= row.keys():
                errors.append({"ref": f"satır {number}", "error": "missing record keys"})
            elif not row["sections"]:
                errors.append({"ref": f"satır {number} · {row['ref']}", "error": row["status"]})
            elif any(s["confidence"] not in BANDS for s in row["sections"]):
                errors.append({"ref": f"satır {number} · {row['ref']}", "error": "unknown band"})
            else:
                records.append(row)
    return records, errors


def prepare(records: Sequence[dict[str, Any]]) -> list[PreparedAct]:
    prepared = []
    for r in records:
        label = act_label(r["ref"], r["issuer"])
        act = {k: r[k] for k in ("issuer", "kind", "subject", "date")}
        sections = []
        for s in r["sections"]:
            reasons = sorted(
                {code(w) for w in s["warnings"] if band_rules.RULES.get(code(w), HIGH) != HIGH}
            )
            fields = {**s, "act_ref": r["ref"], "act": act, "file_sha256": r["file"]["sha256"]}
            sections.append(
                PreparedSection(
                    section_no=s["section_no"],
                    fields={**fields, "content_hash": content_hash(fields)},
                    warnings=s["warnings"],
                    confidence={"band": s["confidence"], "reasons": reasons},
                )
            )
        issued = f", {date.fromisoformat(r['date']).strftime('%d.%m.%Y')}" if r["date"] else ""
        prepared.append(
            PreparedAct(
                ref=r["ref"],
                parser_version=r["parser_version"],
                title=f"{label} · {r['subject']}" if r["subject"] else label,
                official_ref=f"{label}{issued}",
                file=r["file"],
                sections=sections,
            )
        )
    return prepared


@dataclass
class _Known:
    source_id: uuid.UUID | None = None
    keys: set[Key] = field(default_factory=set)


async def _known(factory: async_sessionmaker[AsyncSession], refs: list[str]) -> dict[str, _Known]:
    """The genelges' source ids and loaded section keys, by ref."""
    found = {ref: _Known() for ref in refs}
    ref = Extraction.fields["act_ref"].as_string()
    async with factory() as session:
        result = await session.execute(
            select(
                ref,
                Extraction.source_id,
                Extraction.parser_version,
                Extraction.fields["section_no"].as_string(),
                Extraction.fields["file_sha256"].as_string(),
                Extraction.fields["content_hash"].as_string(),
            )
            .where(Extraction.parser_name == ADMIN_ACT_PARSER_NAME, ref.in_(refs))
            .order_by(Extraction.extracted_at)
        )
        for act_ref, source_id, version, section_no, sha, digest in result:
            found[act_ref].source_id = source_id
            found[act_ref].keys.add((version, section_no, sha, digest))
    return found


def _key(act: PreparedAct, s: PreparedSection) -> Key:
    return (act.parser_version, s.section_no, act.file["sha256"], s.fields["content_hash"])


async def _write_act(
    session: AsyncSession,
    act: PreparedAct,
    pending: list[PreparedSection],
    source_id: uuid.UUID | None,
    job_id: uuid.UUID,
    counts: Counts,
) -> None:
    """The file, the source (unless the genelge has one) and the pending extractions of one
    genelge, in the caller's transaction. `counts` is a scratch copy that the caller merges after
    the commit."""
    sha = act.file["sha256"]
    file_id = (
        await session.execute(select(IngestFile.id).where(IngestFile.sha256 == sha).limit(1))
    ).scalar_one_or_none()
    if file_id is None:
        file_id = uuid.uuid4()
        await session.execute(
            insert(IngestFile),
            {
                "id": file_id,
                "job_id": job_id,
                "path": act.file["path"],
                "sha256": sha,
                "detected_type": act.file.get("detected_type"),
                "size": act.file.get("size", 0),
                "review_status": ReviewStatus.approved,  # a system import: no human step
            },
        )
        counts.files_new += 1
    if source_id is None:
        source_id = uuid.uuid4()
        await session.execute(
            insert(Source),
            {
                "id": source_id,
                "category": SourceCategory.admin_act,
                "title": act.title,
                "official_ref": act.official_ref,
                "source_rank": SourceRank.official_secondary,
                "license": License.public,
                "status": RecordStatus.analyzed,
            },
        )
        counts.sources_new += 1
    await session.execute(
        insert(Extraction),
        [
            {
                "file_id": file_id,
                "source_id": source_id,
                "parser_name": ADMIN_ACT_PARSER_NAME,
                "parser_version": act.parser_version,
                "fields": s.fields,
                "confidence": s.confidence,
                "warnings": s.warnings,
            }
            for s in pending
        ],
    )


async def load(
    factory: async_sessionmaker[AsyncSession], acts: list[PreparedAct], counts: Counts
) -> uuid.UUID | None:
    """Write what is not in the database yet, one transaction per genelge; a genelge whose write
    fails for a database reason lands in `counts.errors` and the others go on. Returns the job
    id, or None when nothing was new."""
    known = await _known(factory, [act.ref for act in acts])
    todo = []
    for act in acts:
        pending = [s for s in act.sections if _key(act, s) not in known[act.ref].keys]
        counts.skipped_existing += len(act.sections) - len(pending)
        if pending:
            todo.append((act, pending))
    if not todo:
        return None
    async with factory() as session:
        job = IngestJob(
            kind=IngestKind.bulk, status=IngestStatus.running, started_at=datetime.now(UTC)
        )
        session.add(job)
        await session.commit()
    for act, pending in todo:
        # Counted on a copy, merged after the commit: a rolled-back genelge adds nothing.
        done = Counts()
        try:
            async with factory() as session:
                await _write_act(session, act, pending, known[act.ref].source_id, job.id, done)
                await session.commit()
        except DBAPIError as exc:
            if not is_row_error(exc):
                raise
            counts.errors.append({"ref": act.ref, "error": error_name(exc)})
            continue
        counts.new += len(pending)
        counts.sources_new += done.sources_new
        counts.files_new += done.files_new
    return job.id


def build_summary(acts: Sequence[PreparedAct], counts: Counts) -> dict[str, Any]:
    """What a run did; `acts` lists the sections and bands of every genelge in the input."""
    return {
        "sections": sum(len(act.sections) for act in acts),
        "new": counts.new,
        "skipped": counts.skipped_existing,
        "sources_new": counts.sources_new,
        "files_new": counts.files_new,
        "errors": len(counts.errors),
        "error_refs": counts.errors,
        "acts": {
            act.ref: {
                "sections": len(act.sections),
                "bands": dict(Counter(s.confidence["band"] for s in act.sections)),
            }
            for act in acts
        },
    }


async def _run(path: Path) -> int:
    records, errors = read_records(path)
    acts = prepare(records)
    counts = Counts(errors=errors)
    engine = make_engine(get_settings().database_url)
    factory = make_session_factory(engine)
    try:
        job_id = await load(factory, acts, counts)
        summary = build_summary(acts, counts)
        if job_id:
            await finish_job(factory, job_id, summary)
    finally:
        await engine.dispose()
    print(
        f"sections {summary['sections']}, new {summary['new']}, skipped {summary['skipped']}, "
        f"errors {summary['errors']}, acts {summary['acts']}"
    )
    for error in counts.errors:
        print(f"error: {error['ref']}: {error['error']}")
    return 1 if summary["errors"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.loaders.admin_acts", description=__doc__)
    parser.add_argument("acts", type=Path, help="admin-acts.jsonl of `hukuk-ingest admin-acts`")
    return asyncio.run(_run(parser.parse_args(argv).acts))


if __name__ == "__main__":
    sys.exit(main())
